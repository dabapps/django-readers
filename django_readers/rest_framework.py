from copy import deepcopy
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
from django_readers import specs
from django_readers.utils import SpecVisitor
from rest_framework import serializers
from rest_framework.utils import model_meta


class _SpecToSerializerVisitor(SpecVisitor):
    def __init__(self, model):
        self.model = model
        self.field_builder = serializers.ModelSerializer()
        self.info = model_meta.get_field_info(model)
        self.fields = {}

    def _snake_case_to_capfirst(self, snake_case):
        return "".join(part.title() for part in snake_case.split("_"))

    def visit_str(self, item):
        return self.visit_dict_item_str(item, item)

    def visit_dict_item_str(self, key, value):
        # This is a model field, so we can use ModelSerializer
        # machinery to figure out which output field type to use
        field_class, field_kwargs = self.field_builder.build_field(
            value,
            self.info,
            self.model,
            0,
        )
        if key != value:
            field_kwargs["source"] = value
        field_kwargs.setdefault("read_only", True)
        self.fields[key] = field_class(**field_kwargs)
        return key, value

    def visit_dict_item_list(self, key, value):
        # This is a relationship, so we recurse and create
        # a nested serializer to represent it
        rel_info = self.info.relations[key]
        capfirst = self._snake_case_to_capfirst(key)
        child_serializer = spec_to_serializer_class(
            f"{capfirst}Serializer",
            rel_info.related_model,
            value,
            is_root=False,
        )
        self.fields[key] = child_serializer(
            read_only=True,
            many=rel_info.to_many,
        )
        return key, value

    def visit_dict_item_dict(self, key, value):
        # This is an aliased relationship, so we basically
        # do the same as the previous case, but handled
        # slightly differently to set the `source` correctly
        relationship_name, relationship_spec = next(iter(value.items()))
        rel_info = self.info.relations[relationship_name]
        capfirst = self._snake_case_to_capfirst(relationship_name)
        child_serializer = spec_to_serializer_class(
            f"{capfirst}Serializer",
            rel_info.related_model,
            relationship_spec,
            is_root=False,
        )
        self.fields[key] = child_serializer(
            read_only=True,
            many=rel_info.to_many,
            source=relationship_name,
        )
        return key, value

    def visit_dict_item_tuple(self, key, value):
        # The output field has been explicity configured in the spec.
        # We copy the field so its _creation_counter is correct and
        # it appears in the right order in the resulting serializer
        if hasattr(value, "output_field"):
            output_field = deepcopy(value.output_field)
            output_field._kwargs["read_only"] = True
            self.fields[key] = output_field
        else:
            # Fallback case: we don't know what field type to use
            self.fields[key] = serializers.ReadOnlyField()
        return key, value

    visit_dict_item_callable = visit_dict_item_tuple

    def visit_tuple(self, item):
        if hasattr(item, "output_field"):
            # This must be a projector pair, so `output_field` is actually a
            # dictionary mapping field names to Fields
            for name, field in item.output_field.items():
                output_field = deepcopy(field)
                output_field._kwargs["read_only"] = True
                self.fields[name] = output_field
        return item

    visit_callable = visit_tuple


class _ToRepresentationMixin:
    def to_representation(self, instance):
        return self.context["project"](instance)


def spec_to_serializer_class(serializer_name, model, spec, is_root=True):
    visitor = _SpecToSerializerVisitor(model)
    visitor.visit(spec)

    bases = (serializers.Serializer,)
    if is_root:
        bases = (_ToRepresentationMixin,) + bases

    return type(serializer_name, bases, visitor.fields)


class _CallWithRequestVisitor(SpecVisitor):
    def __init__(self, request):
        self.request = request

    def visit_callable(self, fn):
        if getattr(fn, "call_with_request", False):
            return fn(self.request)
        return fn


class SpecMixin:
    spec = None

    def get_spec(self):
        if self.spec is None:
            raise ImproperlyConfigured("SpecMixin requires spec or get_spec")
        return self.spec

    def _preprocess_spec(self, spec):
        visitor = _CallWithRequestVisitor(self.request)
        return visitor.visit(spec)

    def get_reader_pair(self):
        return specs.process(self._preprocess_spec(self.get_spec()))

    @cached_property
    def reader_pair(self):
        return self.get_reader_pair()

    @property
    def prepare(self):
        return self.reader_pair[0]

    @property
    def project(self):
        return self.reader_pair[1]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.prepare(queryset)

    def get_serializer_class(self):
        name = self.__class__.__name__.replace("View", "") + "Serializer"
        model = getattr(getattr(self, "queryset", None), "model", None)
        return spec_to_serializer_class(name, model, self.spec)

    def get_serializer_context(self):
        return {"project": self.project, **super().get_serializer_context()}


class PairWithOutputField(tuple):
    output_field = None


def output_field(output_field):
    if isinstance(output_field, dict):
        if not all(
            isinstance(item, serializers.Field) for item in output_field.values()
        ):
            raise TypeError("Each value must be an instance of Field")
    elif not isinstance(output_field, serializers.Field):
        raise TypeError("output_field must be an instance of Field")

    def decorator(pair_or_callable):
        if isinstance(pair_or_callable, tuple):
            pair_or_callable = PairWithOutputField(pair_or_callable)
        pair_or_callable.output_field = output_field
        return pair_or_callable

    return decorator


class out:
    def __init__(self, output_field):
        self.output_field = output_field

    def __rrshift__(self, other):
        return output_field(self.output_field)(other)


def call_with_request(fn):
    fn.call_with_request = True
    return fn

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from django.contrib.contenttypes.fields import ReverseGenericManyToOneDescriptor
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
from django_readers import specs
from django_readers.utils import SpecVisitor
from functools import wraps
from rest_framework import serializers
from rest_framework.utils import model_meta
from typing import Optional

import inspect

TYPES_TO_SERIALIZER_FIELDS = {
    int: serializers.IntegerField(),
    Optional[int]: serializers.IntegerField(allow_null=True),
    str: serializers.CharField(),
    Optional[str]: serializers.CharField(allow_null=True),
    float: serializers.FloatField(),
    Optional[float]: serializers.FloatField(allow_null=True),
    bool: serializers.BooleanField(),
    Optional[bool]: serializers.BooleanField(allow_null=True),
    date: serializers.DateField(),
    Optional[date]: serializers.DateField(allow_null=True),
    datetime: serializers.DateTimeField(),
    Optional[datetime]: serializers.DateTimeField(allow_null=True),
    time: serializers.TimeField(),
    Optional[time]: serializers.TimeField(allow_null=True),
    timedelta: serializers.DurationField(),
    Optional[timedelta]: serializers.DurationField(allow_null=True),
}


def serializer_field_for_type(type_):
    try:
        return TYPES_TO_SERIALIZER_FIELDS[type_]
    except (KeyError, TypeError):
        pass


def add_annotation(obj, key, value):
    obj._readers_annotation = getattr(obj, "_readers_annotation", None) or {}
    obj._readers_annotation[key] = value


def get_annotation(obj, key):
    # Either the item itself or (if this is a pair) just the
    # producer/projector function may have been decorated
    if value := getattr(obj, "_readers_annotation", {}).get(key):
        return value
    if isinstance(obj, tuple):
        return get_annotation(obj[1], key)


def get_serializer_field(obj):
    # if the object has been explicitly annotated, always
    # prefer the annotation
    annotation = get_annotation(obj, "field")
    if annotation:
        # the annotation might be a type, if so we need to map it to a field
        field = serializer_field_for_type(annotation)
        if field:
            return field
        # otherwise, we assume it's a field and return it as-is
        return annotation

    # if this is a pair, we're interested in the producer (or projector)
    if isinstance(obj, tuple):
        obj = obj[1]

    # if it's a callable, does it have an return type annotation?
    if callable(obj):
        return_type = inspect.signature(obj).return_annotation
        return serializer_field_for_type(return_type)


class ProjectionSerializer:
    def __init__(self, data=None, many=False, context=None):
        self.many = many
        self._data = data
        self.context = context

    @property
    def data(self):
        project = self.context["view"].project
        if self.many:
            return [project(item) for item in self._data]
        return project(self._data)


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
        return ProjectionSerializer


class _CallWithRequestVisitor(SpecVisitor):
    def __init__(self, request):
        self.request = request

    def visit_callable(self, fn):
        return fn(self.request)


class _SpecToSerializerVisitor(SpecVisitor):
    def __init__(self, model, name):
        self.model = model
        self.name = name
        self.field_builder = serializers.ModelSerializer()
        self.info = model_meta.get_field_info(model)
        self.fields = {}

    def _lowercase_with_underscores_to_capitalized_words(self, string):
        return "".join(part.title() for part in string.split("_"))

    def _prepare_field(self, field, kwargs=None):
        # We copy the field so its _creation_counter is correct and
        # it appears in the right order in the resulting serializer.
        # We also force it to be read_only
        field = deepcopy(field)
        if kwargs:
            field._kwargs.update(kwargs)
        field._kwargs["read_only"] = True
        return field

    def visit_str(self, item):
        return self.visit_dict_item_str(item, item)

    def visit_dict_item_str(self, key, value):
        # This is a model field name. First, check if the
        # field has been explicitly overridden
        if out := get_serializer_field(value):
            field = self._prepare_field(out, kwargs=get_annotation(value, "kwargs"))

        else:
            # No explicit override, so we can use ModelSerializer
            # machinery to figure out which field type to use
            field_class, field_kwargs = self.field_builder.build_field(
                value,
                self.info,
                self.model,
                0,
            )
            if key != value:
                field_kwargs["source"] = value
            field_kwargs.setdefault("read_only", True)

            if kwargs := get_annotation(value, "kwargs"):
                field_kwargs.update(kwargs)
            field = field_class(**field_kwargs)

        self.fields[str(key)] = field
        return key, value

    def _get_child_serializer_kwargs(self, rel_info):
        kwargs = {"read_only": True, "many": rel_info.to_many}
        if rel_info.model_field and rel_info.model_field.null:
            kwargs["allow_null"] = True
        if rel_info.reverse and not rel_info.to_many:
            kwargs["allow_null"] = True
        return kwargs

    def _get_rel_info(self, rel_name):
        descriptor = getattr(self.model, rel_name)
        # Special case for reverse generic relations (GenericRelation field)
        # as these don't appear in rest-framework's rel_info
        if isinstance(descriptor, ReverseGenericManyToOneDescriptor):
            return model_meta.RelationInfo(
                model_field=descriptor.field,
                related_model=descriptor.field.related_model,
                to_many=True,
                to_field=None,
                has_through_model=False,
                reverse=True,
            )
        return self.info.relations[rel_name]

    def visit_dict_item_list(self, key, value):
        # This is a relationship, so we recurse and create
        # a nested serializer to represent it
        rel_info = self._get_rel_info(key)
        capfirst = self._lowercase_with_underscores_to_capitalized_words(key)
        child_serializer_class = serializer_class_for_spec(
            f"{self.name}{capfirst}",
            rel_info.related_model,
            value,
        )
        serializer_kwargs = self._get_child_serializer_kwargs(rel_info)
        self.fields[key] = child_serializer_class(**serializer_kwargs)
        return key, value

    def visit_dict_item_dict(self, key, value):
        # This is an aliased relationship, so we basically
        # do the same as the previous case, but handled
        # slightly differently to set the `source` correctly
        relationship_name, relationship_spec = next(iter(value.items()))
        rel_info = self._get_rel_info(relationship_name)
        capfirst = self._lowercase_with_underscores_to_capitalized_words(key)
        child_serializer_class = serializer_class_for_spec(
            f"{self.name}{capfirst}",
            rel_info.related_model,
            relationship_spec,
        )
        serializer_kwargs = self._get_child_serializer_kwargs(rel_info)
        serializer_kwargs["source"] = relationship_name
        self.fields[key] = child_serializer_class(**serializer_kwargs)
        return key, value

    def visit_dict_item_tuple(self, key, value):
        # This is a producer pair.
        out = get_serializer_field(value)
        kwargs = get_annotation(value, "kwargs") or {}
        if out:
            field = self._prepare_field(out, kwargs)
            self.fields[key] = field
        else:
            # Fallback case: we don't know what field type to use
            self.fields[key] = serializers.ReadOnlyField(**kwargs)
        return key, value

    visit_dict_item_callable = visit_dict_item_tuple

    def visit_tuple(self, item):
        # This is a projector pair.
        out = get_annotation(item, "field")
        kwargs = get_annotation(item, "kwargs") or {}
        if out:
            # `out` is a dictionary mapping field names to either types or Fields
            for name, field in out.items():
                mapped_field = serializer_field_for_type(field)
                if mapped_field:
                    field = mapped_field
                field = self._prepare_field(field, kwargs)
                self.fields[name] = field
        # There is no fallback case because we have no way of knowing the shape
        # of the returned dictionary, so the schema will be unavoidably incorrect.
        return item

    visit_callable = visit_tuple


def serializer_class_for_spec(name_prefix, model, spec):
    visitor = _SpecToSerializerVisitor(model, name_prefix)
    visitor.visit(spec)

    return type(
        f"{name_prefix}Serializer",
        (serializers.Serializer,),
        {
            "Meta": type("Meta", (), {"model": model}),
            **visitor.fields,
        },
    )


def serializer_class_for_view(view):
    name_prefix = view.__class__.__name__
    if name_prefix.endswith("View"):
        name_prefix = name_prefix[:-4]

    if hasattr(view, "model"):
        model = view.model
    else:
        model = getattr(getattr(view, "queryset", None), "model", None)

    if not model:
        raise ImproperlyConfigured(
            "View class must have either a 'queryset' or 'model' attribute"
        )

    return serializer_class_for_spec(name_prefix, model, view.spec)


class PairWithAnnotation(tuple):
    _readers_annotation = None


class StringWithAnnotation(str):
    _readers_annotation = None


def out(*args, **kwargs):
    if args:
        if len(args) != 1:
            raise TypeError("Provide a single field or dictionary of fields")
        field_or_dict = args[0]
        if isinstance(field_or_dict, dict):
            if not all(
                isinstance(item, serializers.Field)
                or item in TYPES_TO_SERIALIZER_FIELDS.keys()
                for item in field_or_dict.values()
            ):
                raise TypeError(
                    "Each value must be an instance of Field or a supported type"
                )
        elif not (
            isinstance(field_or_dict, serializers.Field)
            or field_or_dict in TYPES_TO_SERIALIZER_FIELDS.keys()
        ):
            raise TypeError("Must be an instance of Field or a supported type")
    else:
        field_or_dict = None

    class ShiftableDecorator:
        def __call__(self, item):
            if callable(item):

                @wraps(item)
                def wrapper(*args, **kwargs):
                    result = item(*args, **kwargs)
                    return self(result)

                add_annotation(wrapper, "field", field_or_dict)
                add_annotation(wrapper, "kwargs", kwargs)
                return wrapper
            else:
                if isinstance(item, str):
                    item = StringWithAnnotation(item)
                    add_annotation(item, "field", field_or_dict)
                    add_annotation(item, "kwargs", kwargs)
                if isinstance(item, tuple):
                    item = PairWithAnnotation(item)
                    add_annotation(item, "field", field_or_dict)
                    add_annotation(item, "kwargs", kwargs)
                return item

        def __rrshift__(self, other):
            return self(other)

    return ShiftableDecorator()

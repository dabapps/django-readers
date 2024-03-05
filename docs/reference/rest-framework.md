If you use [django-rest-framework](https://www.django-rest-framework.org/), `django-readers` provides a view mixin that allows you to easily use a [spec](specs.md) to serialize your data:

```python
from django_readers.rest_framework import SpecMixin


class AuthorDetailView(SpecMixin, RetrieveAPIView):
    queryset = Author.objects.all()
    spec = [
        "id",
        "name",
        {
            "book_set": [
                "id",
                "title",
                "publication_date",
            ]
        },
    ]
```

This mixin is only suitable for use with `RetrieveAPIView` or `ListAPIView`. It doesn't use a "real" Serializer: it calls the `project` function that is the result of processing your `spec`. We recommend using separate views for endpoints that modify data, rather than combining these concerns into a single endpoint.

If your endpoint needs to provide dynamic behaviour based on the incoming request, you have two options:

1. `SpecMixin` supports one extra feature in its `spec` property: any callable in the spec (in place of a pair) will automatically be called at request time, and passed a single argument: the `request` object. This callable can return a pair of functions that close over the request.
2. You can override the `get_spec` method and return your spec. Note that this approach is not compatible with schema generation (see below).

If you need to override `get_queryset`, you must call `self.prepare` on the queryset that you return:

```python hl_lines="9"
class GoogleyAuthorListView(SpecMixin, ListAPIView):

    spec = [
       ...,
    ]

    def get_queryset(self):
        queryset = Author.objects.filter(email__contains="google.com")
        return self.prepare(queryset)
```

## Serializer and schema generation

The `django-readers` `SpecMixin` bypasses the usual Django REST framework approach of serializing data using a `Serializer` in favour of using a projector function to generate a mapping of names to values based on a model instance. This is simpler, faster and less memory intensive than using a `Serializer`. However, some parts of REST framework rely on serializers to do their work; in particular, the [schema generation mechanism](https://www.django-rest-framework.org/api-guide/schemas/) introspects serializer fields to generate an OpenAPI schema.

To enable schema generation (and any other requirements for a "real" serializer) for `django-readers` views, two utility functions are provided: `serializer_class_for_spec` and `serializer_class_for_view`.

Note that the serializers created by these functions are not actually used at request time: they are useful only for introspection.

## `rest_framework.serializer_class_for_spec(name_prefix, model, spec)` {: #serializer-class-for-spec}

This takes:

* A name prefix for the resulting top-level serializer class. This should be `CapitalizedWords`, the word `Serializer` will be appended.
* A model class
* A spec

It returns a serializer class representing the spec, with nested serializers representing the relationships.

For named fields (strings in the spec) it uses the same mechanism as `ModelSerializer` to introspect the model and select appropriate serializer fields for each model field. For custom pairs, the field must be specified explicitly: [see below](#customising-serializer-fields) for details.

```python hl_lines="11"
spec = [
    "name",
    {
        "book_set": [
            "id",
            "title",
        ]
    },
]

cls = serializer_class_for_spec("Publisher", Publisher, spec)
print(cls())
```

This prints something like:

```
PublisherSerializer():
    name = CharField(max_length=100, read_only=True)
    book_set = PublisherBookSetSerializer(many=True, read_only=True):
        id = IntegerField(label='ID', read_only=True)
        title = CharField(allow_null=True, max_length=100, read_only=True, required=False)
```

## `rest_framework.serializer_class_for_view(view)` {: #serializer-class-for-view}

This higher-level function generates a serializer given a view instance. 

* The name of the serializer is inferred from the view name (the word `View` is removed).
* The model class is taken from either the `queryset` attribute of the view, or (if `get_queryset` has been overridden), explicitly from the `model` attribute.
* The spec is taken from the `spec` attribute of the view.

This can be used to create a simple [custom `AutoSchema` subclass](https://www.django-rest-framework.org/api-guide/schemas/#autoschema) to support schema generation:

```python
class SpecSchema(AutoSchema):
    def get_serializer(self, path, method):
        return serializer_class_for_view(self.view)()
```

Note that `django-readers` does not provide this view mixin: it is trivial to create and add to your project, and it is likely that it will need to be customised to your specific needs. 

## Customising serializer fields

For named fields (strings) in a spec, `serializer_class_for_spec` uses the same mechanism as `ModelSerializer` to infer the field types for the model. However, for custom pairs in a spec, the serializer field to use must be specified explicitly. `django-readers` provides a utility called `out` which can be used in two ways: as a decorator, or inline in a spec.

### `out` as a decorator

For custom pair functions, you can use `out` as a decorator, and provide a serializer field instance to use in the serializer:

```python hl_lines="4"
from django_readers.rest_framework import out


@out(serializers.CharField())
def hello_world():
    return qs.noop, lambda instance: "Hello world"


class SomeView(SpecMixin, RetrieveAPIView):
    queryset = SomeModel.objects.all()
    spec = [
        ...,
        {"hello": hello_world()},
        ...,
    ]
```

You can also decorate only the producer function of a pair:

```python hl_lines="1"
@out(serializers.CharField())
def produce_hello_world(instance):
    return "Hello world"

hello_world = qs.noop, produce_hello_world

class SomeView(SpecMixin, RetrieveAPIView):
    queryset = SomeModel.objects.all()
    spec = [
        ...,
        {"hello": hello_world},
        ...,
    ]
```

For projector pairs, `out` should be given a dictionary mapping the field names in the returned dictionary to their output field types:

```python hl_lines="1-6"
@out(
    {
        "hello": serializers.CharField(),
        "answer": serializers.IntegerField(),
    }
)
def hello_world():
    return qs.noop, lambda instance: {"hello": "world", "answer": 42}

class SomeView(SpecMixin, RetrieveAPIView):
    queryset = SomeModel.objects.all()
    spec = [
        ...,
        hello_world(),
        ...,
    ]
```

Again, you can also decorate only the projector function of the pair.

### `out` used inline in a spec

For cases where a reusable pair function (eg from the `django_readers.pairs` module) is being used in a spec, it may be inconvenient to wrap this in a function just to apply the `out` decorator. In this case, `out` supports a special "[DSL](https://en.wikipedia.org/wiki/Domain-specific_language)-ish" syntax, by overriding the `>>` operator to allow it to easily be used inline in a spec:

```python hl_lines="5"
class SomeView(SpecMixin, RetrieveAPIView):
    queryset = SomeModel.objects.all()
    spec = [
        ...,
        {"genre": pairs.field_display("genre") >> out(serializers.CharField())},
        ...,
    ]
```

This mechanism can also be used to override the output field type for an autogenerated field (a string).

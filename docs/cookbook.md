This section of the documentation is intended to give you real-world examples of how to achieve specific requirements with `django-readers`. It uses the same set of models (books, authors and publishers) introduced in the [tutorial](tutorial.md).

In most cases, we just show the spec itself, and any custom reader functions. These specs can be used either inside a view or with the Django REST framework `SpecMixin`.

## Retrieve fields from a model instance

```python
spec = [
    "id",
    "title",
    "publication_date",
]
```

## Retrieve id of related model instance

```python
spec = [
    "publisher_id",
]
```

## Alias a field (change the output field name)

```python
spec = [
    "id",
    {"date_published": "publication_date"},
]
```

## Retrieve fields on related instance or instances

```python
spec = [
    {
        "publisher": [
            "id",
            "name",
        ]
    },
    {
        "authors": [
            "id",
            "name",
        ]
    },
]
```

## Follow a reverse foreign key

This spec would be applied to the `Publisher` model:

```python
spec = [
    "name",
    {
        "book_set": [
            "id",
            "title",
        ]
    },
]
```

## Retrieve a list of the IDs of related objects

```python
spec = [
    "name",
    {"book_set": pairs.pk_list("book_set")},
]
```

## Filter the set of related instances

`pairs.filter(args)` is a shortcut for `(qs.filter(args), projectors.noop)`

```python
spec = [
    "name",
    {
        "book_set": [
            pairs.filter(publication_date__year=2022),
            "id",
            "title",
        ]
    },
]
```

## Alias a relationship

To alias a relationship, nest the relationship spec inside another dictionary:

```python
spec = [
    "name",
    {
        "books_2022": {
            "book_set": [
                pairs.filter(publication_date__year=2022),
                "id",
                "title",
            ]
        }
    },
]
```

## Alias a relationship with a custom `to_attr`

The above example uses the default name (`book_set`) for the relationship when
the related objects are prefetched. If you wish to load the same relationship
multiple times with different filters, this won't work. To provide a `to_attr`
for the relationship, drop down to the `specs.relationship` function:

```python
from django_readers import specs


spec = [
    "name",
    {
        "books_2022": specs.relationship(
            "book_set",
            [
                pairs.filter(publication_date__year=2022),
                "id",
                "title",
            ],
            to_attr="books_2022",
        )
    },
]
```

## Apply arbitrary queryset operations

```python
spec = [
    "name",
    {
        "book_set": [
            pairs.filter(publication_date__year=2022),
            (qs.distinct(), projectors.noop),
            "id",
            "title",
        ]
    },
]
```

## Retrieve a `count` of related models

```python
spec = [
    "name",
    {"published_book_count": pairs.count("book")},
]
```


## Derive a value via an arbitrary annotation

```python
published_in_2022 = (
    qs.annotate(
        published_in_2022=Case(
            When(publication_date__year=2022, then=True),
            default=False,
        )
    ),
    producers.attr("published_in_2022"),
)

spec = [
    "title",
    {"published_in_2022": published_in_2022},
]
```

## Retrieve a value from a model property that requires a model field to be loaded

```python
class Book(models.Model):
    ...

    @property
    def published_this_year(self):
        return self.publication_date.year == date.today().year
```

```python
spec = [
    "title",
    {
        "published_this_year": (
            qs.include_fields("publication_date"),
            producers.attr("published_this_year"),
        )
    },
]
```

## Call a method on a model that requires a model field to be loaded

```python
class Book(models.Model):
    ...

    def published_in_year(self, year):
        return self.publication_date.year == year
```

```python
spec = [
    "title",
    {
        "published_in_2020": (
            qs.include_fields("publication_date"),
            producers.method("published_in_year", 2020),
        )
    },
]
```

## Parameterise a pair with a higher-order pair function

```python
def email_domain_is(domain):
    prepare = qs.include_fields("email")

    def produce(author):
        return author.email.endswith(domain)

    return prepare, produce
```

```python
spec = [
    "id",
    "name",
    {"works_for_google": email_domain_is("google.com")},
    {"works_for_apple": email_domain_is("apple.com")},
]
```

## Use `select_related` instead of `prefetch_related`

We use the `specs.relationship` function but explicitly discard its queryset function and substitute our own. Note that this has major limitations: because the relationship is not represented by a queryset internally, the spec cannot be nested any further and no custom pairs can be used. Only do this if you're sure you know what you're doing.

```python
spec = [
    "id",
    "title",
    {
        "publisher": (
            qs.select_related_fields("publisher__name"),
            pairs.discard_queryset_function(
                specs.relationship("publisher", ["name"]),
            ),
        )
    },
]
```

## Specify output fields for Django REST framework introspection

The [Django REST framework layer](/reference/rest-framework/) supports generation of serializer classes based on a spec, for the purpose of introspection and schema generation. For custom behaviour like pairs and higher-order functions, the output field type must be explicitly specified. Below is an example covering a couple of use cases. See [the docs on serializer and schema generation](/reference/rest-framework/#serializer-and-schema-generation) for full details.

```python
from django_readers.rest_framework import out, serializer_class_for_view, SpecMixin
from rest_framework.views import RetrieveAPIView
from rest_framework import serializers


class SpecSchema(AutoSchema):
    def get_serializer(self, path, method):
        return serializer_class_for_view(self.view)()


@out(serializers.BooleanField())
def request_user_is_author(request):
    def produce(instance):
        return instance.author.email == request.user.email

    return (
        qs.auto_prefetch_relationship(
            "author",
            prepare_related_queryset=qs.include_fields("email"),
        ),
        produce,
    )


class BookDetailView(SpecMixin, RetrieveAPIView):
    schema = SpecSchema()
    queryset = Book.objects.all()
    spec = [
        "id",
        "title",
        {"request_user_is_author": request_user_is_author},
        {"format": pairs.field_display("format") >> out(serializers.CharField())},
    ]
```

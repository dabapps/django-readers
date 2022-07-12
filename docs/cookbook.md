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

    def published_in_year(self, year):
        return self.publication_date.year == year

    @property
    def published_this_year(self):
        return self.published_in_year(date.today().year)
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

    def project(author):
        return author.email.endswith(domain)

    return prepare, project
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

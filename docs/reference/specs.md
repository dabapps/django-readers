The `specs` module provides a layer of syntactic sugar on top of [pairs](pairs.md) that makes it much quicker and easier to assemble complex trees of producers and projectors. This layer is the real magic of `django-readers`: a straightforward way of specifying the shape of your data in order to efficiently select and project a complex tree of related objects.

A spec is a list. Under the hood, the `specs` module is a very lightweight wrapper on top of [`pairs`](pairs.md). Simple transformations are applied to each item in the spec to replace it with the relevant pair function. The list may contain:

* _Strings_. These are interpreted as field names and are replaced with [`pairs.field`](pairs.md#field).
* _Dictionaries_ serve two purposes:
    * If the dictionary value is a list, they are interpreted as relationships, with the key specifying the relationship name and the value being a "child spec" for projecting the related objects. This is a shortcut for [`pairs.relationship`](pairs.md#relationship).
    * If the value is anything else (a string or a `(prepare, produce)` pair), the value returned by the produce function in the pair is projected under the specified key. This is a shortcut for [`pairs.producer_to_projector`](pairs.md#producer_to_projector).
* _Projector pairs_ of `(prepare, project)` functions. These are left as-is, allowing you to implement your own arbitrarily complex logic if needed.

Import like this: `from django_readers import specs`

## `specs.process(spec)` {: #process}

Takes a spec and returns a projector pair `(prepare, project)`.

```python
from django_readers import specs

spec = [
    "name",
    {
        "book_set": [
            "title",
            "publication_date",
        ]
    },
]

prepare, project = specs.process(spec)

queryset = prepare(Author.objects.all())
result = [project(instance) for instance in queryset]
```

!!! note
    if [`django-zen-queries`](https://github.com/dabapps/django-zen-queries) is installed (which is recommended!), `django-readers` will automatically apply `queries_disabled()` to the `prepare` and `project` functions returned by `specs.process`. See the [tutorial](../tutorial.md#a-note-on-django-zen-queries) for details.

## `specs.relationship(name, relationship_spec, to_attr=None)` {: #relationship}

This function implements the behaviour of the `{"relationship_name": [child spec..]}` functionality in `specs.process`. It is useful if you wish to pass a `to_attr` argument to the underlying prefetch:

```python
spec = [
    "name",
    specs.relationship(
        "book_set",
        [
            pairs.filter(publication_date__year__lte=2017),
            "title",
            "publication_date",
        ],
        to_attr="vintage_books",
    ),
]
```

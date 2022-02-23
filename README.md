django-readers
==============

**A lightweight function-oriented toolkit for better organisation of business logic and efficient selection and projection of data in Django projects.**

Tested against Django 2.2, 3.2 and 4.0 on Python 3.6, 3.7, 3.8, 3.9 and 3.10

![Build Status](https://github.com/dabapps/django-readers/workflows/CI/badge.svg)
[![pypi release](https://img.shields.io/pypi/v/django-readers.svg)](https://pypi.python.org/pypi/django-readers)

### Installation

Install from PyPI

    pip install django-readers

## tl;dr

`django-readers` lets you write Django views like this:

```python
def author_list(request):
    spec = [
        "id",
        "name",
        {
            "book_set": [
                "id",
                "title",
                "publication_year",
            ]
        },
    ]

    prepare, project = specs.process(spec)
    queryset = prepare(Author.objects.all())
    return render(
        request,
        "author_list.html",
        {"authors": [project(instance) for instance in queryset]},
    )
```

And [Django REST framework](https://www.django-rest-framework.org/) views like this:

```python
class AuthorListView(SpecMixin, ListAPIView):
    queryset = Author.objects.all()
    spec = [
        "id",
        "name",
        {
            "book_set": [
                "id",
                "title",
                "publication_year",
            ]
        },
    ]
```

A `django-readers` "spec" precisely specifies the data that your view depends on (which fields from which models). _Only_ this data will be fetched from the database, in the most efficient way possible. This is intended to avoid the [N+1 queries problem](https://stackoverflow.com/questions/97197/what-is-the-n1-selects-problem-in-orm-object-relational-mapping) and can dramatically improve the performance of your application.

However, `django-readers` is more than just this. It is also intended to suggest patterns which help with organising business logic in a Django codebase, following a function-oriented style. It introduces a few simple concepts, and provides some tools to assemble them together into a working application. It can easily be combined with existing patterns and libraries.

* **queryset preparation functions** replace custom queryset methods and encapsulate data selection: filtering, annotation etc. They can be composed to express complex selection logic.
* **producer and projector functions** replace model methods and encapsulate business logic for transforming and presenting data. They can be combined to form lightweight business objects (dictionaries) that are the right shape for the code that consumes them.
* **reader pairs** combine queryset functions and producers, expressing the dependencies between them.
* a high-level **spec** provides a concise way to express exactly which data should be selected and projected at the point of use.

## A note on this documentation

`django-readers` is as much a set of recommended patterns as it is a library of code. This README attempts to explain the reasoning behind the patterns, and give some examples of how the library helps you to implement them. However, you are strongly encouraged to read the source to fully understand `django-readers`: it's quite straightforward and only 300 or so lines of code. Also, the tests (under `tests/`) provide some real-world examples of how each "layer" of the library might be used, so they are worth reading too.

## Motivation

Django common practices encourage a "fat models" approach. That is: most of the business logic of the application goes in the model layer (on the models themselves, or on custom managers or querysets). This is often a bad idea for several reasons:

First, it goes against the [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle). Models are already responsible for mapping between your database tables and your application code and back again. This mapping is a highly complex task, and that's quite enough for one set of classes to be responsible for.

Second, it is bad for code organisation, particularly in larger projects. Your `models.py` becomes a trash pile onto which all business logic is dumped. Models and querysets grow to thousands of lines of code. The API surface area for each model becomes huge, and this entire surface is available to any part of your application that imports the model.

Third and worst, often model methods themselves perform queries against other models. This is a disaster for application performance, leading to inefficient query patterns that can be very difficult to fix. When they _are_ fixed (through judicious use of `select_related` and `prefetch_related` on the queryset), the model methods become tightly bound to the precise way that the query is built, resulting in unpredictable and brittle code.

**`django-readers` encourages you to instead structure your code around plain functions rather than methods on classes. You can put these functions wherever you like in your codebase. Complex business logic is built by composing and combining these functions.**

`django-readers` provides a set of tools to help with the parts of your business logic that are responsible for _reads_ from the database: selecting and transforming data before presenting it to clients. It is designed to be used with Django templates as well as Django REST framework.

The functionality that `django-readers` provides is deliberately straightforward and interoperable with existing Django libraries, patterns and practices. You can choose to use just the parts of `django-readers` that appeal to you and make sense in your project.

## Features and concepts

`django-readers` is organised in three layers of _"reader functions"_. At the highest level of abstraction is `django_readers.specs` (the top layer), which depends on `django_readers.pairs` (the middle layer), which depends on `django_readers.producers`, `django_readers.projectors` and `django_readers.qs` (the bottom layer).

These layers can be intermingled in a real-world application. To expain each layer, it makes most sense to start at the bottom and work upwards.

### `django_readers.qs`: queryset preparation functions

A queryset preparation function is a function that accepts a queryset as its single argument, and returns a new queryset with some modifications applied.

```python
def prepare(queryset):
    return queryset.filter(name="shakespeare")
```

These functions are used to encapsulate database query logic which would traditionally live in a custom queryset method.

`django-readers` provides a library of functions (under `django_readers.qs`) which mirror all the default methods on the base `QuerySet` that return a new queryset.

Queryset functions can be combined with the `pipe` function (named following standard functional programming parlance). `qs.pipe` returns a new queryset function that calls each function in its argument list in turn, passing the return value of the first as the argument of the second, and so on. It literally "pipes" your queryset through its list of functions.

```python
from django_readers import qs

recent_books_with_prefetched_authors = qs.pipe(
    qs.filter(year__gte=2020),
    qs.prefetch_related("author_set"),
    qs.order_by("name"),
)

queryset = recent_books_with_prefetched_authors(Book.objects.all())
```

### `django_readers.producers` and `django_readers.projectors`: value production and model projection functions

A producer is a function that accepts a model instance as its single argument, and returns a value representing a subset or transformation of the instance data.

Business logic that would traditionally go in model methods should instead go in producers.

```python
from datetime import datetime


def produce_age(instance):
    return datetime.now().year - instance.birth_year


author = Author(name="Some Author", birth_year=1984)
print(produce_age(author))
#  37
```

The simplest producer is one that returns the value of an object attribute. `django-readers` provides a producer that does this:

```python
from django_readers import producers

author = Author(name="Some Author")
produce_name = producers.attr("name")
print(produce_name(author))
#  'Some Author'
```

Producers return a value, but in order to convert a model instance into a lightweight business object suitable for passing around your project, this value must be combined with a name. This is the role of a projector. A projector function takes a model instance and returns a dictionary mapping keys to the values returned by producer functions.

These functions "project" your data layer into your application's business logic domain. Think of the dictionary returned by a projector (the "projection") as the simplest possible domain object. Generally speaking, it's not necessary to write your own projector functions - you can simply wrap a producer function.

```python
from datetime import datetime


def produce_age(instance):
    return datetime.now().year - instance.birth_year


project_age = projectors.producer_to_projector("age", produce_age)

author = Author(name="Some Author", birth_year=1984)
print(project_age(author))
#  {'age': 37}
```

A dictionary is returned because these projectors are intended to be _composable_: multiple simple projector functions can be combined into a more complex projector function that returns a dictionary containing the keys and values from all of its child projectors. This is done using the `projectors.combine` function:

```python
from django_readers import producers, projectors

project = projectors.combine(
    projectors.producer_to_projector("name", producers.attr("name")),
    project_age,
)
print(project(author))
#  {'name': 'Some Author', 'age': 37}
```

This composition generally happens at the place in your codebase where the domain model is actually being _used_ (in a view, say). The projection will therefore contain precisely the keys needed by that view. This solves the problem of models becoming vast ever-growing flat namespaces containing all the functionality needed by all parts of your application.

Related objects can also be produced using the `producers.relationship` function, resulting in a nested projection:

```python
project = projectors.combine(
    projectors.producer_to_projector("name", producers.attr("name")),
    projectors.producer_to_projector("age", produce_age),
    projectors.producer_to_projector(
        "book_set",
        producers.relationship(
            "book_set",
            projectors.combine(
                projectors.producer_to_projector("title", producers.attr("title")),
                projectors.producer_to_projector(
                    "publication_year",
                    producers.attr("publication_year"),
                ),
            ),
        ),
    ),
)

print(project(author))
#  {'name': 'Some Author', 'age': 37, 'book_set': [{'title': 'Some Book', 'publication_year': 2019}]}
```

Note above that the second argument to `producers.relationship` is a projector function which projects each related object.

The `producers.attr` function takes an optional argument `transform_value`, which is a function that receives the value of the attribute and returns a new value. This is useful if the value of the attribute needs to be converted in some way during projection.

For example, imagine you have an `IntegerField` but you want the produced value to be a stringified version of the integer value. In that case, you can use `producers.attr("my_integer_field", transform_value=str)`.

By default, the `transform_value` function is only called if the value of the attribute is not `None` (so in the example above, if the database value of `my_integer_field` is `NULL` then `None` would be returned, rather than the string `"None"`). If you want the `transform_value` function to _always_ be called, use `producers.attr("my_integer_field", transform_value=str, transform_value_if_none=True)`.

Finally, the `producers.method` function will call the given method name on the instance, returning the result under a key matching the method name. Any extra arguments passed to `producers.method` will be passed along to the method.

### `django_readers.pairs`: "reader pairs" combining `prepare` with `produce` and `project`

`prepare` and `produce` (and therefore also `project`) functions are intimately connected, with the `produce`/`project` functions usually depending on fields, annotations or relationships loaded by the `prepare` function. For this reason, `django-readers` expects these functions to live together in two-tuples: `(prepare, produce)` (a "producer pair") and `(prepare, project)` (a "projector pair"). Remember that the difference between `produce` and `project` is that the former returns a single value, whereas the latter returns a dictionary binding one or more names (keys) to one or more values.

In the example used above, the `produce_age` producer depends on the `birth_year` field:

```python
age_pair = (qs.include_fields("birth_year"), produce_age)
```

`django-readers` includes some useful functions that create pairs. These attempt to produce the most efficient queries they can, which means loading only those database fields which are required to produce the value:

```python
from django_readers import pairs

prepare, produce = pairs.field("name")
queryset = prepare(Author.objects.all())
print(queryset.query)
#  SELECT "author"."id", "author"."name" FROM "author"
print(produce(queryset.first()))
#  'Some Author'
```

The `pairs.field` function takes the same `transform_value` and `transform_value_if_none` arguments as `producers.attr` (see above).

When composing multiple pairs together, it is again necessary to wrap the producer to convert it to a projector, thus forming `(prepare, project)` pairs. This can be done with the `pairs.producer_to_projector` function:

```python
prepare, project = pairs.combine(
    pairs.producer_to_projector("name", pairs.field("name")),
    pairs.producer_to_projector("birth_year", pairs.field("birth_year")),
)
```

Relationships can automatically be loaded and projected, too:

```python
prepare, project = pairs.combine(
    pairs.producer_to_projector("name", pairs.field("name")),
    pairs.producer_to_projector("age", age_pair),
    pairs.producer_to_projector(
        "book_set",
        pairs.relationship(
            "book_set",
            pairs.combine(
                pairs.producer_to_projector("title", pairs.field("title")),
                pairs.producer_to_projector(
                    "publication_year", pairs.field("publication_year")
                ),
            ),
        ),
    ),
)
```

Again, only the precise fields that are needed are loaded from the database. All relationship functions take an optional `to_attr` argument which is passed to the underlying `Prefetch` object.

Note that `django-readers` _always_ uses `prefetch_related` to load relationships, even in circumstances where `select_related` would usually be used (ie `ForeignKey` and `OneToOneField`), resulting in one query per relationship. This approach allows the code to be "fractal": the tree of `(prepare, project)` pairs can be recursively applied to the tree of related querysets.

Of course, it is quite possible to use `select_related` by applying `qs.select_related` at the root of your query, but this must be done manually. To help with this, `django-readers` provides `qs.select_related_fields`, which combines `select_related` with `include_fields` to allow you to specify exactly which fields you need from the related objects. Also, the `pairs` module provides functions to discard one or other item from the pair: `pairs.discard_projector` and `pairs.discard_queryset_function`. These are useful if you'd like to create a complex pair using the high-level `specs` module (see below) but only actually use one or other item from the pair. Note that these only exist for readability: they are equivalent to simply indexing into the pair (`pair[0]` or `pair[1]` respectively).

You can use `pairs.pk_list` to produce a list containing just the primary keys of the related objects.

As a shortcut, the `pairs` module provides functions called `filter`, `exclude` and `order_by`, which can be used to apply the given queryset functions to the queryset _without affecting the projection_. These are equivalent to (for example) `(qs.filter(arg=value), projectors.noop)` and are most useful for filtering or ordering related objects:

```python
prepare, project = pairs.combine(
    pairs.producer_to_projector("name", pairs.field("name")),
    pairs.producer_to_projector("age", age_pair),
    pairs.producer_to_projector(
        "book_set",
        pairs.relationship(
            "book_set",
            pairs.combine(
                pairs.filter(publication_year__gte=2020),
                pairs.order_by("title"),
                pairs.producer_to_projector("title", pairs.field("title")),
                pairs.producer_to_projector(
                    "publication_year", pairs.field("publication_year")
                ),
            ),
            to_attr="recent_books",
        ),
    ),
)
```

`django-readers` also comes with a pair function for working with Django's `get_FOO_display` mechanism. From the Django docs:

> For every field that has `choices` set, the object will have a `get_FOO_display()` method, where `FOO` is the name of the field. This method returns the “human-readable” value of the field.

The `pairs.field_display` function takes the field name as its single argument and returns a pair which loads the field from the database, and then produces the result of calling `get_<field>_display`.

Finally, `pairs.count` and `pairs.has` provide shortcuts to annotate a queryset with the count or existence of related objects, and produce these values.

### `django_readers.specs`: a high-level specification for efficient data querying and projection

Manually assembling trees of pairs as seen above may seem long-winded. The `specs` module provides a layer of syntactic sugar that makes it much easier. This layer is the real magic of `django-readers`: a straightforward way of specifying the shape of your data in order to efficiently select and project a complex tree of related objects.

The resulting nested dictionary structure may be returned from as view as a JSON response (assuming all your producers return JSON-serializable values), or included in a template context in place of a queryset or model instance.

A spec is a list. Under the hood, the `specs` module is a very lightweight wrapper on top of `pairs` - it applies simple transformations to the items in the list to replace them with the relevant pair functions. The list may contain:

* _strings_, which are interpreted as field names and are replaced with `pairs.field`,
* _dictionaries_, which serve two purposes: if the value is a list, they are interpreted as relationships (with the keys specifying the relationship name and the values being specs for projecting the related objects) and are replaced with `pairs.relationship`. If the value is anything else (a string or a `(prepare, produce)` pair), the value returned by the produce function in the pair is projected under the specified key.
* _pairs_ of `(prepare, project)` functions (see previous section), which are left as-is.

The example from the last section may be written as the following spec:

```python
from django_readers import specs

spec = [
    "name",
    {"age": age_pair},
    {
        "book_set": [
            "title",
            "publication_year",
        ]
    },
]

prepare, project = specs.process(spec)

queryset = prepare(Author.objects.all())
result = [project(instance) for instance in queryset]
```

The structure of this specification is heavily inspired by [`django-rest-framework-serialization-spec`](https://github.com/dabapps/django-rest-framework-serialization-spec/), minus the concept of "plugins", which are replaced with directly including `(prepare, produce)` pairs in the spec. It should be trivial to convert or "adapt" a `serialization-spec` plugin into a suitable `django-readers` pair.

### `django-rest-framework` view mixin

If you use [django-rest-framework](https://www.django-rest-framework.org/), `django-readers` provides a shortcut that allows you to easily use a `spec` to serialize your data:

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
                "publication_year",
            ]
        },
    ]
```

This mixin is only suitable for use with `RetrieveAPIView` or `ListAPIView`. It doesn't use a "real" Serializer: it calls the `project` function that is the result of processing your `spec`. We recommend using separate views for endpoints that modify data, rather than combining these concerns into a single endpoint.

If your endpoint needs to provide dynamic behaviour based on the user making the request, you should instead override the `get_spec` method and return your spec.

### A note on `django-zen-queries`

An important pattern to avoid inefficient database queries in Django projects is to isolate the *fetching of data* from the *rendering of data*. This pattern can be implemented with the help of [`django-zen-queries`](https://github.com/dabapps/django-zen-queries), which allows you to mark blocks of code under which database queries are not allowed.

In a project using `django-readers`, it is good practice to disallow queries in the `prepare` and `project` phases:

```python
import zen_queries

prepare, project = specs.process(
    [
        # some spec
    ]
)

with zen_queries.queries_disabled():
    queryset = prepare(Author.objects.all())

queryset = zen_queries.fetch(queryset)  # execute the database queries

with zen_queries.queries_disabled():
    result = [project(instance) for instance in queryset]

# ...render result as JSON or in a template
```

To enforce this, if `django-zen-queries` is installed, `django-readers` will automatically apply
`queries_disabled()` to the `prepare` and `project` functions returned by `specs.process`, so there is no need to apply it manually as in the above example.

### Where should this code go?

We recommend that your custom functions go in a file called `readers.py` inside your Django apps. Specs should be declared at the point they are used, usually in your `views.py`.

### What about other types of business logic?

You'll notice that `django-readers` is focused on _reads_: business logic which selects some data from the database and/or transforms it in such a way that it can be displayed to a user. What about other common types of business logic that involve accepting input from users and processing it?

`django-readers` doesn't provide any code to help with this, but we encourage you to follow the same function-oriented philosophy. Structure your codebase around functions which take model instances and encapsulate these sorts of write actions. You might choose to call them `action functions` and place them in a file called `actions.py`.

The other common task needed is data validation. We'd suggest Django forms and/or Django REST framework serializers are perfectly adequate here.

### Is `django-readers` a "service layer"?

Not really, although it does solve some of the same problems. It suggests alternative (and, we think, beneficial) ways to structure your business logic without attempting to hide or abstract away the underlying Django concepts, and so should be easily understandable by any experienced Django developer. You can easily "mix and match" `django-readers` concepts into an existing application.

If you are someone who feels more comfortable thinking in terms of established Design Patterns, you may consider the dictionaries returned from projector functions as simple [Data Transfer Objects](https://martinfowler.com/eaaCatalog/dataTransferObject.html), and the idea of dividing read and write logic into `readers` and `actions` as a version of [CQRS](https://martinfowler.com/bliki/CQRS.html).

## Code of conduct

For guidelines regarding the code of conduct when contributing to this repository please review [https://www.dabapps.com/open-source/code-of-conduct/](https://www.dabapps.com/open-source/code-of-conduct/)

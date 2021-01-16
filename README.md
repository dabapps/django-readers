djunc
=====

**STATUS: EXPERIMENTAL**

![Build Status](https://github.com/dabapps/djunc/workflows/CI/badge.svg)
[![pypi release](https://img.shields.io/pypi/v/djunc.svg)](https://pypi.python.org/pypi/djunc)


**A lightweight function-oriented toolkit for better organisation of business logic and efficient selection and projection of data in Django projects.**

Tested against Django 2.2 - 3.1 on Python 3.6 - 3.9.

### Installation

Install from PyPI

    pip install djunc

## A note on this documentation

`djunc` is as much a set of recommended patterns as it is a library of code. This README attempts to explain the reasoning behind the patterns, and give some examples of how the library helps you to implement them. However, you are strongly encouraged to read the source to fully understand `djunc`: it's quite straightforward and considerably less than 200 lines of code. Also, the tests (under `tests/`) provide some real-world examples of how each "layer" of the library might be used, so they are worth reading too.

## Motivation

Django common practices encourage a "fat models" approach. That is: most of the business logic of the application goes in the model layer (on the models themselves, or on custom managers or querysets). This is a bad idea for several reasons:

First, it goes against the [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle). Models are *already* responsible for mapping between your database tables and your application code and back again. This mapping is a highly complex task, and that's quite enough for one set of classes to be responsible for.

Second, is is bad for code organisation, particularly in larger projects. Your `models.py` becomes a trash pile onto which all business logic is dumped. Models grow to thousands of lines of code. The API surface area for each model becomes huge, and this entire surface is available to any part of your application that imports that model.

Third and worst, often model methods themselves perform queries against other models. This is a disaster for application performance, leading to inefficient query patterns that can be very difficult to fix. When they are fixed (through judicious use of `select_related` and `prefetch_related` on the queryset), the model methods become tightly bound to the precise way that the query is built, resulting in unpredictable and brittle code.

**`djunc` encourages you to instead structure your code around plain *functions* rather than methods on classes. You can put these functions wherever you like in your codebase. Complex business logic is built by composing and combining these functions.**

The functionality that `djunc` provides is deliberately straightforward and interoperable with existing Django libraries, patterns and practices. You can choose to use just the parts of `djunc` that appeal to you and make sense in your project.

## Features and concepts

`djunc` is organised in three layers. At the highest level of abstraction is `djunc.spec` (the top layer), which depends on `djunc.pairs` (the middle layer), which depends on `djunc.projectors` and `djunc.qs` (the bottom layer).

These layers can be intermingled in a real-world application. To expain each layer, it makes most sense to start at the bottom and work upwards.

### `djunc.qs`: queryset preparation functions

A *queryset preparation function* is a function that *accepts a queryset* as its single argument, and *returns a new queryset* with some modifications applied.

```
def prepare(queryset):
    return queryset.filter(name="djunc")
```

These functions are used to encapsulate database query logic, where traditionally a custom queryset method would be used.

`djunc` provides a library of functions (under `djunc.qs`) which mirror all the default methods on the base `QuerySet` that return a new queryset.

Queryset functions can be combined with the `pipe` function (named following standard functional programming parlance). `qs.pipe` returns a new queryset function that calls each function in its argument list in turn, passing the return value of each as the argument of the next. It literally "pipes" your queryset through its list of functions.

```python
from djunc import qs

recent_books_with_prefetched_authors = qs.pipe(
    qs.filter(year__gte=2020),
    qs.prefetch_related("author_set"),
    qs.order_by("name"),
)

queryset = recent_books_with_prefetched_authors(Book.objects.all())
```

### `djunc.projectors`: model projection functions

A *projector* is a function that *accepts a model instance* as its single argument, and *returns a dictionary* containing some subset or transformation of the instance data.

These functions "project" your database layer into your application's business logic domain. Business logic that would traditionally go in model methods should instead go in projectors.

The simplest projector is one that returns the value of a model field, wrapped in a dictionary with the field name as its single key. `djunc` provides a projector that does this:

```python
from djunc import projectors

author = Author(name="Some Author")
project = projectors.field("name")
print(project(author))
#  {'name': 'Some Author'}
```

It's trivial to write a custom projector:

```python
from datetime import datetime

def project_age(instance):
    return {"age": datetime.now().year - instance.birth_year}

author = Author(name="Some Author", birth_year=1984)
print(project_age(author))
#  {'age': 37}
```

Projectors can be combined. The keys and values from the dictionary returned by each individual projector are merged togther.

```python
from djunc import projectors

project = projectors.combine(
    projectors.field("name"),
    project_age,
)
print(project(author))
#  {'name': 'Some Author', 'age': 37}
```

Related objects can also be projected, resulting in a nested projection:

```python
project = projectors.combine(
    projectors.field("name"),
    project_age,
    projectors.relationship("book_set", projectors.combine(
        projectors.field("title"),
        projectors.field("publication_year"),
    )),
)
print(project(author))
#  {'name': 'Some Author', 'age': 37, 'book_set': [{'title': 'Some Book', 'publication_year': 2019}]}
```

### `djunc.pairs`: (prepare, project) pairs

`prepare` and `project` functions are intimately connected, with the `project` function depending on fields, annotations or relationships loaded by the `prepare` function. For this reason, `djunc` expects these functions to live together in a two-tuple called a *pair*: `(prepare, project)`.

In the example used above, the `project_age` projector depends on the `birth_year` field:

```python
age_pair = (qs.include_fields("birth_year"), project_age)
```

`djunc` includes some useful functions that create pairs. These attempt to produce the most efficient queries they can, which means loading only those database fields which are required to project your query:

```python
from djunc import pairs

prepare, project = pairs.field("name")
queryset = prepare(Author.objects.all())
print(queryset.query)
#  SELECT "author"."id", "author"."name" FROM "author"
result = project(queryset.first())
print(project(author))
#  {'name': 'Some Author'}
```

Relationships can automatically be loaded and projected, too:

```python
prepare, project = pairs.combine(
    pairs.field("name"),
    age_pair,
    pairs.auto_relationship("book_set", *pairs.combine(
        pairs.field("title"),
        pairs.field("publication_year"),
    ))
)
```

Again, only the precise fields that are needed are loaded from the database.

Note that `djunc` _always_ uses `prefetch_related` to load relationships, even in circumstances where `select_related` would usually be used (ie `ForeignKey` and `OneToOneField`), resulting in one query per relationship. This approach allows the code to be "fractal": the tree of `(prepare, project)` pairs can be recursively applied to the tree of related querysets. Of course, it is quite possible to use `select_related` by applying `qs.select_related` at the root of your query, but this must be done manually.

### `djunc.spec`: a high-level spec for efficient data querying and projection

This layer is the real magic of `djunc`: a straightforward way of specifying the shape of your data in order to efficiently select and project a complex tree of related objects.

The resulting nested dictionary structure may be returned from as view as a JSON response (assuming all your projectors return JSON-serializable values), or included in a template context in place of a queryset or model instance.

A spec is a list, which may contain:

* _strings_, which are interpreted as field names,
* _dictionaries_, which are interpreted as relationships (with the keys specifying the relationship name and the values being specs for projecting the related objects)
* _pairs_ of `(prepare, project)` functions (see previous section), which are left as-is.

The example from the last section may be written as the following spec:

```python
from djunc import spec

prepare, project = spec.process(
    [
        "name",
        age_pair,
        {"book_set": ["title", "publication_year"]},
    ]
)

queryset = prepare(Author.objects.all())
result = [project(instance) for instance in queryset]
```

The structure of this spec is heavily inspired by [`django-rest-framework-serialization-spec`](https://github.com/dabapps/django-rest-framework-serialization-spec/), minus the concept of "plugins", which are replaced with directly including `(prepare, project)` pairs in the spec. It should be trivial to convert or "adapt" a `serialization-spec` plugin into a suitable `djunc` pair.

### A note on `django-zen-queries`

An important pattern to avoid inefficient database queries in Django projects is to isolate the *fetching of data* from the *rendering of data*. This pattern can be implemented with the help of [`django-zen-queries`](https://github.com/dabapps/django-zen-queries), which allows you to mark blocks of code under which database queries are not allowed.

In a project using `djunc`, it is good practice to disallow queries in the `prepare` and `project` phases:

```python
import zen_queries

prepare, project = spec.process([
    # some spec
])

with zen_queries.queries_disabled():
    queryset = prepare(Author.objects.all())

queryset = zen_queries.fetch(queryset)  # execute the database queries

with zen_queries.queries_disabled():
    result = [project(instance) for instance in queryset]

# ...render result as JSON or in a template
```

## Code of conduct

For guidelines regarding the code of conduct when contributing to this repository please review [https://www.dabapps.com/open-source/code-of-conduct/](https://www.dabapps.com/open-source/code-of-conduct/)

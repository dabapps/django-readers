`django-readers` provides a set of tools to help with the parts of your business logic that are responsible for _reads_ from the database: selecting and transforming data before presenting it to clients. It can be used with views that render Django templates as well as Django REST framework views.

The functionality that `django-readers` provides is deliberately straightforward and interoperable with existing Django libraries, patterns and practices. You can choose to use just the parts of `django-readers` that appeal to you and make sense in your project.

A `django-readers` "spec" precisely specifies the data that your view depends on (which particular fields from which related models). _Only_ this data will be fetched from the database, in the most efficient way possible. This is intended to avoid the [N+1 queries problem](https://stackoverflow.com/questions/97197/what-is-the-n1-selects-problem-in-orm-object-relational-mapping) and can dramatically improve the performance of your application.

However, `django-readers` is more than just this. It is also intended to suggest patterns which help with organising business logic in a Django codebase, following a function-oriented style. It introduces a few simple concepts, and provides some tools to assemble them together into a working application. It can easily be combined with existing patterns and libraries.

* **queryset preparation functions** replace custom queryset methods and encapsulate data selection: filtering, annotation etc. They can be composed to express complex selection logic.
* **producer and projector functions** replace model methods and encapsulate business logic for transforming and presenting data. They can be combined to form lightweight business objects (dictionaries) that are the right shape for the code that consumes them.
* **reader pairs** combine queryset functions and producers (or projectors), expressing the dependencies between them.
* a high-level **spec** provides a concise way to express exactly which data should be selected and projected at the point of use.

## Motivation

Django common practices encourage a "fat models" approach. Most of the business logic of the application goes in the model layer (on the models themselves, or on custom managers or querysets). Experience has suggested that this is often a bad idea for several reasons:

First, it goes against the [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle). Models are already responsible for mapping between your database tables and your application code and back again. This mapping is a highly complex task, and that's quite enough for one set of classes to be responsible for.

Second, it is bad for code organisation, particularly in larger projects. Your `models.py` becomes a trash pile onto which all business logic is dumped. Models and querysets grow to thousands of lines of code. The API surface area for each model becomes huge, and this entire surface is available to any part of your application that imports the model.

Third and worst, often model methods themselves perform queries against other models. This is a disaster for application performance, leading to inefficient query patterns that can be very difficult to fix. When they _are_ fixed (through judicious use of `select_related` and `prefetch_related` on the queryset), the model methods become tightly coupled to the precise way that the query is built, resulting in unpredictable and brittle code.

`django-readers` encourages you to structure your code around plain functions rather than methods on classes. You can put these functions wherever you like in your codebase. Complex business logic is built by composing and combining these functions.

!!! note
    YAGNI, "You Aren't Gonna Need It", it's a [well-understood mantra](https://martinfowler.com/bliki/Yagni.html) in software development. It means that you should only make changes to your software (including adding abstraction and generalising code structures) when you are sure that you absolutely need them, and not before. Related to this is the famous quote from Donald Knuth: "premature optimization is the root of all evil". This suggests that usually performance concerns fall under YAGNI: you shouldn't spend time making code fast until its slowness becomes a real problem for users.

    As a counterpoint to this advice, Simon Willison coined the phrase [PAGNI](https://simonwillison.net/2021/Jul/1/pagnis/), "Probably Are Gonna Need It". PAGNI applies in situations "when the cost of adding something later is so dramatically expensive compared with the cost of adding it early on that it’s worth taking the risk [...] when you know from experience that an initial investment will pay off many times over."

    `django-readers` (and its sister project [`django-zen-queries`](https://github.com/dabapps/django-zen-queries)) were built partly as a result of a strong belief (gained through many years of experience) that understanding and controlling your application's database querying behaviour firmly falls into the PAGNI category. This is particularly true of applications that you know are going to be complex: any code abstraction patterns you decide to follow in order to manage the complexity _must_ take into account query patterns or they are highly likely to cause terrible performance problems. This is the heart of the [object-relational impedance mismatch](https://en.wikipedia.org/wiki/Object%E2%80%93relational_impedance_mismatch).

## Features and concepts

`django-readers` is organised in three layers of _"reader functions"_. At the highest level of abstraction is `django_readers.specs` (the top layer), which depends on `django_readers.pairs` (the middle layer), which depends on `django_readers.producers`, `django_readers.projectors` and `django_readers.qs` (the bottom layer).

These layers can be intermingled in a real-world application. To expain each layer, it makes most sense to start at the bottom and work upwards.

### Queryset preparation functions

A queryset preparation function is a function that accepts a queryset as its single argument, and returns a new queryset with some modifications applied. These functions are used to encapsulate database query logic that would traditionally live in a custom queryset method. If you were writing one of these yourself, it might look like this:

```python
def prepare(queryset):
    return queryset.filter(name="shakespeare")
```

However, you don't usually need to write your own queryset functions: `django-readers` provides a [library of functions under `django_readers.qs`](reference/queryset-functions.md) which mirror all the default methods on the base `QuerySet` that return a new queryset, as well as some extra utility functions.

Queryset functions can be combined with the [`qs.pipe`](reference/queryset-functions.md#pipe) function (named following standard functional programming parlance). `qs.pipe` returns a new queryset function that calls each function in its argument list in turn, passing the return value of the first as the argument of the second, and so on. It literally "pipes" your queryset through its list of functions.

```python
from django_readers import qs

recent_books_with_prefetched_authors = qs.pipe(
    qs.filter(publication_date__year=2020),
    qs.prefetch_related("authors"),
    qs.order_by("name"),
)

queryset = recent_books_with_prefetched_authors(Book.objects.all())
```

### Producers and projectors

A [producer](reference/producers.md) is a function that accepts a model instance as its single argument, and returns a value representing a subset or transformation of the instance data.

Business logic that would traditionally go in model methods should instead go in producers.

```python
from datetime import datetime


def produce_age(instance):
    return datetime.now().year - instance.birth_year


author = Author(name="Some Author", birth_year=1984)
print(produce_age(author))
#  37
```

The simplest producer is one that returns the value of an object attribute. `django-readers` provides a function to create producers that do this:

```python
from django_readers import producers

author = Author(name="Some Author")
produce_name = producers.attr("name")
print(produce_name(author))
#  'Some Author'
```

Producers return a value, but in order to convert a model instance into a lightweight business object (a dictionary) suitable for passing around your project, this value must be combined with a name. This is the role of a [projector](reference/projectors.md). A projector function takes a model instance and returns a dictionary mapping keys to the values returned by producer functions.

These functions "project" your data layer into your application's business logic domain. Think of the dictionary returned by a projector (the "projection") as the simplest possible domain object. Generally speaking, it's not necessary to write your own projector functions. You can instead wrap a producer function with [`projectors.producer_to_projector`](reference/projectors.md#producer_to_projector)

```python
from datetime import datetime
from django_readers import projectors


def produce_age(instance):
    return datetime.now().year - instance.birth_year


project_age = projectors.producer_to_projector("age", produce_age)

author = Author(name="Some Author", birth_year=1984)
print(project_age(author))
#  {'age': 37}
```

Like queryset functions, projectors are intended to be _composable_: multiple simple projector functions can be combined into a more complex projector function that returns a dictionary containing the keys and values from all of its child projectors. This is done using the [`projectors.combine`](reference/projectors.md#combine) function:

```python
from django_readers import producers, projectors

project = projectors.combine(
    projectors.producer_to_projector("name", producers.attr("name")),
    projectors.producer_to_projector("age", produce_age),
)
print(project(author))
#  {'name': 'Some Author', 'age': 37}
```

This composition generally happens at the place in your codebase where the domain model is actually being _used_ (in a view, say). The projection will therefore contain precisely the keys needed by that view. This solves the problem of models becoming vast ever-growing flat namespaces containing all the functionality needed by all parts of your application.

Related objects can also be produced using the [`producers.relationship`](reference/producers.md#relationship) function, resulting in a nested projection:

```python
project = projectors.combine(
    projectors.producer_to_projector("name", producers.attr("name")),
    projectors.producer_to_projector("age", produce_age),
    projectors.producer_to_projector(
        "book_set",
        producers.relationship(
            "book_set",
            projectors.combine(
                projectors.producer_to_projector(
                    "title",
                    producers.attr("title"),
                ),
                projectors.producer_to_projector(
                    "publication_date",
                    producers.attr("publication_date"),
                ),
            ),
        ),
    ),
)

print(project(author))
#  {
#      'name': 'Some Author',
#      'age': 37,
#      'book_set': [
#          {'title': 'Some Book', 'publication_date': 2019}
#      ]
#   }
```

Note above that the second argument to `producers.relationship` is a projector function to project each related object.

### Pairs

`prepare` and `produce` (and therefore also `project`) functions are intimately connected, with the `produce`/`project` functions usually depending on fields, annotations or relationships loaded by the `prepare` function. For this reason, `django-readers` expects these functions to live together in two-tuples: `(prepare, produce)` (a "producer pair") and `(prepare, project)` (a "projector pair"). Remember that the difference between `produce` and `project` is that the former returns a single value, whereas the latter returns a dictionary binding one or more names (keys) to one or more values.

In the example used above, the `produce_age` producer depends on the `birth_year` field:

```python
age = (qs.include_fields("birth_year"), produce_age)
```

`django-readers` includes [some useful functions that create pairs](reference/pairs.md). These attempt to generate the most efficient queries they can, which means loading only those database fields required to produce the value or values:

```python
from django_readers import pairs

prepare, produce = pairs.field("name")
queryset = prepare(Author.objects.all())
print(queryset.query)
#  SELECT "author"."id", "author"."name" FROM "author"
print(produce(queryset.first()))
#  'Some Author'
```

When composing multiple pairs together, it is again necessary to wrap the producer to convert it to a projector, thus forming `(prepare, project)` pairs. This can be done with the [`pairs.producer_to_projector`](reference/pairs.md#producer_to_projector) function:

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
    pairs.producer_to_projector("age", age),
    pairs.producer_to_projector(
        "book_set",
        pairs.relationship(
            "book_set",
            pairs.combine(
                pairs.producer_to_projector("title", pairs.field("title")),
                pairs.producer_to_projector(
                    "publication_date", pairs.field("publication_date")
                ),
            ),
        ),
    ),
)
```

Again, only the precise fields that are needed are loaded from the database. All relationship functions take an optional `to_attr` argument which is passed to the underlying `Prefetch` object.

Note that `django-readers` _always_ uses `prefetch_related` to load relationships, even in circumstances where `select_related` would usually be used (i.e. `ForeignKey` and `OneToOneField`), resulting in one query per relationship. This approach allows the code to be "fractal": the tree of `(prepare, project)` pairs can be recursively applied to the tree of related querysets. It is possible to use `select_related` but this [must be done manually](cookbook.md#use-select_related-instead-of-prefetch_related).

### Specs

Manually assembling trees of pairs as seen above may seem long-winded. [The `specs` module](reference/specs.md) provides a layer of syntactic sugar that makes it much easier. This layer is the real magic of `django-readers`: a straightforward way of specifying the shape of your data in order to efficiently select and project a complex tree of related objects.

The resulting nested dictionary structure may be returned from a view as a JSON response (assuming all your producers return JSON-serializable values), or included in a template context in place of a queryset or model instance.

A spec is a list. Under the hood, the `specs` module is a very lightweight wrapper on top of `pairs`. Each item in the list undergoes a simple transformation to replace it with a pair function. See [the reference documentation for specs](reference/specs.md) for details.

The example from the last section may be written as the following spec:

```python
from django_readers import specs

spec = [
    "name",
    {"age": age},
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
    The structure of this specification is heavily inspired by [`django-rest-framework-serialization-spec`](https://github.com/dabapps/django-rest-framework-serialization-spec/), minus the concept of "plugins", which are replaced with directly including `(prepare, produce)` pairs in the spec. It should be trivial to convert or "adapt" a `serialization-spec` plugin into a suitable `django-readers` pair.

## Where should this code go?

We recommend that your custom functions go in a file called `readers.py` inside your Django apps. Specs should be declared at the point they are used, usually in your `views.py`.

## What about other types of business logic?

You'll notice that `django-readers` is focused on _reads_: business logic which selects some data from the database and/or transforms it in such a way that it can be displayed to a user. What about other common types of business logic that involve accepting input from users and processing it?

`django-readers` doesn't provide any code to help with this, but we encourage you to follow the same function-oriented philosophy. Structure your codebase around functions which take model instances and encapsulate these sorts of write actions. You might choose to call them `action functions` and place them in a file called `actions.py`.

The other common task needed is data validation. We'd suggest Django forms and/or Django REST framework serializers are perfectly adequate here.

## Is `django-readers` a "service layer"?

Not really, although it does solve some of the same problems. It suggests alternative (and, we think, beneficial) ways to structure your business logic without attempting to hide or abstract away the underlying Django concepts, and so should be easily understandable by any experienced Django developer. You can easily "mix and match" `django-readers` concepts into an existing application.

If you are someone who feels more comfortable thinking in terms of established Design Patterns, you may consider the dictionaries returned from projector functions as simple [Data Transfer Objects](https://martinfowler.com/eaaCatalog/dataTransferObject.html), and the idea of dividing read and write logic into `readers` and `actions` as a version of [CQRS](https://martinfowler.com/bliki/CQRS.html).

## Is `django-readers` a serialization or data conversion library?

Not really, although again it does solve some of the same problems. `django-readers` is often compared to projects like [`attrs`](https://www.attrs.org/)/[`cattrs`](https://cattrs.readthedocs.io/) and [`pydantic`](https://pydantic-docs.helpmanual.io/).

However, `django-readers` is focused on the _shape_ of the data and how to extract it from the database (via the Django ORM) efficiently, rather than converting and validating the types. It eschews a class-oriented style in favour of plain, composable functions operating on plain data structures like dictionaries, and deliberately avoids static type annotations.

If your intention is to render your data to JSON, we recommend you use `django-readers` to project the model field values, and then lean on Django or Django REST framework's built-in rich encoders for converting types like `datetime` and `UUID` to JSON-friendly strings.

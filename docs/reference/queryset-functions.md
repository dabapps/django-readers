Queryset functions take a queryset as their single argument and return a modified queryset. The `qs` module contains higher-order functions that create queryset functions.

Import like this: `from django_readers import qs`

## Functions that mirror built-in QuerySet methods

* `qs.filter`
* `qs.all`
* `qs.exclude`
* `qs.select_related`
* `qs.prefetch_related`
* `qs.order_by`
* `qs.distinct`
* `qs.extra`
* `qs.defer`
* `qs.only`
* `qs.using`
* `qs.annotate`

These functions mirror the methods on the base `QuerySet` class that return new querysets. See [the Django documentation](https://docs.djangoproject.com/en/3.2/ref/models/querysets/#methods-that-return-new-querysets) for an explanation of these.

An example of how to use them:

```python
prepare = qs.filter(name__startswith="Fred")
queryset = prepare(Author.objects.all())
```

This is equivalent to:

```python
queryset = Author.objects.filter(name__startswith="Fred")
```

## `qs.noop` {: #noop}

This is a queryset function that does nothing: equivalent to calling `.all()` on a queryset. It is useful for creating pairs in which the producer function does not require any data from the database to return its value.

## `qs.include_fields(*fields)` {: #include_fields}

Returns a queryset function that tells the queryset to return the specified fields from the database and defer the rest. This is like the built-in `.only(*fields)` method, but is _composable_. On a standard queryset, repeated calls to `.only` will override each other, so calling `Author.objects.only("name").only("email")` is equivalent to just calling `Author.objects.only("email")`. On the other hand, `include_fields` _adds_ the provided fields to the set of fields to load:

```python
queryset = Author.objects.all()
queryset = qs.include_fields("name")(queryset)
queryset = qs.include_fields("email")(queryset)
```

This is equivalent to `Author.objects.only("name", "email")`.

## `qs.pipe(*fns)` {: #pipe}

Queryset functions can be composed with the `pipe` function (named following standard functional programming parlance). `qs.pipe` returns a new queryset function that calls each function in its argument list in turn, passing the return value of the first as the argument of the second, and so on. It literally "pipes" your queryset through its list of functions.

```python
prepare = qs.pipe(
    qs.include_fields("name"),
    qs.include_fields("email"),
    qs.filter(name__startswith="Fred"),
)
queryset = prepare(Author.objects.all())
```

Think of `pipe` as being a nicer way to nest queryset function calls:

```python
queryset = qs.filter(name__startswith="Fred")(
    qs.include_fields("email")(
        qs.include_fields("name")(
            Author.objects.all(),
        )
    )
)
```

## `qs.select_related_fields(*fields)` {: #select_related_fields}

Combines `select_related` with `include_fields` to allow you to specify exactly which fields you need from the related objects.

```python
prepare = qs.pipe(
    qs.include_fields("title"),
    qs.select_related_fields("publisher__name"),
)
```

## Prefetching

!!! note
    The below functions return functions that use `prefetch_related` to efficiently load related objects. We use `prefetch_related` to load all relationship types because this means our functions can be recursive - we can apply pairs to the related querysets, all the way down the tree.

There are six types of relationship from the point of view of the "main" object:

  * Forward one-to-one - a OneToOneField on the main object
  * Reverse one-to-one - a OneToOneField on the related object
  * Forward many-to-one - a ForeignKey on the main object
  * Reverse many-to-one - a ForeignKey on the related object
  * Forward many-to-many - a ManyToManyField on the main object
  * Reverse many-to-many - a ManyToManyField on the related object

ManyToManyFields are symmetrical, so the latter two collapse down to the same thing.
The forward one-to-one and many-to-one are identical as they both relate a single
related object to the main object. The reverse one-to-one and many-to-one are identical
except the former relates the main object to a single related object, and the latter
relates the main object to many related objects. Because the `projectors.relationship`
function already infers whether to iterate or project a single instance, we can collapse
these two functions into one as well.

There are functions for forward, reverse or many-to-many relationships, and then
an "auto" function which selects the correct relationship type by introspecting the
model. It shouldn't usually be necessary to use the manual functions unless you're
doing something weird, like providing a custom queryset.

## `qs.prefetch_forward_relationship(name, related_queryset, prepare_related_queryset=noop, to_attr=None)` {: #prefetch_forward_relationship}

!!! note
    It shouldn't usually be necessary to use this function directly: `auto_prefetch_relationship` (see below) is almost always a better option.

```python
prepare = qs.prefetch_forward_relationship(
    "publisher",
    Publisher.objects.all(),
    qs.include_fields("name"),
)
queryset = prepare(Book.objects.all())
```

This is equivalent to:

```python
queryset = Book.objects.prefetch_related(
    Prefetch("publisher", queryset=Publisher.objects.only("name"))
)
```

## `prefetch_reverse_relationship(name, related_name, related_queryset, prepare_related_queryset=noop, to_attr=None)` {: #prefetch_reverse_relationship}

!!! note
    It shouldn't usually be necessary to use this function directly: `auto_prefetch_relationship` (see below) is almost always a better option.

```python
prepare = qs.prefetch_reverse_relationship(
    "book_set",
    "publisher",
    Book.objects.all(),
    qs.include_fields("name"),
)
queryset = prepare(Publisher.objects.all())
```

This is equivalent to:

```python
queryset = Publisher.objects.prefetch_related(
    Prefetch("book_set", queryset=Book.objects.only("publisher", "name"))
)
```

## `prefetch_many_to_many_relationship(name, related_queryset, prepare_related_queryset=noop, to_attr=None)`  {: #prefetch_many_to_many_relationship}

!!! note
    It shouldn't usually be necessary to use this function directly: `auto_prefetch_relationship` (see below) is almost always a better option.

```python
prepare = qs.prefetch_many_to_many_relationship(
    "authors",
    Author.objects.all(),
    qs.include_fields("name"),
)
```

This is equivalent to:

```python
queryset = Book.objects.prefetch_related(
    Prefetch("authors", queryset=Author.objects.only("name"))
)
```

## `qs.auto_prefetch_relationship(name, prepare_related_queryset=noop, to_attr=None)` {: #auto_prefetch_relationship}

Usually, the above functions do not need to be used directly. Instead, `auto_prefetch_relationship` can figure out which one to use by looking at the model:

```python
prepare = qs.pipe(
    qs.auto_prefetch_relationship(
        "authors",
        prepare_related_queryset=qs.pipe(
            qs.include_fields("name"),
            qs.filter(email__icontains="google.com"),
            to_attr="googley_authors",
        ),
    ),
    qs.auto_prefetch_relationship(
        "publisher", prepare_related_queryset=qs.include_fields("name")
    ),
)
queryset = prepare(Book.objects.all())
```

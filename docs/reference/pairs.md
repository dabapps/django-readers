Pair functions return a tuple of two functions: either `(prepare, produce)` (a "producer pair" consisting of a [queryset function](queryset-functions.md) and a [producer function](producers.md)) or `(prepare, project)` (a "projector pair" consisting of a [queryset function](queryset-functions.md) and a [projector function](projectors.md)). The grouping of these two types of function represents a dependency: **in order to call the producer (or projector) function on a model instance, you must first call the queryset function on the queryset that was used to retrieve the instance**.

Remember that the difference between a producer and a projector is that the former returns a single value, whereas the latter returns a dictionary binding one or more names (keys) to one or more values. In order to use a pair in a [spec](specs.md), it must be a projector pair, so that the values returned by each projector in the spec are associated with names (the keys) that can be used in the final projection. However, at the point where a pair is created in your codebase, you often don't know what the output key should be: you are only interested in the value derived from the instance. So it's almost always the case that custom pairs will be written as producer pairs, and converted to projector pairs at the point where they are used in a spec, either by using the [`pairs.producer_to_projector`](#producer_to_projector) function or by using the shorthand syntax available in a [spec](specs.md).

Import like this: `from django_readers import pairs`

## `pairs.field(name, *, transform_value=None, transform_value_if_none=False)` {: #field}

Returns a pair which loads and produces the value of a model field.

```python
from django_readers import pairs

prepare, produce = pairs.field("name")
queryset = prepare(Author.objects.all())
print(queryset.query)
#  SELECT "author"."id", "author"."name" FROM "books_author"
print(produce(queryset.first()))
#  'Some Author'
```

The `pairs.field` function takes the same `transform_value` and `transform_value_if_none` arguments as [`producers.attr`](producers.md#attr).

## `pairs.field_display(name)` {: #field_display}

A pair function for working with Django's `get_FOO_display` mechanism. From the Django docs:

> For every field that has `choices` set, the object will have a `get_FOO_display()` method, where `FOO` is the name of the field. This method returns the “human-readable” value of the field.

The `pairs.field_display` function takes the field name as its single argument and returns a pair which loads the field from the database, and then produces the result of calling `get_<field>_display`.

## `pairs.annotate(*args, **kwargs)` {: #annotate}

Returns a pair that adds an annotation to the queryset and produces the annotated value. Like the `annotate` method on `QuerySet`, this can take either a positional argument (if the annotation function supports this) or a keyword argument. Unlike the annotate method, this can only handle a single annotation at a time.

This function can optionally take `transform_value` and `transform_value_if_none` keyword arguments, which are passed to the [producer](producers.md#attr).

For example:

```python
from django.db.models.functions import ExtractYear
from django_readers import pairs

prepare, produce = pairs.annotate(
    publication_year=ExtractYear("publication_date"),
)
queryset = prepare(Book.objects.all())
print(queryset.query)
#  SELECT "book"."id", EXTRACT('year' FROM "book"."publication_date"
#  AT TIME ZONE 'UTC') AS "publication_year" FROM "books_book"
print(produce(queryset.first()))
#  2013
```

## `pairs.count(name, *args, **kwargs)` {: #count}

Returns a pair which annotates a `Count` of the named relationship field onto the queryset, and produces its value. The `*args` and `**kwargs` parameters to this function are passed directly to the underlying `Count` annotation, so can be used to provide `distinct` and `filter` arguments.

## `pairs.has(name, *args, **kwargs)` {: #has}

Returns a pair which annotates a `Count` of the named relationship field onto the queryset, and produces a boolean representing whether or not that count is zero. The `*args` and `**kwargs` parameters to this function are passed directly to the underlying `Count` annotation, so can be used to provide `distinct` and `filter` arguments.

## `pairs.sum(name, *args, **kwargs)` {: #sum}

Returns a pair which annotates a `Count` of the named relationship field onto the queryset, and produces its value. The `*args` and `**kwargs` parameters to this function are passed directly to the underlying `Sum` annotation, so can be used to provide `distinct` and `filter` arguments etc.

## `pairs.filter(*args, **kwargs)` {: #filter}

Returns a pair consisting of a [`qs.filter`](queryset-functions.md#functions-that-mirror-built-in-queryset-methods) queryset function, and a [no-op projector](projectors.md#noop). Most useful for filtering relationships.

## `pairs.exclude(*args, **kwargs)` {: #exclude}

Returns a pair consisting of a [`qs.exclude`](queryset-functions.md#exclude) queryset function, and a [no-op projector](projectors.md#noop). Most useful for filtering relationships.

## `pairs.order_by(*args, **kwargs)` {: #order_by}

Returns a pair consisting of a [`qs.order_by`](queryset-functions.md#functions-that-mirror-built-in-queryset-methods) queryset function, and a [no-op projector](projectors.md#noop). Most useful for ordering relationships.

## Relationships

The following pair functions return the various [queryset functions that prefetch
relationships of various types](queryset-functions.md#prefetching), and then [produce those related objects](producers.md#relationship).

There are functions for forward, reverse or many-to-many relationships, and then
a `relationship` function which selects the correct one by introspecting the
model. It shouldn't usually be necessary to use the manual functions unless you're
doing something weird, like providing a custom queryset.

## `pairs.forward_relationship(name, related_queryset, relationship_pair, to_attr=None)` {: #forward_relationship}

See [`qs.prefetch_forward_relationship`](queryset-functions.md#prefetch_forward_relationship)

## `pairs.reverse_relationship(name, related_name, related_queryset, relationship_pair, to_attr=None)` {: #reverse_relationship}

See [`qs.prefetch_reverse_relationship`](queryset-functions.md#prefetch_reverse_relationship)

## `pairs.many_to_many_relationship(name, related_queryset, relationship_pair, to_attr=None)` {: #many_to_many_relationship}

See [`qs.prefetch_many_to_many_relationship`](queryset-functions.md#prefetch_many_to_many_relationship)

## `pairs.relationship(name, relationship_pair, to_attr=None)` {: #relationship}

See [`qs.auto_prefetch_relationship`](queryset-functions.md#auto_prefetch_relationship)

## `pairs.pk_list(name, to_attr=None)` {: #pk_list}

Given an attribute name (which should be a relationship field), return a pair consisting of a queryset function which prefetches the relationship (including only the primary key of each related object) and a producer which returns a list of those primary keys (or just a single PK if this is a to-one field, but this is an inefficient way of doing it).

See [`producers.pk_list`](producers.md#pk_list)

## Utilities

The following functions are useful when working with pairs in your codebase.

## `pairs.producer_to_projector(name, pair)` {: #producer_to_projector}

Given a name (key) and a _producer pair_ consisting of a queryset function and a producer function, returns a _projector pair_ consisting of the same queryset function, and a projector function which returns a dictionary mapping the name to the value derived from the producer.

## `pairs.combine(*pairs)` {: #combine}

Given a list of projector pairs as `*args`, return a pair which consists of a queryset function which pipes together the queryset function from each pair, and a projector which combines the projector function from each pair.

## `pairs.discard_projector(pair)` {: #discard_projector}

Given a pair, return only the first item in the pair (the queryset function). This is equivalent to `pairs[0]`, but using the function can make the intention clearer.

## `pairs.discard_queryset_function(pair)` {: #discard_queryset_function}

Given a pair, return only the second item in the pair (the projector function). This is equivalent to `pairs[1]`, but using the function can make the intention clearer.

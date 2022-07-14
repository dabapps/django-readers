Producer functions take a model instance as their single argument and return a value derived from that instance. The `producers` module contains higher-order functions that create producers.

Import like this: `from django_readers import producers`

## `producers.attr(name, *, transform_value=None, transform_value_if_none=False)` {: #attr}

Returns a producer which gets the specified attribute name from the instance. Most useful for retrieving the value of model fields.

```python
instance = Book(title="Pro Django")
produce_title = producers.attr("title")
value = produce_title(instance)
print(value)
# prints "Pro Django"
```

The `producers.attr` function takes an optional argument `transform_value`, which is a function that receives the value of the attribute and returns a new value. This is useful if the value of the attribute needs to be converted in some way during projection.

For example, imagine you have an `IntegerField` but you want the produced value to be a stringified version of the integer value. In that case, you can use `producers.attr("my_integer_field", transform_value=str)`.

By default, the `transform_value` function is only called if the value of the attribute is not `None` (so in the example above, if the database value of `my_integer_field` is `NULL` then `None` would be returned, rather than the string `"None"`). If you want the `transform_value` function to _always_ be called, use `producers.attr("my_integer_field", transform_value=str, transform_value_if_none=True)`.

## `producers.method(name, /, *args, **kwargs)` {: #method}

Returns a producer that calls the method name on the instance. If additional arguments and/or keyword arguments are given, they will be given to the method as well. For example:

```python
class Book(models.Model):
    ...

    def published_in_year(self, year):
        return self.publication_date.year == year


instance = Book(publication_year=2020)
produce_published_in_2020 = producers.method("published_in_year", 2020)
value = produce_published_in_2020(instance)
print(value)
# prints "True"
```

## `producers.relationship(name, related_projector)` {: #relationship}

!!! note
    You shouldn't generally need to use this function directly, instead it would be called for you via a higher-level construct such as a [pair function](pairs.md) or a [spec](specs.md).

Given an attribute name and a projector, return a producer which plucks the attribute off the instance, figures out whether it represents a single object or an iterable/queryset of objects, and applies the given [projector](projectors.md) to the related object or objects.

## `producers.pk_list(name)` {: #pk_list}

!!! note
    You shouldn't generally need to use this function directly, instead it would be called for you via a higher-level [pair function](pairs.md#pk_list).

Given an attribute name (which should be a relationship field), return a producer which returns a list of the PK of each item in the relationship (or just a single PK if this is a to-one field, but this is an inefficient way of doing it).

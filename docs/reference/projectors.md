Projector functions take a model instance as their single argument and return a dictionary mapping one or more keys to value derived from that instance, usually via [producer functions](producers.md). The `projectors` module contains higher-order functions that create producers from projectors, and compose projectors together.

Import like this: `from django_readers import projectors`

## `projectors.producer_to_projector(key, producer)` {: #producer_to_projector}

Given a key and a producer function, return a projector which calls the producer function on the given instance and returns a dictionary containing a single key mapping to this value.

```python
instance = Book(title="Pro Django")
produce_title = producers.attr("title")
project = projectors.producer_to_projector("title", produce_title)
projection = project(instance)
print(projection)
# prints {"title": "Pro Django"}
```

## `projectors.combine(*projectors)` {: #combine}

Takes multiple projectors provided as arguments and return another projector which calls each projector in turn and merges the resulting dictionaries.

```python
instance = Book(
    title="Pro Django",
    publication_date=datetime.date(2013, 7, 10),
)
produce_title = producers.attr("title")
produce_pub_date: producers.attr("publication_date")
project = projectors.combine(
    projectors.producer_to_projector("title", produce_title),
    projectors.producer_to_projector("publication_date", produce_pub_date),
)
projection = project(instance)
print(projection)
# prints {"title": "Pro Django", "publication_date": datetime.date(2013, 7, 10)}
```

## `projectors.noop` {: #noop}

A projector function which just returns an empty dictionary. Useful for including [pairs](pairs.md) in a spec which affect only the queryset, not the projection.

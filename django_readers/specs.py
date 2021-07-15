from django_readers import pairs
from django_readers.utils import queries_disabled


def process_item(item):
    if isinstance(item, str):
        return pairs.wrap_producer(item, pairs.field(item))
    if isinstance(item, dict):
        return pairs.combine(
            *[
                relationship(name, relationship_spec)
                for name, relationship_spec in item.items()
            ]
        )
    return item


def process(spec):
    return queries_disabled(pairs.combine(*(process_item(item) for item in spec)))


def relationship(name, relationship_spec, to_attr=None):
    return pairs.wrap_producer(
        to_attr or name, pairs.relationship(name, process(relationship_spec), to_attr)
    )

from django_readers import pairs
from django_readers.utils import queries_disabled


def process_item(item):
    if isinstance(item, str):
        item = {item: item}
    if isinstance(item, dict):
        return pairs.combine(
            *[
                relationship_or_wrap(name, child_spec)
                for name, child_spec in item.items()
            ]
        )
    return item


def process(spec):
    return queries_disabled(pairs.combine(*(process_item(item) for item in spec)))


def relationship(name, relationship_spec, to_attr=None):
    return pairs.wrap_producer(
        to_attr or name, pairs.relationship(name, process(relationship_spec), to_attr)
    )


def relationship_or_wrap(name, child_spec):
    if isinstance(child_spec, str):
        return pairs.wrap_producer(name, pairs.field(child_spec))
    if isinstance(child_spec, list):
        return relationship(name, child_spec)
    if isinstance(child_spec, dict):
        relationship_name, relationship_spec = next(iter(child_spec.items()))
        return pairs.wrap_producer(
            name, pairs.relationship(relationship_name, process(relationship_spec))
        )
    return pairs.wrap_producer(name, child_spec)

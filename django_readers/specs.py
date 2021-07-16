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
    return pairs.producer_to_projector(
        to_attr or name, pairs.relationship(name, process(relationship_spec), to_attr)
    )


def relationship_or_wrap(name, child_spec):
    if isinstance(child_spec, str):
        producer_pair = pairs.field(child_spec)
    elif isinstance(child_spec, list):
        producer_pair = pairs.relationship(name, process(child_spec))
    elif isinstance(child_spec, dict):
        if len(child_spec) != 1:
            raise ValueError("Aliased relationship spec must contain only one key")
        relationship_name, relationship_spec = next(iter(child_spec.items()))
        producer_pair = pairs.relationship(
            relationship_name, process(relationship_spec)
        )
    else:
        producer_pair = child_spec
    return pairs.producer_to_projector(name, producer_pair)

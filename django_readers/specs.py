from django_readers import pairs
from django_readers.utils import queries_disabled


def process_item(item):
    if isinstance(item, str):
        return pairs.field(item)
    if isinstance(item, dict):
        return pairs.combine(
            *[
                alias_or_relationship(name, child_spec)
                for name, child_spec in item.items()
            ]
        )
    return item


def process(spec):
    return queries_disabled(pairs.combine(*(process_item(item) for item in spec)))


def alias(alias_or_aliases, item):
    return pairs.alias(alias_or_aliases, process_item(item))


def alias_or_relationship(name, child_spec):
    if isinstance(child_spec, list):
        return relationship(name, child_spec)
    return alias(name, process_item(child_spec))


def relationship(name, relationship_spec, to_attr=None):
    return pairs.relationship(name, process(relationship_spec), to_attr)

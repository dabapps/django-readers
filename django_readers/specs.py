from django_readers import pairs
from django_readers.utils import queries_disabled


def process_item(item):
    if isinstance(item, str):
        return pairs.field(item)
    if isinstance(item, dict):
        return pairs.combine(
            *[
                pairs.auto_relationship(name, process(child_spec))
                for name, child_spec in item.items()
            ]
        )
    return item


def process(spec):
    return queries_disabled(pairs.combine(*(process_item(item) for item in spec)))


def alias(alias_or_aliases, item):
    return pairs.alias(alias_or_aliases, process_item(item))

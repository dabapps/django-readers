from djunc import pairs
from djunc.utils import queries_disabled


def process_item(item):
    if isinstance(item, str):
        return pairs.field(item)

    if isinstance(item, tuple) and isinstance(item[0], (str, dict)):
        alias_or_aliases, to_alias = item
        return pairs.alias(alias_or_aliases, *process_item(to_alias))

    if isinstance(item, dict):
        for name, child_spec in item.items():
            return pairs.auto_relationship(name, *process(child_spec))

    return item


def process(spec):
    return queries_disabled(pairs.combine(*(process_item(item) for item in spec)))

from djunc import pairs


def process_item(item):
    if isinstance(item, str):
        return pairs.field(item)
    if isinstance(item, dict):
        for name, child_spec in item.items():
            return pairs.auto_relationship(name, *process(child_spec))
    return item


def process(spec):
    return pairs.combine(*(process_item(item) for item in spec))


def alias(item, aliases):
    """
    Given a spec item and a dictionary of aliases {"old_key_name": "new_key_name"},
    apply `pairs.alias` to the project function from the processed pair.
    """
    return pairs.alias(process_item(item), aliases)

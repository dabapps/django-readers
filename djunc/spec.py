from djunc import pairs


def process_item(item):
    if isinstance(item, str):
        return pairs.field(item)
    return item


def process(spec):
    return pairs.unzip(process_item(item) for item in spec)

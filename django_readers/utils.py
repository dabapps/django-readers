try:
    import zen_queries
except ImportError:
    zen_queries = None


def map_or_apply(obj, fn):
    """
    If the first argument is iterable, map the function across each item in it and
    return the result. If it looks like a queryset or manager, call `.all()` and
    map the function across the result of that. If it's is a single item, just call
    the function on that item and return the result.
    """
    if obj is None:
        return None

    try:
        # Is the object itself iterable?
        return [fn(item) for item in iter(obj)]
    except TypeError:
        try:
            # Does the object have a `.all()` method (is it a manager?)
            return [fn(item) for item in obj.all()]
        except AttributeError:
            # It must be a single object
            return fn(obj)


def none_safe_attrgetter(attr):
    """
    Like operator.attrgetter, but if using a dotted-path style, and any of the
    attributes in the path has a value of None, the whole function short-circuits and
    returns None rather than raising AttributeError when the next part of the dotted
    path tries to grab an attribute off a None.
    """

    def none_safe_get_attr(obj):
        for name in attr.split("."):
            obj = getattr(obj, name)
            if obj is None:
                return None
        return obj

    return none_safe_get_attr


def queries_disabled(pair):
    prepare, project = pair
    decorator = zen_queries.queries_disabled() if zen_queries else lambda fn: fn
    return decorator(prepare), decorator(project)


class SpecVisitor:
    def visit(self, spec):
        return [self.visit_item(item) for item in spec]

    def visit_item(self, item):
        if isinstance(item, str):
            return self.visit_str(item)
        if isinstance(item, dict):
            return self.visit_dict(item)
        if isinstance(item, tuple):
            return self.visit_tuple(item)
        if callable(item):
            return self.visit_callable(item)
        raise ValueError(f"Unexpected item in spec: {item}")

    def visit_str(self, item):
        return item

    def visit_dict(self, item):
        return dict(self.visit_dict_item(key, value) for key, value in item.items())

    def visit_tuple(self, item):
        return item

    def visit_callable(self, item):
        return item

    def visit_dict_item(self, key, value):
        if isinstance(value, str):
            return self.visit_dict_item_str(key, value)
        if isinstance(value, list):
            return self.visit_dict_item_list(key, value)
        if isinstance(value, dict):
            if len(value) != 1:
                raise ValueError("Aliased relationship spec must contain only one key")
            return self.visit_dict_item_dict(key, value)
        if isinstance(value, tuple):
            return self.visit_dict_item_tuple(key, value)
        if callable(value):
            return self.visit_dict_item_callable(key, value)
        raise ValueError(f"Unexpected item in spec: {key}, {value}")

    def visit_dict_item_str(self, key, value):
        return key, self.visit_str(value)

    def visit_dict_item_list(self, key, value):
        return key, self.visit(value)

    def visit_dict_item_dict(self, key, value):
        return key, self.visit_dict(value)

    def visit_dict_item_tuple(self, key, value):
        return key, self.visit_tuple(value)

    def visit_dict_item_callable(self, key, value):
        return key, self.visit_callable(value)

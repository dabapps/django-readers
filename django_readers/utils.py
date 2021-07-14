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

def map_or_apply(obj, fn):
    """
    If the first argument is iterable, map the function across each item in it and
    return the result. If it looks like a queryset or manager, call `.all()` and
    map the function across the result of that. If it's is a single item, just call
    the function on that item and return the result.
    """
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

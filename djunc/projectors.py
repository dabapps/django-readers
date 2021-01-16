from operator import attrgetter


def wrap(key, value_getter):
    def projector(instance):
        return {key: value_getter(instance)}

    return projector


def field(name):
    return wrap(name, attrgetter(name))


def relationship(name, related_projector):
    """
    Given an attribute name and a projector, return a projector which plucks
    the attribute off the instance, figures out whether it represents a single
    object or an iterable/queryset of objects, and applies the given projector
    to the related object or objects.
    """

    def value_getter(instance):
        related = attrgetter(name)(instance)

        # Figure out if we need to project the related object, or iterate over it
        # and project each item.
        try:
            # Is the instance itself iterable?
            return [related_projector(instance) for instance in iter(related)]
        except TypeError:
            try:
                # Does the instance have a `.all()` method (ie is it a queryset?)
                return [related_projector(instance) for instance in related.all()]
            except AttributeError:
                # It must be a single instance
                return related_projector(related)

    return wrap(name, value_getter)


def combine(*projectors):
    """
    Given a list of projectors as *args, return another projector which calls each
    projector in turn and merges the resulting dictionaries.
    """

    def combined(instance):
        result = {}
        for projector in projectors:
            result.update(projector(instance))
        return result

    return combined


def alias(projector, aliases):
    """
    Given a projector and a dictionary of aliases {"old_key_name": "new_key_name"},
    return a projector which replaces the keys in the output of the original projector
    with those provided in the alias map.
    """

    def aliaser(instance):
        projected = projector(instance)
        for old, new in aliases.items():
            projected[new] = projected.pop(old)
        return projected

    return aliaser


def noop(instance):
    return {}

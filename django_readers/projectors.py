from django.core.exceptions import ObjectDoesNotExist
from django_readers.utils import map_or_apply
from operator import attrgetter, methodcaller


def wrap(key, value_getter):
    def projector(instance):
        return {key: value_getter(instance)}

    return projector


def attr(name):
    return wrap(name, attrgetter(name))


def method(name, *args, **kwargs):
    return wrap(name, methodcaller(name, *args, **kwargs))


def relationship(name, related_projector):
    """
    Given an attribute name and a projector, return a projector which plucks
    the attribute off the instance, figures out whether it represents a single
    object or an iterable/queryset of objects, and applies the given projector
    to the related object or objects.
    """

    def value_getter(instance):
        try:
            related = attrgetter(name)(instance)
        except ObjectDoesNotExist:
            return None
        return map_or_apply(related, related_projector)

    return wrap(name, value_getter)


def pk_list(name):
    """
    Given an attribute name (which should be a relationship field), return a
    projector which returns a list of the PK of each item in the relationship (or
    just a single PK if this is a to-one field, but this is an inefficient way of
    doing it).
    """
    return relationship(name, attrgetter("pk"))


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


def alias(alias_or_aliases, projector):
    """
    Given a projector and a dictionary of aliases {"old_key_name": "new_key_name"},
    return a projector which replaces the keys in the output of the original projector
    with those provided in the alias map. As a shortcut, the argument can be a single
    string, in which case this will automatically alias a single-key projector without
    needing to know the key name of key in the dictionary returned from the
    inner projector.
    """

    def aliaser(instance):
        projected = projector(instance)
        if isinstance(alias_or_aliases, str) and len(projected) != 1:
            raise TypeError(
                "A single string can only be used as an alias for projectors "
                "that return a dictionary with a single key. Please use a mapping "
                "to define aliases instead."
            )

        alias_map = (
            {next(iter(projected)): alias_or_aliases}
            if isinstance(alias_or_aliases, str)
            else alias_or_aliases
        )
        for old, new in alias_map.items():
            projected[new] = projected.pop(old)
        return projected

    return aliaser


def noop(instance):
    return {}

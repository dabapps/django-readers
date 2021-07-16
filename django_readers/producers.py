from django.core.exceptions import ObjectDoesNotExist
from django_readers.utils import map_or_apply, none_safe_attrgetter
from operator import attrgetter, methodcaller


def attr(name, *, transform_value=None, transform_value_if_none=False):
    def producer(instance):
        value = none_safe_attrgetter(name)(instance)
        if transform_value and (value is not None or transform_value_if_none):
            value = transform_value(value)
        return value

    return producer


method = methodcaller


def relationship(name, related_projector):
    """
    Given an attribute name and a projector, return a producer which plucks
    the attribute off the instance, figures out whether it represents a single
    object or an iterable/queryset of objects, and applies the given projector
    to the related object or objects.
    """

    def producer(instance):
        try:
            related = none_safe_attrgetter(name)(instance)
        except ObjectDoesNotExist:
            return None
        return map_or_apply(related, related_projector)

    return producer


def pk_list(name):
    """
    Given an attribute name (which should be a relationship field), return a
    producer which returns a list of the PK of each item in the relationship (or
    just a single PK if this is a to-one field, but this is an inefficient way of
    doing it).
    """
    return relationship(name, attrgetter("pk"))

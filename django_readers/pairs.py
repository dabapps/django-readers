from django.db.models import Count, Sum
from django_readers import producers, projectors, qs
from operator import itemgetter


def producer_to_projector(name, pair):
    prepare, produce = pair
    return prepare, projectors.producer_to_projector(name, produce)


def field(name, *, transform_value=None, transform_value_if_none=False):
    return qs.include_fields(name), producers.attr(
        name,
        transform_value=transform_value,
        transform_value_if_none=transform_value_if_none,
    )


def combine(*pairs):
    """
    Given a list of pairs as *args, return a pair which pipes together the prepare
    function from each pair, and combines the project function from each pair.
    """
    prepare_fns, project_fns = zip(*pairs)
    return qs.pipe(*prepare_fns), projectors.combine(*project_fns)


discard_projector = itemgetter(0)


discard_queryset_function = itemgetter(1)


def field_display(name):
    """
    Works with Django's get_FOO_display mechanism for fields with choices set. Given
    the name of a field, returns a producer that calls get_<name>_display.
    """
    return qs.include_fields(name), producers.method(f"get_{name}_display")


def annotate(*args, **kwargs):
    """
    Return a pair that adds an annotation to the queryset and produces the value. Like
    the annotate method on QuerySet, this can take either a positional argument or a
    keyword argument. Unlike the annotate method, this can only handle a single
    annotation at a time. Also, this function can optionally take transform_value and
    tranform_value_if_none arguments, which are passed to the producer.
    """
    transform_value = kwargs.pop("transform_value", None)
    transform_value_if_none = kwargs.pop("transform_value_if_none", False)

    if len(args) + len(kwargs) != 1:
        raise ValueError("Only a single annotation is supported")

    annotations = kwargs or {args[0].default_alias: args[0]}
    name, annotation = next(iter(annotations.items()))

    return (
        qs.annotate(**{name: annotation}),
        producers.attr(
            name,
            transform_value=transform_value,
            transform_value_if_none=transform_value_if_none,
        ),
    )


def count(name, *args, **kwargs):
    return annotate(
        **{f"{name}_count": Count(name, *args, **kwargs)},
    )


def has(name, *args, **kwargs):
    return annotate(
        **{f"{name}_count": Count(name, *args, **kwargs)}, transform_value=bool
    )


def sum(name, *args, **kwargs):
    return annotate(
        **{f"{name}_sum": Sum(name, *args, **kwargs)},
    )


def filter(*args, **kwargs):
    return qs.filter(*args, **kwargs), projectors.noop


def exclude(*args, **kwargs):
    return qs.exclude(*args, **kwargs), projectors.noop


def order_by(*args, **kwargs):
    return qs.order_by(*args, **kwargs), projectors.noop


"""
Below are pair functions which return the various queryset functions that prefetch
relationships of various types, and then produce those related objects.

There are functions for forward, reverse or many-to-many relationships, and then
a `relationship` function which selects the correct one by introspecting the
model. It shouldn't usually be necessary to use the manual functions unless you're
doing something weird, like providing a custom queryset.
"""


def forward_relationship(name, related_queryset, relationship_pair, to_attr=None):
    prepare_related_queryset, project_relationship = relationship_pair
    prepare = qs.prefetch_forward_relationship(
        name, related_queryset, prepare_related_queryset, to_attr
    )
    return prepare, producers.relationship(to_attr or name, project_relationship)


def reverse_relationship(
    name, related_name, related_queryset, relationship_pair, to_attr=None
):
    prepare_related_queryset, project_relationship = relationship_pair
    prepare = qs.prefetch_reverse_relationship(
        name, related_name, related_queryset, prepare_related_queryset, to_attr
    )
    return prepare, producers.relationship(to_attr or name, project_relationship)


def many_to_many_relationship(name, related_queryset, relationship_pair, to_attr=None):
    prepare_related_queryset, project_relationship = relationship_pair
    prepare = qs.prefetch_many_to_many_relationship(
        name, related_queryset, prepare_related_queryset, to_attr
    )
    return prepare, producers.relationship(to_attr or name, project_relationship)


def relationship(name, relationship_pair, to_attr=None):
    prepare_related_queryset, project_relationship = relationship_pair
    prepare = qs.auto_prefetch_relationship(name, prepare_related_queryset, to_attr)
    return prepare, producers.relationship(to_attr or name, project_relationship)


def pk_list(name, to_attr=None):
    return (
        qs.auto_prefetch_relationship(name, qs.include_fields("pk"), to_attr=to_attr),
        producers.pk_list(to_attr or name),
    )

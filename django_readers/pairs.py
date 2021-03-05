from django_readers import projectors, qs


def field(name):
    return qs.include_fields(name), projectors.attr(name)


def combine(*pairs):
    """
    Given a list of pairs as *args, return a pair which pipes together the prepare
    function from each pair, and combines the project function from each pair.
    """
    prepare_fns, project_fns = zip(*pairs)
    return qs.pipe(*prepare_fns), projectors.combine(*project_fns)


def alias(alias_or_aliases, pair):
    prepare, project = pair
    return prepare, projectors.alias(alias_or_aliases, project)


def prepare_only(prepare):
    return prepare, projectors.noop


def project_only(project):
    return qs.noop, project


def field_display(name):
    """
    Works with Django's get_FOO_display mechanism for fields with choices set. Given
    the name of a field, calls get_<name>_display, and returns a projector that puts
    the returned value under the key <name>_display.
    """
    return qs.include_fields(name), projectors.alias(
        f"{name}_display", projectors.method(f"get_{name}_display")
    )


def filter(*args, **kwargs):
    return prepare_only(qs.filter(*args, **kwargs))


"""
Below are pair functions which return the various queryset functions that prefetch
relationships of various types, and then project those related objects.

There are functions for forward, reverse or many-to-many relationships, and then
an `auto_relationship` function which selects the correct one by introspecting the
model. It shouldn't usually be necessary to use the manual functions unless you're
doing something weird, like providing a custom queryset.
"""


def forward_relationship(name, related_queryset, relationship_pair, to_attr=None):
    prepare_related_queryset, project_relationship = relationship_pair
    prepare = qs.prefetch_forward_relationship(
        name, related_queryset, prepare_related_queryset, to_attr
    )
    return prepare, projectors.relationship(to_attr or name, project_relationship)


def reverse_relationship(
    name, related_name, related_queryset, relationship_pair, to_attr=None
):
    prepare_related_queryset, project_relationship = relationship_pair
    prepare = qs.prefetch_reverse_relationship(
        name, related_name, related_queryset, prepare_related_queryset, to_attr
    )
    return prepare, projectors.relationship(to_attr or name, project_relationship)


def many_to_many_relationship(name, related_queryset, relationship_pair, to_attr=None):
    prepare_related_queryset, project_relationship = relationship_pair
    prepare = qs.prefetch_many_to_many_relationship(
        name, related_queryset, prepare_related_queryset, to_attr
    )
    return prepare, projectors.relationship(to_attr or name, project_relationship)


def auto_relationship(name, relationship_pair, to_attr=None):
    prepare_related_queryset, project_relationship = relationship_pair
    prepare = qs.auto_prefetch_relationship(name, prepare_related_queryset, to_attr)
    return prepare, projectors.relationship(to_attr or name, project_relationship)


def pk_list(name, to_attr=None):
    return (
        qs.auto_prefetch_relationship(name, qs.include_fields("pk"), to_attr=to_attr),
        projectors.pk_list(to_attr or name),
    )

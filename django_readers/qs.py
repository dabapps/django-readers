from django.db.models import Prefetch, QuerySet
from django.db.models.constants import LOOKUP_SEP
from django.db.models.fields.related_descriptors import (
    ForwardManyToOneDescriptor,
    ForwardOneToOneDescriptor,
    ManyToManyDescriptor,
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
)


def _method_to_function(method):
    """
    Return a function that when called with any arguments will return another
    function that takes a queryset and calls the given queryset method, passing
    the queryset as the `self` parameter and forwarding along the other arguments.
    """

    def make_queryset_function(*args, **kwargs):
        def queryset_function(queryset):
            return method(queryset, *args, **kwargs)

        return queryset_function

    return make_queryset_function


"""
The following functions mirror all the default methods on the base
`QuerySet` that return a new `QuerySet`.
"""
filter = _method_to_function(QuerySet.filter)
all = _method_to_function(QuerySet.all)
exclude = _method_to_function(QuerySet.exclude)
select_related = _method_to_function(QuerySet.select_related)
prefetch_related = _method_to_function(QuerySet.prefetch_related)
order_by = _method_to_function(QuerySet.order_by)
distinct = _method_to_function(QuerySet.distinct)
extra = _method_to_function(QuerySet.extra)
defer = _method_to_function(QuerySet.defer)
only = _method_to_function(QuerySet.only)
using = _method_to_function(QuerySet.using)


def annotate(*args, **kwargs):
    def queryset_function(queryset):
        return include_fields("pk")(queryset.annotate(*args, **kwargs))

    return queryset_function


noop = all()  # a queryset function that does nothing


def include_fields(*fields):
    """
    Returns a queryset function that extends an already-`.only()`d queryset
    with more fields.
    """

    def fields_included(queryset):
        return queryset.only(*queryset.query.deferred_loading[0], *fields)

    return fields_included


def pipe(*fns):
    """
    Given a list of queryset functions as *args, return a new queryset function
    that calls each function in turn, passing the return value of each as the
    argument to the next.
    """

    def piped(queryset):
        for fn in fns:
            queryset = fn(queryset)
        return queryset

    return piped


def select_related_fields(*fields):
    """
    Like select_related, but selects only specific fields from the related objects
    """
    return pipe(
        select_related(*{field.rpartition(LOOKUP_SEP)[0] for field in fields}),
        include_fields(*fields),
    )


"""
The below functions return functions that use `prefetch_related` to efficiently load
related objects. We use `prefetch_related` to load all relationship types because this
means our functions can be recursive - we can apply pairs to the related querysets, all
the way down the tree.

There are six types of relationship from the point of view of the "main" object:

  * Forward one-to-one - a OneToOneField on the main object
  * Reverse one-to-one - a OneToOneField on the related object
  * Forward many-to-one - a ForeignKey on the main object
  * Reverse many-to-one - a ForeignKey on the related object
  * Forward many-to-many - a ManyToManyField on the main object
  * Reverse many-to-many - a ManyToManyField on the related object

ManyToManyFields are symmetrical, so the latter two collapse down to the same thing.
The forward one-to-one and many-to-one are identical as they both relate a single
related object to the main object. The reverse one-to-one and many-to-one are identical
except the former relates the main object to a single related object, and the latter
relates the main object to many related objects. Because the `projectors.relationship`
function already infers whether to iterate or project a single instance, we can collapse
these two functions into one as well.

There are functions for forward, reverse or many-to-many relationships, and then
an "auto" function which selects the correct relationship type by introspecting the
model. It shouldn't usually be necessary to use the manual functions unless you're
doing something weird, like providing a custom queryset.
"""


def prefetch_forward_relationship(
    name, related_queryset, prepare_related_queryset=noop, to_attr=None
):
    """
    Efficiently prefetch a forward relationship: one where the field on the "parent"
    queryset is a concrete field. We need to include this field in the query.
    """
    return pipe(
        include_fields(name),
        prefetch_related(
            Prefetch(
                name,
                pipe(
                    include_fields("pk"),
                    prepare_related_queryset,
                )(related_queryset),
                to_attr,
            )
        ),
    )


def prefetch_reverse_relationship(
    name, related_name, related_queryset, prepare_related_queryset=noop, to_attr=None
):
    """
    Efficiently prefetch a reverse relationship: one where the field on the "parent"
    queryset is not a concrete field - a foreign key from another object points at it.
    We need the `related_name` (ie the name of the relationship field on the related
    object) so that we can include this field in the query for the related objects,
    as Django will need it when it comes to stitch them together when the query
    is executed.
    """
    return pipe(
        include_fields("pk"),
        prefetch_related(
            Prefetch(
                name,
                pipe(
                    include_fields(related_name),
                    prepare_related_queryset,
                )(related_queryset),
                to_attr,
            )
        ),
    )


def prefetch_many_to_many_relationship(
    name, related_queryset, prepare_related_queryset=noop, to_attr=None
):
    """
    For many-to-many relationships, both sides of the relationship are non-concrete,
    so we don't need to do anything special with including fields. They are also
    symmetrical, so no need to differentiate between forward and reverse direction.
    """
    return pipe(
        include_fields("pk"),
        prefetch_related(
            Prefetch(
                name,
                pipe(
                    include_fields("pk"),
                    prepare_related_queryset,
                )(related_queryset),
                to_attr,
            )
        ),
    )


def auto_prefetch_relationship(name, prepare_related_queryset=noop, to_attr=None):
    """
    Given the name of a relationship, return a prepare function which introspects the
    relationship to discover its type and generates the correct set of
    `select_related` and `include_fields` calls to apply to efficiently load it. A
    queryset function may also be passed, which will be applied to the related
    queryset.

    This is by far the most complicated part of the entire library. The reason
    it's so complicated is because Django's related object descriptors are
    inconsistent: each type has a slightly different way of accessing its related
    queryset, the name of the field on the other side of the relationship, etc.
    """

    def prepare(queryset):
        related_descriptor = getattr(queryset.model, name)

        if type(related_descriptor) in (
            ForwardOneToOneDescriptor,
            ForwardManyToOneDescriptor,
        ):
            return prefetch_forward_relationship(
                name,
                related_descriptor.field.related_model.objects.all(),
                prepare_related_queryset,
                to_attr,
            )(queryset)
        if type(related_descriptor) is ReverseOneToOneDescriptor:
            return prefetch_reverse_relationship(
                name,
                related_descriptor.related.field.name,
                related_descriptor.related.field.model.objects.all(),
                prepare_related_queryset,
                to_attr,
            )(queryset)
        if type(related_descriptor) is ReverseManyToOneDescriptor:
            return prefetch_reverse_relationship(
                name,
                related_descriptor.rel.field.name,
                related_descriptor.rel.field.model.objects.all(),
                prepare_related_queryset,
                to_attr,
            )(queryset)
        if type(related_descriptor) is ManyToManyDescriptor:
            field = related_descriptor.rel.field
            if related_descriptor.reverse:
                related_queryset = field.model.objects.all()
            else:
                related_queryset = field.target_field.model.objects.all()

            return prefetch_many_to_many_relationship(
                name,
                related_queryset,
                prepare_related_queryset,
                to_attr,
            )(queryset)

    return prepare

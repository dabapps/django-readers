from django.db.models import Prefetch, QuerySet


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
annotate = _method_to_function(QuerySet.annotate)
order_by = _method_to_function(QuerySet.order_by)
distinct = _method_to_function(QuerySet.distinct)
extra = _method_to_function(QuerySet.extra)
defer = _method_to_function(QuerySet.defer)
only = _method_to_function(QuerySet.only)
using = _method_to_function(QuerySet.using)


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
        select_related(*{field.rpartition("__")[0] for field in fields}),
        include_fields(*fields),
    )


def prefetch_forward_relationship(name, related_queryset):
    """
    Efficiently prefetch a forward relationship: one where the field on the "parent"
    queryset is a concrete field. We need to include this field in the query.
    """
    return pipe(
        include_fields(name),
        prefetch_related(Prefetch(name, related_queryset)),
    )


def prefetch_reverse_relationship(name, related_name, related_queryset):
    """
    Efficiently prefetch a reverse relationship: one where the field on the "parent"
    queryset is not a concrete field - a foreign key from another object points at it.
    We need the `related_name` (ie the name of the relationship field on the related
    object) so that we can include this field in the query for the related objects,
    as Django will need it when it comes to stitch them together when the query
    is executed.
    """
    return prefetch_related(
        Prefetch(
            name,
            include_fields(related_name)(related_queryset),
        )
    )


def prefetch_many_to_many_relationship(name, related_queryset):
    """
    For many-to-many relationships, both sides of the relationship are non-concrete,
    so we don't need to do anything special with including fields. They are also
    symmetrical, so no need to differentiate between forward and reverse direction.
    """
    return prefetch_related(Prefetch(name, related_queryset))

from django.db.models import Prefetch, QuerySet


def _method_to_function(method):
    def make_function(*args, **kwargs):
        def function(queryset):
            return method(queryset, *args, **kwargs)

        return function

    return make_function


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
    def fields_included(queryset):
        """ Extend an already-`.only()`d queryset with more fields """
        return queryset.only(*queryset.query.deferred_loading[0], *fields)

    return fields_included


def pipe(*fns):
    def piped(queryset):
        for fn in fns:
            queryset = fn(queryset)
        return queryset

    return piped


def prefetch_forward_relationship(name, related_queryset):
    """
    Efficiently prefetch a forward relationship (ie one where the field on the "parent"
    queryset is a concrete field). We need to include this field in the query.
    """
    return pipe(
        include_fields(name),
        prefetch_related(Prefetch(name, related_queryset)),
    )


def prefetch_reverse_relationship(name, related_name, related_queryset):
    """
    Efficiently prefetch a reverse relationship (ie one where the field on the "parent"
    queryset is not a concrete field - a foreign key from another object points at it).
    We need the `related_name` (ie the name of the relationship field on the related
    object) so that we can include this field in the query for the related objects,
    as Django will need it when it comes to stitch them together.
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

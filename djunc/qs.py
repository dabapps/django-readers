from django.db.models import Prefetch, QuerySet


def method_to_function(method):
    def make_queryset_function(*args, **kwargs):
        def queryset_function(queryset):
            return method(queryset, *args, **kwargs)

        return queryset_function

    return make_queryset_function


filter = method_to_function(QuerySet.filter)
all = noop = method_to_function(QuerySet.all)
exclude = method_to_function(QuerySet.exclude)
select_related = method_to_function(QuerySet.select_related)
prefetch_related = method_to_function(QuerySet.prefetch_related)
annotate = method_to_function(QuerySet.annotate)
order_by = method_to_function(QuerySet.order_by)
distinct = method_to_function(QuerySet.distinct)
extra = method_to_function(QuerySet.extra)
defer = method_to_function(QuerySet.defer)
only = method_to_function(QuerySet.only)
using = method_to_function(QuerySet.using)


def include_fields(*fields):
    def queryset_function(queryset):
        """ Extend an already-`.only()`d queryset with more fields """
        return queryset.only(*queryset.query.deferred_loading[0], *fields)

    return queryset_function


def pipe(*fns):
    def queryset_function(queryset):
        for fn in fns:
            queryset = fn(queryset)
        return queryset

    return queryset_function


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

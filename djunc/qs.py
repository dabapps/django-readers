from django.db.models import QuerySet


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

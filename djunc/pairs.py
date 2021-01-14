from django.db.models import Prefetch
from djunc import projectors, qs


def field(name):
    return qs.include_fields(name), projectors.field(name)


def unzip(pairs):
    prepare_fns, project_fns = zip(*pairs)
    return qs.pipe(*prepare_fns), projectors.compose(*project_fns)


def relationship(name, prepare_and_project_relationship):
    prepare_related_queryset, project_relationship = prepare_and_project_relationship

    def queryset_function(queryset):
        related_field = queryset.model._meta.get_field(name)
        related_queryset = related_field.related_model.objects.all()
        related_queryset = prepare_related_queryset(related_queryset)
        prepare_main_queryset = qs.pipe(
            qs.include_fields(name),
            qs.prefetch_related(Prefetch(name, related_queryset)),
        )
        return prepare_main_queryset(queryset)

    projector = projectors.relationship(name, project_relationship)
    return queryset_function, projector

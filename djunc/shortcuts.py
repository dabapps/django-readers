from django import shortcuts as django_shortcuts
from djunc import specs


def apply_spec(spec, queryset_or_model_or_manager, *, many, raise_404=False):
    prepare, project = specs.process(spec)
    queryset = prepare(django_shortcuts._get_queryset(queryset_or_model_or_manager))
    if many:
        if raise_404:
            items = django_shortcuts.get_list_or_404(queryset)
        else:
            items = list(queryset)
        return [project(item) for item in items]
    else:
        if raise_404:
            item = django_shortcuts.get_object_or_404(queryset)
        else:
            item = queryset.get()
        return project(item)

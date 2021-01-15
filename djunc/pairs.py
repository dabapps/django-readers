from django.db.models import Prefetch
from djunc import projectors, qs


def field(name):
    return qs.include_fields(name), projectors.field(name)


def unzip(pairs):
    prepare_fns, project_fns = zip(*pairs)
    return qs.pipe(*prepare_fns), projectors.compose(*project_fns)


def reverse_many_to_one_relationship(
    name, related_name, related_queryset, relationship_pair
):
    prepare_related_queryset, project_relationship = relationship_pair

    queryset_function = qs.prefetch_reverse_relationship(
        name, related_name, prepare_related_queryset(related_queryset)
    )

    projector = projectors.relationship(name, project_relationship, many=True)
    return queryset_function, projector


def forward_many_to_one_relationship(name, related_queryset, relationship_pair):
    prepare_related_queryset, project_relationship = relationship_pair

    queryset_function = qs.prefetch_forward_relationship(
        name, prepare_related_queryset(related_queryset)
    )

    projector = projectors.relationship(name, project_relationship, many=False)
    return queryset_function, projector


def forward_one_to_one_relationship(name, related_queryset, relationship_pair):
    prepare_related_queryset, project_relationship = relationship_pair

    queryset_function = qs.prefetch_forward_relationship(
        name, prepare_related_queryset(related_queryset)
    )

    projector = projectors.relationship(name, project_relationship, many=False)
    return queryset_function, projector


def reverse_one_to_one_relationship(
    name, related_name, related_queryset, relationship_pair
):
    prepare_related_queryset, project_relationship = relationship_pair

    queryset_function = qs.prefetch_reverse_relationship(
        name, related_name, prepare_related_queryset(related_queryset)
    )

    projector = projectors.relationship(name, project_relationship, many=False)
    return queryset_function, projector


def many_to_many_relationship(name, related_queryset, relationship_pair):
    prepare_related_queryset, project_relationship = relationship_pair

    queryset_function = qs.prefetch_many_to_many_relationship(
        name, prepare_related_queryset(related_queryset)
    )

    projector = projectors.relationship(name, project_relationship, many=True)
    return queryset_function, projector

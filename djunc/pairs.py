from django.db.models.fields.related_descriptors import (
    ForwardManyToOneDescriptor,
    ForwardOneToOneDescriptor,
    ManyToManyDescriptor,
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
)
from djunc import projectors, qs


def field(name):
    return qs.include_fields(name), projectors.field(name)


def unzip(pairs):
    prepare_fns, project_fns = zip(*pairs)
    return qs.pipe(*prepare_fns), projectors.compose(*project_fns)


"""
Below are functions which return pairs that use `prefetch_related` to efficiently load
related objects, and then project those related objects. We use `prefetch_related` to
load all relationship types because this means our functions can be recursive - we
can apply pairs to the related querysets, all the way down the tree.

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
relates the main object to many related objects. Because the projectors.relationship
function already infers whether to iterate or project a single instance, we can collapse
these two functions into one as well.

There are functions for forward, reverse or many-to-many relationships, and then
an `auto_relationship` function which selects the correct one by introspecting the
model.
"""


def forward_relationship(
    name, related_queryset, prepare_related_queryset, project_relationship
):
    related_queryset = prepare_related_queryset(related_queryset)
    queryset_function = qs.prefetch_forward_relationship(name, related_queryset)
    return queryset_function, projectors.relationship(name, project_relationship)


def reverse_relationship(
    name, related_name, related_queryset, prepare_related_queryset, project_relationship
):
    related_queryset = prepare_related_queryset(related_queryset)
    queryset_function = qs.prefetch_reverse_relationship(
        name, related_name, related_queryset
    )
    return queryset_function, projectors.relationship(name, project_relationship)


def many_to_many_relationship(
    name, related_queryset, prepare_related_queryset, project_relationship
):
    related_queryset = prepare_related_queryset(related_queryset)
    queryset_function = qs.prefetch_many_to_many_relationship(name, related_queryset)
    return queryset_function, projectors.relationship(name, project_relationship)


def auto_relationship(name, prepare_related_queryset, project_relationship):
    def queryset_function(queryset):
        related_descriptor = getattr(queryset.model, name)

        if type(related_descriptor) in (
            ForwardOneToOneDescriptor,
            ForwardManyToOneDescriptor,
        ):
            return qs.prefetch_forward_relationship(
                name,
                prepare_related_queryset(
                    related_descriptor.field.related_model.objects.all()
                ),
            )(queryset)
        if type(related_descriptor) is ReverseOneToOneDescriptor:
            return qs.prefetch_reverse_relationship(
                name,
                related_descriptor.related.field.name,
                prepare_related_queryset(
                    related_descriptor.related.field.model.objects.all()
                ),
            )(queryset)
        if type(related_descriptor) is ReverseManyToOneDescriptor:
            return qs.prefetch_reverse_relationship(
                name,
                related_descriptor.rel.field.name,
                prepare_related_queryset(
                    related_descriptor.rel.field.model.objects.all()
                ),
            )(queryset)
        if type(related_descriptor) is ManyToManyDescriptor:
            field = related_descriptor.rel.field
            if related_descriptor.reverse:
                related_queryset = field.model.objects.all()
            else:
                related_queryset = field.target_field.model.objects.all()

            return qs.prefetch_many_to_many_relationship(
                name,
                prepare_related_queryset(related_queryset),
            )(queryset)

    return queryset_function, projectors.relationship(name, project_relationship)

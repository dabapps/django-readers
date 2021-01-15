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
relates the main object to many related objects.

There is a function for manually specifying each of these relationship types, and then
an `auto_relationship` function which selects the correct one by introspecting the
relationships.
"""


def _forward_relationship(name, related_queryset, relationship_pair):
    prepare_related_queryset, project_relationship = relationship_pair
    related_queryset = prepare_related_queryset(related_queryset)
    queryset_function = qs.prefetch_forward_relationship(name, related_queryset)
    projector = projectors.relationship(name, project_relationship, many=False)
    return queryset_function, projector


def _make_reverse_relationship(many):
    def reverse_relationship(name, related_name, related_queryset, relationship_pair):
        prepare_related_queryset, project_relationship = relationship_pair
        related_queryset = prepare_related_queryset(related_queryset)
        queryset_function = qs.prefetch_reverse_relationship(
            name, related_name, related_queryset
        )
        projector = projectors.relationship(name, project_relationship, many=many)
        return queryset_function, projector

    return reverse_relationship


forward_one_to_one_relationship = _forward_relationship
forward_many_to_one_relationship = _forward_relationship
reverse_one_to_one_relationship = _make_reverse_relationship(many=False)
reverse_many_to_one_relationship = _make_reverse_relationship(many=True)


def many_to_many_relationship(name, related_queryset, relationship_pair):
    prepare_related_queryset, project_relationship = relationship_pair
    related_queryset = prepare_related_queryset(related_queryset)
    queryset_function = qs.prefetch_many_to_many_relationship(name, related_queryset)
    projector = projectors.relationship(name, project_relationship, many=True)
    return queryset_function, projector


def auto_relationship(name, relationship_pair):
    inferred_projector = None

    def queryset_function(queryset):
        nonlocal inferred_projector
        inferred_queryset_function = None

        related_descriptor = getattr(queryset.model, name)

        if type(related_descriptor) is ForwardOneToOneDescriptor:
            (
                inferred_queryset_function,
                inferred_projector,
            ) = forward_one_to_one_relationship(
                name,
                related_descriptor.field.related_model.objects.all(),
                relationship_pair,
            )
        if type(related_descriptor) is ForwardManyToOneDescriptor:
            (
                inferred_queryset_function,
                inferred_projector,
            ) = forward_many_to_one_relationship(
                name,
                related_descriptor.field.related_model.objects.all(),
                relationship_pair,
            )
        if type(related_descriptor) is ReverseOneToOneDescriptor:
            (
                inferred_queryset_function,
                inferred_projector,
            ) = reverse_one_to_one_relationship(
                name,
                related_descriptor.related.field.name,
                related_descriptor.related.field.model.objects.all(),
                relationship_pair,
            )
        if type(related_descriptor) is ReverseManyToOneDescriptor:
            (
                inferred_queryset_function,
                inferred_projector,
            ) = reverse_many_to_one_relationship(
                name,
                related_descriptor.rel.field.name,
                related_descriptor.rel.field.model.objects.all(),
                relationship_pair,
            )
        if type(related_descriptor) is ManyToManyDescriptor:
            field = related_descriptor.rel.field
            if related_descriptor.reverse:
                related_queryset = field.model.objects.all()
            else:
                related_queryset = field.target_field.model.objects.all()
            (
                inferred_queryset_function,
                inferred_projector,
            ) = many_to_many_relationship(
                name,
                related_queryset,
                relationship_pair,
            )
        return inferred_queryset_function(queryset)

    def projector(instance):
        return inferred_projector(instance)

    return queryset_function, projector

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


def combine(*pairs):
    """
    Given a list of pairs as *args, return a pair which pipes together the prepare
    function from each pair, and combines the project function from each pair.
    """
    prepare_fns, project_fns = zip(*pairs)
    return qs.pipe(*prepare_fns), projectors.combine(*project_fns)


def alias(alias_or_aliases, pair):
    prepare, project = pair
    return prepare, projectors.alias(alias_or_aliases, project)


def prepare_only(prepare):
    return prepare, projectors.noop


def project_only(project):
    return qs.noop, project


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
relates the main object to many related objects. Because the `projectors.relationship`
function already infers whether to iterate or project a single instance, we can collapse
these two functions into one as well.

There are functions for forward, reverse or many-to-many relationships, and then
an `auto_relationship` function which selects the correct one by introspecting the
model. It shouldn't usually be necessary to use the manual functions unless you're
doing something weird, like providing a custom queryset.
"""


def forward_relationship(name, related_queryset, relationship_pair):
    prepare_related_queryset, project_relationship = relationship_pair
    related_queryset = prepare_related_queryset(related_queryset)
    prepare = qs.prefetch_forward_relationship(name, related_queryset)
    return prepare, projectors.relationship(name, project_relationship)


def reverse_relationship(name, related_name, related_queryset, relationship_pair):
    prepare_related_queryset, project_relationship = relationship_pair
    related_queryset = prepare_related_queryset(related_queryset)
    prepare = qs.prefetch_reverse_relationship(name, related_name, related_queryset)
    return prepare, projectors.relationship(name, project_relationship)


def many_to_many_relationship(name, related_queryset, relationship_pair):
    prepare_related_queryset, project_relationship = relationship_pair
    related_queryset = prepare_related_queryset(related_queryset)
    prepare = qs.prefetch_many_to_many_relationship(name, related_queryset)
    return prepare, projectors.relationship(name, project_relationship)


def auto_relationship(name, relationship_pair):
    """
    Given the name of a relationship, return a prepare function which introspects the
    relationship to discover its type and generates the correct set of
    `select_related` and `include_fields` calls to apply to efficiently load it,
    and apply the provided prepare and project functions to the relationship.

    This is by far the most complicated part of the entire library. The reason
    it's so complicated is because Django's related object descriptors are
    inconsistent: each type has a slightly different way of accessing its related
    queryset, the name of the field on the other side of the relationship, etc.
    """
    prepare_related_queryset, project_relationship = relationship_pair

    def prepare(queryset):
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

    return prepare, projectors.relationship(name, project_relationship)

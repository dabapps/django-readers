from operator import attrgetter


def wrap(key, value_getter):
    def projector(instance):
        return {key: value_getter(instance)}

    return projector


def field(name):
    return wrap(name, attrgetter(name))


def relationship(name, related_projector, many=False):
    def value_getter(instance):
        related = attrgetter(name)(instance)

        if many:
            return [related_projector(instance) for instance in related.all()]
        else:
            return related_projector(related)

    return wrap(name, value_getter)


def compose(*projectors):
    def composed(instance):
        result = {}
        for projector in projectors:
            result.update(projector(instance))
        return result

    return composed


def alias(projector, aliases):
    def aliaser(instance):
        projected = projector(instance)
        for old, new in aliases.items():
            projected[new] = projected.pop(old)
        return projected

    return aliaser

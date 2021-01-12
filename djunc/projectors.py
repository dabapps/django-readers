from operator import attrgetter


def wrap(key, value_getter):
    def projector(instance):
        return {key: value_getter(instance)}

    return projector


def field(name):
    return wrap(name, attrgetter(name))


def relationship(name, related_projector, many=False):
    def projector(instance):
        related = attrgetter(name)(instance)

        if many:
            value = [related_projector(instance) for instance in related.all()]
        else:
            value = related_projector(related)

        return {name: value}

    return projector


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

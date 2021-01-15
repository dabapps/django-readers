from operator import attrgetter


def wrap(key, value_getter):
    def projector(instance):
        return {key: value_getter(instance)}

    return projector


def field(name):
    return wrap(name, attrgetter(name))


def relationship(name, related_projector):
    def value_getter(instance):
        related = attrgetter(name)(instance)

        # Figure out if we need to project the related object, or iterate over it
        # and project each item.
        try:
            # Is the instance itself iterable?
            return [related_projector(instance) for instance in iter(related)]
        except TypeError:
            try:
                # Does the instance have a `.all()` method (ie is it a queryset?)
                return [related_projector(instance) for instance in related.all()]
            except AttributeError:
                # It must be a single instance
                return related_projector(related)

    return wrap(name, value_getter)


def combine(*projectors):
    def combined(instance):
        result = {}
        for projector in projectors:
            result.update(projector(instance))
        return result

    return combined


def alias(projector, aliases):
    def aliaser(instance):
        projected = projector(instance)
        for old, new in aliases.items():
            projected[new] = projected.pop(old)
        return projected

    return aliaser

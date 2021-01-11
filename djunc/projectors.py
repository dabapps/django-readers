import operator


def field(name, value_getter=None):
    value_getter = value_getter or operator.attrgetter(name)

    def projector(instance):
        return {name: value_getter(instance)}

    return projector


def compose(*projectors):
    def composed(instance):
        result = {}
        for projector in projectors:
            result.update(projector(instance))
        return result

    return composed

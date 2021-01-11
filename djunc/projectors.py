import operator


def wrap(name, value_getter):
    def projector(instance):
        return {name: value_getter(instance)}

    return projector


def field(name):
    return wrap(name, operator.attrgetter(name))


def compose(*projectors):
    def composed(instance):
        result = {}
        for projector in projectors:
            result.update(projector(instance))
        return result

    return composed

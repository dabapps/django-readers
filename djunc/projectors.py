def field(name):
    def projector(instance):
        return {name: getattr(instance, name)}

    return projector


def compose(*projectors):
    def composed(instance):
        result = {}
        for projector in projectors:
            result.update(projector(instance))
        return result

    return composed

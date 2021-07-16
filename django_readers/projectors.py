def producer_to_projector(key, producer):
    def projector(instance):
        return {key: producer(instance)}

    return projector


def combine(*projectors):
    """
    Given a list of projectors as *args, return another projector which calls each
    projector in turn and merges the resulting dictionaries.
    """

    def combined(instance):
        result = {}
        for projector in projectors:
            projection = projector(instance)
            if not isinstance(projection, dict):
                raise TypeError(f"Projector {projector} did not return a dictionary")
            result.update(projection)
        return result

    return combined


def noop(instance):
    return {}

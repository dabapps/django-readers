from djunc import projectors, qs


def field(name):
    return qs.include_fields(name), projectors.field(name)


def process(spec):
    prepare_fns, project_fns = zip(*spec)
    return qs.pipe(*prepare_fns), projectors.compose(*project_fns)

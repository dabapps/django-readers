from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
from django_readers import specs


class ProjectionSerializer:
    def __init__(self, data=None, many=False, context=None):
        self.many = many
        self._data = data
        self.context = context

    @property
    def data(self):
        project = self.context["view"].project
        if self.many:
            return [project(item) for item in self._data]
        return project(self._data)


class SpecMixin:
    spec = None

    def get_spec(self):
        if self.spec is None:
            raise ImproperlyConfigured("SpecMixin requires spec or get_spec")
        return self.spec

    def get_reader_pair(self):
        return specs.process(self.get_spec())

    @cached_property
    def reader_pair(self):
        return self.get_reader_pair()

    @property
    def prepare(self):
        return self.reader_pair[0]

    @property
    def project(self):
        return self.reader_pair[1]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.prepare(queryset)

    def get_serializer_class(self):
        return ProjectionSerializer

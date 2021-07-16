from django.test import TestCase
from django_readers import producers, projectors
from tests.models import Widget


class WrapProducerTestCase(TestCase):
    def test_producer_to_projector(self):
        widget = Widget(name="test", other="other")

        def produce_name(instance):
            return instance.name

        project = projectors.producer_to_projector("name", produce_name)
        result = project(widget)
        self.assertEqual(result, {"name": "test"})


class CombineTestCase(TestCase):
    def test_combine(self):
        widget = Widget.objects.create(name="test", other="other")
        project = projectors.combine(
            projectors.producer_to_projector("name", producers.attr("name")),
            projectors.producer_to_projector("other", producers.attr("other")),
        )
        result = project(widget)
        self.assertEqual(result, {"name": "test", "other": "other"})

    def test_combined_error_if_dictionary_not_returned(self):
        widget = Widget.objects.create(name="test", other="other")
        project = projectors.combine(
            projectors.producer_to_projector("name", producers.attr("name")),
            producers.attr("other"),
        )
        with self.assertRaises(TypeError):
            project(widget)


class NoOpTestCase(TestCase):
    def test_noop(self):
        widget = Widget.objects.create(name="test")
        project = projectors.noop
        result = project(widget)
        self.assertEqual(result, {})

from django.http import Http404
from django.test import TestCase
from djunc.shortcuts import apply_spec
from tests.models import Widget


class ApplySpecTestCase(TestCase):
    def test_single(self):
        widget = Widget.objects.create(name="test widget", other="test other")
        spec = ["id", "name", "other"]
        result = apply_spec(spec, Widget, many=False)
        self.assertEqual(
            result,
            {
                "id": widget.id,
                "name": "test widget",
                "other": "test other",
            },
        )

    def test_single_with_missing_object(self):
        spec = ["id", "name", "other"]
        with self.assertRaises(Widget.DoesNotExist):
            apply_spec(spec, Widget, many=False)

    def test_many(self):
        widget_1 = Widget.objects.create(name="test widget 1", other="test other 1")
        widget_2 = Widget.objects.create(name="test widget 2", other="test other 2")
        spec = ["id", "name", "other"]
        result = apply_spec(spec, Widget, many=True)
        self.assertEqual(
            result,
            [
                {
                    "id": widget_1.id,
                    "name": "test widget 1",
                    "other": "test other 1",
                },
                {
                    "id": widget_2.id,
                    "name": "test widget 2",
                    "other": "test other 2",
                },
            ],
        )

    def test_many_with_empty_list(self):
        spec = ["id", "name", "other"]
        result = apply_spec(spec, Widget, many=True)
        self.assertEqual(result, [])

    def test_raise_404_single(self):
        widget = Widget.objects.create(name="test widget", other="test other")
        spec = ["id", "name", "other"]
        result = apply_spec(spec, Widget, many=False, raise_404=True)
        self.assertEqual(
            result,
            {
                "id": widget.id,
                "name": "test widget",
                "other": "test other",
            },
        )

    def test_404_single_with_missing_object(self):
        spec = ["id", "name", "other"]
        with self.assertRaises(Http404):
            apply_spec(spec, Widget, many=False, raise_404=True)

    def test_raise_404_many(self):
        widget_1 = Widget.objects.create(name="test widget 1", other="test other 1")
        widget_2 = Widget.objects.create(name="test widget 2", other="test other 2")
        spec = ["id", "name", "other"]
        result = apply_spec(spec, Widget, many=True, raise_404=True)
        self.assertEqual(
            result,
            [
                {
                    "id": widget_1.id,
                    "name": "test widget 1",
                    "other": "test other 1",
                },
                {
                    "id": widget_2.id,
                    "name": "test widget 2",
                    "other": "test other 2",
                },
            ],
        )

    def test_raise_404_many_with_empty_list(self):
        spec = ["id", "name", "other"]
        with self.assertRaises(Http404):
            apply_spec(spec, Widget, many=True, raise_404=True)

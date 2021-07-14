from django.test import TestCase
from django_readers import utils
from tests.models import Widget


class MapOrApplyTestCase(TestCase):
    def test_single_item(self):
        item = Widget(name="test")
        result = utils.map_or_apply(item, lambda item: item.name)
        self.assertEqual(result, "test")

    def test_null_single_item(self):
        item = None
        result = utils.map_or_apply(item, lambda item: item.name)
        self.assertEqual(result, None)

    def test_plain_iterable(self):
        items = [Widget(name="test 1"), Widget(name="test 2")]
        result = utils.map_or_apply(items, lambda item: item.name)
        self.assertEqual(result, ["test 1", "test 2"])

    def test_manager(self):
        Widget.objects.create(name="test 1")
        Widget.objects.create(name="test 2")
        result = utils.map_or_apply(Widget.objects, lambda item: item.name)
        self.assertEqual(result, ["test 1", "test 2"])


class NoneSafeAttrGetterTestCase(TestCase):
    def test_does_not_raise_error_when_attr_is_none(self):
        widget = Widget()
        get_attr = utils.none_safe_attrgetter("owner.name")
        self.assertIsNone(get_attr(widget))

    def test_does_raise_error_when_attr_missing(self):
        widget = Widget()
        get_attr = utils.none_safe_attrgetter("chowner.chame")
        with self.assertRaises(AttributeError):
            get_attr(widget)

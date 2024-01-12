from django.test import TestCase
from django_readers import producers, projectors
from tests.models import Group, Owner, Widget


def title_and_reverse(arg):
    return str(arg).title()[::-1]


class AttrTestCase(TestCase):
    def test_attr(self):
        widget = Widget.objects.create(name="test")
        produce = producers.attr("name")
        result = produce(widget)
        self.assertEqual(result, "test")

    def test_attr_transform_value(self):
        widget = Widget(name="test")
        produce = producers.attr("name", transform_value=title_and_reverse)
        result = produce(widget)
        self.assertEqual(result, "tseT")

    def test_attr_transform_value_if_none(self):
        widget = Widget(name=None)
        produce = producers.attr("name", transform_value=title_and_reverse)
        result = produce(widget)
        self.assertEqual(result, None)

        produce = producers.attr(
            "name",
            transform_value=lambda value: value.upper(),
            transform_value_if_none=True,
        )

        with self.assertRaisesMessage(
            AttributeError, "'NoneType' object has no attribute 'upper'"
        ):
            result = produce(widget)

    def test_dotted_attr_handles_none(self):
        widget = Widget.objects.create(name="test")
        produce = producers.attr("owner.name")
        result = produce(widget)
        self.assertEqual(result, None)


class RelationshipTestCase(TestCase):
    def test_relationship_producer(self):
        widget = Widget.objects.create(
            name="test widget",
            owner=Owner.objects.create(
                name="test owner", group=Group.objects.create(name="test group")
            ),
        )

        produce = producers.relationship(
            "owner",
            projectors.combine(
                projectors.producer_to_projector("name", producers.attr("name")),
                projectors.producer_to_projector(
                    "group",
                    producers.relationship(
                        "group",
                        projectors.producer_to_projector(
                            "name", producers.attr("name")
                        ),
                    ),
                ),
            ),
        )

        result = produce(widget)
        self.assertEqual(
            result,
            {"name": "test owner", "group": {"name": "test group"}},
        )

    def test_nullable(self):
        widget = Widget.objects.create(owner=None)
        produce = producers.relationship(
            "owner", projectors.producer_to_projector("name", producers.attr("name"))
        )
        result = produce(widget)
        self.assertEqual(result, None)

    def test_nullable_one_to_one(self):
        widget = Widget.objects.create()
        produce = producers.relationship(
            "thing", projectors.producer_to_projector("name", producers.attr("name"))
        )
        result = produce(widget)
        self.assertEqual(result, None)

    def test_many_relationships(self):
        group = Group.objects.create(name="test group")
        owner_1 = Owner.objects.create(name="owner 1", group=group)
        owner_2 = Owner.objects.create(name="owner 2", group=group)
        Widget.objects.create(name="widget 1", owner=owner_1)
        Widget.objects.create(name="widget 2", owner=owner_1)
        Widget.objects.create(name="widget 3", owner=owner_2)

        produce = producers.relationship(
            "owner_set",
            projectors.combine(
                projectors.producer_to_projector("name", producers.attr("name")),
                projectors.producer_to_projector(
                    "widget_set",
                    producers.relationship(
                        "widget_set",
                        projectors.producer_to_projector(
                            "name", producers.attr("name")
                        ),
                    ),
                ),
            ),
        )

        result = produce(group)
        self.assertEqual(
            result,
            [
                {
                    "name": "owner 1",
                    "widget_set": [
                        {"name": "widget 1"},
                        {"name": "widget 2"},
                    ],
                },
                {
                    "name": "owner 2",
                    "widget_set": [
                        {"name": "widget 3"},
                    ],
                },
            ],
        )


class MethodTestCase(TestCase):
    def test_method_with_no_arguments(self):
        class Widget:
            def hello(self):
                return "hello!"

        produce = producers.method("hello")
        result = produce(Widget())
        self.assertEqual(result, "hello!")

    def test_method_with_arguments(self):
        class Widget:
            def hello(self, name):
                return f"hello, {name}!"

        produce = producers.method("hello", "tester")
        result = produce(Widget())
        self.assertEqual(result, "hello, tester!")


class PKListTestCase(TestCase):
    def test_pk_list(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner)
        Widget.objects.create(name="test 2", owner=owner)
        Widget.objects.create(name="test 3", owner=owner)

        produce = producers.pk_list("widget_set")
        result = produce(owner)
        self.assertEqual(result, [1, 2, 3])

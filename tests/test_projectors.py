from django.test import TestCase
from django_readers import projectors
from tests.models import Group, Owner, Widget


class ProjectorTestCase(TestCase):
    def test_attr(self):
        widget = Widget.objects.create(name="test")
        project = projectors.attr("name")
        result = project(widget)
        self.assertEqual(result, {"name": "test"})

    def test_combine(self):
        widget = Widget.objects.create(name="test", other="other")
        project = projectors.combine(
            projectors.attr("name"),
            projectors.attr("other"),
        )
        result = project(widget)
        self.assertEqual(result, {"name": "test", "other": "other"})

    def test_noop(self):
        widget = Widget.objects.create(name="test")
        project = projectors.noop
        result = project(widget)
        self.assertEqual(result, {})

    def test_alias(self):
        widget = Widget.objects.create(name="test")
        project = projectors.alias({"name": "new_name"}, projectors.attr("name"))
        result = project(widget)
        self.assertEqual(result, {"new_name": "test"})

    def test_single_alias(self):
        widget = Widget.objects.create(name="test")
        project = projectors.alias("new_name", projectors.attr("name"))
        result = project(widget)
        self.assertEqual(result, {"new_name": "test"})

    def test_single_alias_with_multiple_keys(self):
        widget = Widget.objects.create(name="test")

        def projector(_):
            return {"a": 1, "b": 2}

        project = projectors.alias("aliased", projector)
        with self.assertRaises(TypeError):
            project(widget)


class RelationshipTestCase(TestCase):
    def test_relationship_projector(self):
        widget = Widget.objects.create(
            name="test widget",
            owner=Owner.objects.create(
                name="test owner", group=Group.objects.create(name="test group")
            ),
        )

        project = projectors.combine(
            projectors.attr("name"),
            projectors.relationship(
                "owner",
                projectors.combine(
                    projectors.attr("name"),
                    projectors.relationship("group", projectors.attr("name")),
                ),
            ),
        )

        result = project(widget)
        self.assertEqual(
            result,
            {
                "name": "test widget",
                "owner": {"name": "test owner", "group": {"name": "test group"}},
            },
        )

    def test_nullable(self):
        widget = Widget.objects.create(owner=None)
        project = projectors.relationship("owner", projectors.attr("name"))
        result = project(widget)
        self.assertEqual(result, {"owner": None})

    def test_many_relationships(self):
        group = Group.objects.create(name="test group")
        owner_1 = Owner.objects.create(name="owner 1", group=group)
        owner_2 = Owner.objects.create(name="owner 2", group=group)
        Widget.objects.create(name="widget 1", owner=owner_1)
        Widget.objects.create(name="widget 2", owner=owner_1)
        Widget.objects.create(name="widget 3", owner=owner_2)

        project = projectors.combine(
            projectors.attr("name"),
            projectors.relationship(
                "owner_set",
                projectors.combine(
                    projectors.attr("name"),
                    projectors.relationship("widget_set", projectors.attr("name")),
                ),
            ),
        )

        result = project(group)
        self.assertEqual(
            result,
            {
                "name": "test group",
                "owner_set": [
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
            },
        )


class MethodTestCase(TestCase):
    def test_method_with_no_arguments(self):
        class Widget:
            def hello(self):
                return "hello!"

        project = projectors.method("hello")
        result = project(Widget())
        self.assertEqual(result, {"hello": "hello!"})

    def test_method_with_arguments(self):
        class Widget:
            def hello(self, name):
                return f"hello, {name}!"

        project = projectors.method("hello", "tester")
        result = project(Widget())
        self.assertEqual(result, {"hello": "hello, tester!"})


class PKListTestCase(TestCase):
    def test_pk_list(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner)
        Widget.objects.create(name="test 2", owner=owner)
        Widget.objects.create(name="test 3", owner=owner)

        project = projectors.pk_list("widget_set")

        result = project(owner)

        self.assertEqual(result, {"widget_set": [1, 2, 3]})

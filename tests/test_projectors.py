from django.test import TestCase
from djunc import projectors
from tests.models import Group, Owner, Widget


class ProjectorTestCase(TestCase):
    def test_field(self):
        widget = Widget.objects.create(name="test")
        project = projectors.field("name")
        result = project(widget)
        self.assertEqual(result, {"name": "test"})

    def test_combine(self):
        widget = Widget.objects.create(name="test", other="other")
        project = projectors.combine(
            projectors.field("name"),
            projectors.field("other"),
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
        project = projectors.alias({"name": "new_name"}, projectors.field("name"))
        result = project(widget)
        self.assertEqual(result, {"new_name": "test"})

    def test_single_alias(self):
        widget = Widget.objects.create(name="test")
        project = projectors.alias("new_name", projectors.field("name"))
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
            projectors.field("name"),
            projectors.relationship(
                "owner",
                projectors.combine(
                    projectors.field("name"),
                    projectors.relationship("group", projectors.field("name")),
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

    def test_many_relationships(self):
        group = Group.objects.create(name="test group")
        owner_1 = Owner.objects.create(name="owner 1", group=group)
        owner_2 = Owner.objects.create(name="owner 2", group=group)
        Widget.objects.create(name="widget 1", owner=owner_1)
        Widget.objects.create(name="widget 2", owner=owner_1)
        Widget.objects.create(name="widget 3", owner=owner_2)

        project = projectors.combine(
            projectors.field("name"),
            projectors.relationship(
                "owner_set",
                projectors.combine(
                    projectors.field("name"),
                    projectors.relationship("widget_set", projectors.field("name")),
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

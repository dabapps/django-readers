from django.test import TestCase
from djunc import pairs
from tests.models import Group, Owner, Widget


class PairsTestCase(TestCase):
    def test_fields(self):
        for name in ["first", "second", "third"]:
            Widget.objects.create(name=name, other=f"other-{name}")

        prepare, project = pairs.unzip(
            [
                pairs.field("name"),
                pairs.field("other"),
            ]
        )

        queryset = prepare(Widget.objects.all())
        result = [project(instance) for instance in queryset]

        self.assertEqual(
            result,
            [
                {"name": "first", "other": "other-first"},
                {"name": "second", "other": "other-second"},
                {"name": "third", "other": "other-third"},
            ],
        )

    def test_relationship(self):
        group = Group.objects.create(name="test group")
        owner = Owner.objects.create(name="test owner", group=group)
        Widget.objects.create(name="test widget", owner=owner)

        prepare, project = pairs.unzip(
            [
                pairs.field("name"),
                pairs.forward_many_to_one_relationship(
                    "owner",
                    Owner.objects.all(),
                    pairs.unzip(
                        [
                            pairs.field("name"),
                            pairs.forward_many_to_one_relationship(
                                "group",
                                Group.objects.all(),
                                pairs.unzip([pairs.field("name")]),
                            ),
                        ]
                    ),
                ),
            ]
        )

        with self.assertNumQueries(0):
            queryset = prepare(Widget.objects.all())

        with self.assertNumQueries(3):
            instance = queryset.first()

        with self.assertNumQueries(0):
            result = project(instance)

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

        prepare, project = pairs.unzip(
            [
                pairs.field("name"),
                pairs.reverse_many_to_one_relationship(
                    "owner_set",
                    "group",
                    Owner.objects.all(),
                    pairs.unzip(
                        [
                            pairs.field("name"),
                            pairs.reverse_many_to_one_relationship(
                                "widget_set",
                                "owner",
                                Widget.objects.all(),
                                pairs.unzip(
                                    [
                                        pairs.field("name"),
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
            ]
        )

        with self.assertNumQueries(0):
            queryset = prepare(Group.objects.all())

        with self.assertNumQueries(3):
            instance = queryset.first()

        with self.assertNumQueries(0):
            result = project(instance)

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

    def test_one_to_one_relationship(self):
        widget = Widget.objects.create(name="test widget")
        Thing.objects.create(name="test thing", widget=widget)

        prepare, project = pairs.unzip(
            [
                pairs.field("name"),
                pairs.forward_one_to_one_relationship(
                    "widget",
                    Widget.objects.all(),
                    pairs.unzip(
                        [
                            pairs.field("name"),
                            pairs.reverse_one_to_one_relationship(
                                "thing",
                                "widget",
                                Thing.objects.all(),
                                pairs.unzip([pairs.field("name")]),
                            ),
                        ]
                    ),
                ),
            ]
        )

        with self.assertNumQueries(0):
            queryset = prepare(Thing.objects.all())

        with self.assertNumQueries(3):
            instance = queryset.first()

        with self.assertNumQueries(0):
            result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test thing",
                "widget": {"name": "test widget", "thing": {"name": "test thing"}},
            },
        )

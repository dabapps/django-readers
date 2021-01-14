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
                pairs.relationship(
                    "owner",
                    pairs.unzip(
                        [
                            pairs.field("name"),
                            pairs.relationship(
                                "group",
                                pairs.unzip([pairs.field("name")]),
                            ),
                        ]
                    ),
                ),
            ]
        )

        with self.assertNumQueries(0):
            queryset = prepare(Widget.objects.all())

        instance = queryset.get()

        with self.assertNumQueries(0):
            result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test widget",
                "owner": {"name": "test owner", "group": {"name": "test group"}},
            },
        )

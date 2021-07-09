from django.test import TestCase
from django_readers import specs
from tests.models import Category, Owner, Thing, Widget


class SpecTestCase(TestCase):
    def test_fields(self):
        for name in ["first", "second", "third"]:
            Widget.objects.create(name=name, other=f"other-{name}")

        prepare, project = specs.process(["name", "other"])

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

    def test_relationships(self):
        owner = Owner.objects.create(name="test owner")
        widget = Widget.objects.create(name="test widget", owner=owner)
        category = Category.objects.create(name="test category")
        category.widget_set.add(widget)
        Thing.objects.create(name="test thing", widget=widget)

        prepare, project = specs.process(
            [
                "name",
                {"owner": ["name", {"widget_set": ["name"]}]},
                {"category_set": ["name", {"widget_set": ["name"]}]},
                {"thing": ["name", {"widget": ["name"]}]},
            ]
        )

        with self.assertNumQueries(0):
            queryset = prepare(Widget.objects.all())

        with self.assertNumQueries(7):
            instance = queryset.first()

        with self.assertNumQueries(0):
            result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test widget",
                "owner": {
                    "name": "test owner",
                    "widget_set": [{"name": "test widget"}],
                },
                "category_set": [
                    {"name": "test category", "widget_set": [{"name": "test widget"}]},
                ],
                "thing": {"name": "test thing", "widget": {"name": "test widget"}},
            },
        )

    def test_multiple_relationships_in_single_dict(self):
        # This is a pretty unusual thing to do, but it should work
        owner = Owner.objects.create(name="test owner")
        widget = Widget.objects.create(name="test widget", owner=owner)
        category = Category.objects.create(name="test category")
        category.widget_set.add(widget)
        Thing.objects.create(name="test thing", widget=widget)

        prepare, project = specs.process(
            [
                "name",
                {
                    "owner": ["name", {"widget_set": ["name"]}],
                    "category_set": ["name", {"widget_set": ["name"]}],
                    "thing": ["name", {"widget": ["name"]}],
                },
            ]
        )

        with self.assertNumQueries(0):
            queryset = prepare(Widget.objects.all())

        with self.assertNumQueries(7):
            instance = queryset.first()

        with self.assertNumQueries(0):
            result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test widget",
                "owner": {
                    "name": "test owner",
                    "widget_set": [{"name": "test widget"}],
                },
                "category_set": [
                    {"name": "test category", "widget_set": [{"name": "test widget"}]},
                ],
                "thing": {"name": "test thing", "widget": {"name": "test widget"}},
            },
        )

    def test_alias(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test widget", owner=owner)

        prepare, project = specs.process(
            [
                specs.alias({"name": "name_alias"}, "name"),
                specs.alias(
                    "widgets",
                    {"widget_set": [specs.alias("alias", "name")]},
                ),
            ]
        )

        with self.assertNumQueries(0):
            queryset = prepare(Owner.objects.all())

        with self.assertNumQueries(2):
            instance = queryset.first()

        with self.assertNumQueries(0):
            result = project(instance)

        self.assertEqual(
            result, {"name_alias": "test owner", "widgets": [{"alias": "test widget"}]}
        )

    def test_relationship_function(self):
        Widget.objects.create(
            name="test widget", owner=Owner.objects.create(name="test owner")
        )

        prepare, project = specs.process(
            [
                "name",
                specs.relationship("owner", ["name"], to_attr="owner_attr"),
            ]
        )

        queryset = prepare(Widget.objects.all())
        instance = queryset.first()
        result = project(instance)

        self.assertEqual(
            result,
            {"name": "test widget", "owner_attr": {"name": "test owner"}},
        )

    def test_alias_shortcut(self):
        Widget.objects.create(
            name="test widget", owner=Owner.objects.create(name="test owner")
        )

        some_pair = (lambda qs: qs, lambda instance: {"value": "some value"})

        prepare, project = specs.process(
            [
                {"aliased_name": "name"},
                {
                    "another_name_alias": "name",
                    "alias_for_owner_relationship": {
                        "owner": [
                            {"aliased_owner_name": "name"},
                        ]
                    },
                },
                {"aliased_value_from_pair": some_pair},
            ]
        )

        queryset = prepare(Widget.objects.all())
        instance = queryset.first()
        result = project(instance)

        self.assertEqual(
            result,
            {
                "aliased_name": "test widget",
                "another_name_alias": "test widget",
                "alias_for_owner_relationship": {"aliased_owner_name": "test owner"},
                "aliased_value_from_pair": "some value",
            },
        )

from django.db.models import Count
from django.db.models.functions import Length
from django.test import TestCase
from django_readers import pairs, producers, projectors, qs, utils
from tests.models import Category, Group, Owner, Thing, Widget
from tests.test_producers import title_and_reverse


class PairsTestCase(TestCase):
    def test_fields(self):
        for name in ["first", "second", "third"]:
            Widget.objects.create(name=name, other=f"other-{name}")

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector("other", pairs.field("other")),
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

    def test_transform_value(self):
        Widget.objects.create(name="test", other="other")
        Widget.objects.create(name=None, other=None)

        prepare, project = pairs.combine(
            pairs.producer_to_projector(
                "name", pairs.field("name", transform_value=title_and_reverse)
            ),
            pairs.producer_to_projector(
                "other",
                pairs.field(
                    "other",
                    transform_value=title_and_reverse,
                    transform_value_if_none=True,
                ),
            ),
        )

        queryset = prepare(Widget.objects.all())
        result = [project(instance) for instance in queryset]

        self.assertEqual(
            result,
            [
                {"name": "tseT", "other": "rehtO"},
                {"name": None, "other": "enoN"},
            ],
        )

    def test_forward_many_to_one_relationship(self):
        group = Group.objects.create(name="test group")
        owner = Owner.objects.create(name="test owner", group=group)
        Widget.objects.create(name="test widget", owner=owner)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "owner",
                pairs.forward_relationship(
                    "owner",
                    Owner.objects.all(),
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector(
                            "group",
                            pairs.forward_relationship(
                                "group",
                                Group.objects.all(),
                                pairs.producer_to_projector(
                                    "name", pairs.field("name")
                                ),
                            ),
                        ),
                    ),
                ),
            ),
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

    def test_forward_many_to_one_relationship_with_to_attr(self):
        Widget.objects.create(
            name="test widget",
            owner=Owner.objects.create(name="test owner"),
        )

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "owner_attr",
                pairs.forward_relationship(
                    "owner",
                    Owner.objects.all(),
                    pairs.producer_to_projector("name", pairs.field("name")),
                    to_attr="owner_attr",
                ),
            ),
        )

        instance = prepare(Widget.objects.all()).first()
        result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test widget",
                "owner_attr": {"name": "test owner"},
            },
        )

    def test_reverse_many_to_one_relationship(self):
        group = Group.objects.create(name="test group")
        owner_1 = Owner.objects.create(name="owner 1", group=group)
        owner_2 = Owner.objects.create(name="owner 2", group=group)
        Widget.objects.create(name="widget 1", owner=owner_1)
        Widget.objects.create(name="widget 2", owner=owner_1)
        Widget.objects.create(name="widget 3", owner=owner_2)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "owner_set",
                pairs.reverse_relationship(
                    "owner_set",
                    "group",
                    Owner.objects.all(),
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector(
                            "widget_set",
                            pairs.reverse_relationship(
                                "widget_set",
                                "owner",
                                Widget.objects.all(),
                                pairs.producer_to_projector(
                                    "name", pairs.field("name")
                                ),
                            ),
                        ),
                    ),
                ),
            ),
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

    def test_reverse_many_to_one_relationship_with_to_attr(self):
        group = Group.objects.create(name="test group")
        Owner.objects.create(name="owner 1", group=group)
        Owner.objects.create(name="owner 2", group=group)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "owner_set_attr",
                pairs.reverse_relationship(
                    "owner_set",
                    "group",
                    Owner.objects.all(),
                    pairs.producer_to_projector("name", pairs.field("name")),
                    to_attr="owner_set_attr",
                ),
            ),
        )

        instance = prepare(Group.objects.all()).first()
        result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test group",
                "owner_set_attr": [
                    {"name": "owner 1"},
                    {"name": "owner 2"},
                ],
            },
        )

    def test_reverse_many_to_one_relationship_with_slice(self):
        group = Group.objects.create(name="test group")
        owner = Owner.objects.create(name="test owner", group=group)
        Widget.objects.create(name="widget 1", value=1, owner=owner)
        Widget.objects.create(name="widget 2", value=100, owner=owner)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "widget_set_attr",
                pairs.reverse_relationship(
                    "widget_set",
                    "owner",
                    Widget.objects.all().order_by("value"),
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector("value", pairs.field("value")),
                    ),
                    to_attr="widget_set_attr",
                    slice=slice(0, 1),
                ),
            ),
        )

        with self.assertNumQueries(0):
            queryset = prepare(Owner.objects.all())

        with self.assertNumQueries(2):
            instance = queryset.first()

        with self.assertNumQueries(0):
            result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test owner",
                "widget_set_attr": [
                    {"name": "widget 1", "value": 1},
                ],
            },
        )

    def test_reverse_many_to_one_relationship_with_slice_post_fn(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="widget 1", value=1, owner=owner)
        Widget.objects.create(name="widget 2", value=100, owner=owner)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "widget_set_attr",
                pairs.reverse_relationship(
                    "widget_set",
                    "owner",
                    Widget.objects.all().order_by("value"),
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector("value", pairs.field("value")),
                    ),
                    to_attr="widget_set_attr",
                    post_fn=utils.collapse_list,
                    slice=slice(1, 2),
                ),
            ),
        )

        with self.assertNumQueries(0):
            queryset = prepare(Owner.objects.all())

        with self.assertNumQueries(2):
            instance = queryset.first()

        with self.assertNumQueries(0):
            result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test owner",
                "widget_set_attr": {"name": "widget 2", "value": 100},
            },
        )

    def test_one_to_one_relationship(self):
        widget = Widget.objects.create(name="test widget")
        Thing.objects.create(name="test thing", widget=widget)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "widget",
                pairs.forward_relationship(
                    "widget",
                    Widget.objects.all(),
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector(
                            "thing",
                            pairs.reverse_relationship(
                                "thing",
                                "widget",
                                Thing.objects.all(),
                                pairs.producer_to_projector(
                                    "name", pairs.field("name")
                                ),
                            ),
                        ),
                    ),
                ),
            ),
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

    def test_one_to_one_relationship_with_to_attr(self):
        widget = Widget.objects.create(name="test widget")
        Thing.objects.create(name="test thing", widget=widget)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "widget_attr",
                pairs.forward_relationship(
                    "widget",
                    Widget.objects.all(),
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector(
                            "thing_attr",
                            pairs.reverse_relationship(
                                "thing",
                                "widget",
                                Thing.objects.all(),
                                pairs.producer_to_projector(
                                    "name", pairs.field("name")
                                ),
                                to_attr="thing_attr",
                            ),
                        ),
                    ),
                    to_attr="widget_attr",
                ),
            ),
        )

        instance = prepare(Thing.objects.all()).first()
        result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test thing",
                "widget_attr": {
                    "name": "test widget",
                    "thing_attr": {"name": "test thing"},
                },
            },
        )

    def test_many_to_many_relationship(self):
        widget = Widget.objects.create(name="test widget")
        category = Category.objects.create(name="test category")
        category.widget_set.add(widget)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "widget_set",
                pairs.many_to_many_relationship(
                    "widget_set",
                    Widget.objects.all(),
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector(
                            "category_set",
                            pairs.many_to_many_relationship(
                                "category_set",
                                Category.objects.all(),
                                pairs.producer_to_projector(
                                    "name", pairs.field("name")
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )

        with self.assertNumQueries(0):
            queryset = prepare(Category.objects.all())

        with self.assertNumQueries(3):
            instance = queryset.first()

        with self.assertNumQueries(0):
            result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test category",
                "widget_set": [
                    {"name": "test widget", "category_set": [{"name": "test category"}]}
                ],
            },
        )

    def test_many_to_many_relationship_with_to_attr(self):
        widget = Widget.objects.create(name="test widget")
        category = Category.objects.create(name="test category")
        category.widget_set.add(widget)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "widget_set_attr",
                pairs.many_to_many_relationship(
                    "widget_set",
                    Widget.objects.all(),
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector(
                            "category_set_attr",
                            pairs.many_to_many_relationship(
                                "category_set",
                                Category.objects.all(),
                                pairs.producer_to_projector(
                                    "name", pairs.field("name")
                                ),
                                to_attr="category_set_attr",
                            ),
                        ),
                    ),
                    to_attr="widget_set_attr",
                ),
            ),
        )

        instance = prepare(Category.objects.all()).first()
        result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test category",
                "widget_set_attr": [
                    {
                        "name": "test widget",
                        "category_set_attr": [{"name": "test category"}],
                    }
                ],
            },
        )

    def test_many_to_many_relationship_with_to_attr_slice_post_fn(self):
        widget_1 = Widget.objects.create(name="test widget 1")
        widget_2 = Widget.objects.create(name="test widget 2")
        category = Category.objects.create(name="test category")
        category.widget_set.add(widget_1)
        category.widget_set.add(widget_2)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "widget_set_attr",
                pairs.many_to_many_relationship(
                    "widget_set",
                    Widget.objects.all().order_by("-name"),
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector(
                            "category_set_attr",
                            pairs.many_to_many_relationship(
                                "category_set",
                                Category.objects.all().order_by("-name"),
                                pairs.producer_to_projector(
                                    "name", pairs.field("name")
                                ),
                                to_attr="category_set_attr",
                            ),
                        ),
                    ),
                    to_attr="widget_set_attr",
                    post_fn=utils.collapse_list,
                    slice=slice(1),
                ),
            ),
        )

        instance = prepare(Category.objects.all()).first()
        result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test category",
                "widget_set_attr": {
                    "name": "test widget 2",
                    "category_set_attr": [{"name": "test category"}],
                },
            },
        )

    def test_relationship(self):
        owner = Owner.objects.create(name="test owner")
        widget = Widget.objects.create(name="test widget", owner=owner)
        category = Category.objects.create(name="test category")
        category.widget_set.add(widget)
        Thing.objects.create(name="test thing", widget=widget)

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "owner",
                pairs.relationship(
                    "owner",
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector(
                            "widget_set",
                            pairs.relationship(
                                "widget_set",
                                pairs.producer_to_projector(
                                    "name", pairs.field("name")
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            pairs.producer_to_projector(
                "category_set",
                pairs.relationship(
                    "category_set",
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector(
                            "widget_set",
                            pairs.relationship(
                                "widget_set",
                                pairs.producer_to_projector(
                                    "name", pairs.field("name")
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            pairs.producer_to_projector(
                "thing",
                pairs.relationship(
                    "thing",
                    pairs.combine(
                        pairs.producer_to_projector("name", pairs.field("name")),
                        pairs.producer_to_projector(
                            "widget",
                            pairs.relationship(
                                "widget",
                                pairs.producer_to_projector(
                                    "name", pairs.field("name")
                                ),
                            ),
                        ),
                    ),
                ),
            ),
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

    def test_relationship_with_to_attr(self):
        Widget.objects.create(
            name="test widget", owner=Owner.objects.create(name="test owner")
        )

        prepare, project = pairs.combine(
            pairs.producer_to_projector("name", pairs.field("name")),
            pairs.producer_to_projector(
                "owner_attr",
                pairs.relationship(
                    "owner",
                    pairs.producer_to_projector("name", pairs.field("name")),
                    to_attr="owner_attr",
                ),
            ),
        )

        instance = prepare(Widget.objects.all()).first()
        result = project(instance)

        self.assertEqual(
            result,
            {
                "name": "test widget",
                "owner_attr": {
                    "name": "test owner",
                },
            },
        )

    def test_select_related(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test widget", owner=owner)

        prepare, project = pairs.combine(
            (
                qs.pipe(
                    qs.select_related("owner"),
                    qs.include_fields("owner__name"),
                ),
                projectors.noop,
            ),
            pairs.producer_to_projector("name", pairs.field("name")),
            (
                qs.noop,
                projectors.producer_to_projector(
                    "owner",
                    producers.relationship(
                        "owner",
                        projectors.producer_to_projector(
                            "name", producers.attr("name")
                        ),
                    ),
                ),
            ),
        )

        with self.assertNumQueries(0):
            queryset = prepare(Widget.objects.all())

        with self.assertNumQueries(1):
            instance = queryset.first()

        with self.assertNumQueries(0):
            result = project(instance)

        self.assertEqual(
            result, {"name": "test widget", "owner": {"name": "test owner"}}
        )


class FieldDisplayTestCase(TestCase):
    def test_field_display(self):
        Thing.objects.create(size="L")
        Thing.objects.create(size="S")
        prepare, project = pairs.producer_to_projector(
            "size_display", pairs.field_display("size")
        )
        queryset = prepare(Thing.objects.order_by("size"))
        result = [project(item) for item in queryset]
        self.assertEqual(
            result,
            [
                {"size_display": "Large"},
                {"size_display": "Small"},
            ],
        )


class FilterTestCase(TestCase):
    def test_filter(self):
        Widget.objects.create(name="first")
        Widget.objects.create(name="second")

        prepare, project = pairs.combine(
            pairs.filter(name="first"),
            pairs.producer_to_projector("name", pairs.field("name")),
        )

        queryset = prepare(Widget.objects.all())
        self.assertEqual(len(queryset), 1)
        result = project(queryset.first())
        self.assertEqual(result, {"name": "first"})


class ExcludeTestCase(TestCase):
    def test_exclude(self):
        Widget.objects.create(name="first")
        Widget.objects.create(name="second")

        prepare, project = pairs.combine(
            pairs.exclude(name="first"),
            pairs.producer_to_projector("name", pairs.field("name")),
        )

        queryset = prepare(Widget.objects.all())
        self.assertEqual(len(queryset), 1)
        result = project(queryset.first())
        self.assertEqual(result, {"name": "second"})


class OrderByTestCase(TestCase):
    def test_order_by(self):
        Widget.objects.create(name="c")
        Widget.objects.create(name="b")
        Widget.objects.create(name="a")

        prepare, project = pairs.combine(
            pairs.order_by("name"),
            pairs.producer_to_projector("name", pairs.field("name")),
        )

        queryset = prepare(Widget.objects.all())
        result = [project(item) for item in queryset]
        self.assertEqual(result, [{"name": "a"}, {"name": "b"}, {"name": "c"}])


class PKListTestCase(TestCase):
    def test_pk_list(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner)
        Widget.objects.create(name="test 2", owner=owner)
        Widget.objects.create(name="test 3", owner=owner)

        prepare, project = pairs.producer_to_projector(
            "widget_set", pairs.pk_list("widget_set")
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"widget_set": [1, 2, 3]})

    def test_pk_list_with_to_attr(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner)
        Widget.objects.create(name="test 2", owner=owner)
        Widget.objects.create(name="test 3", owner=owner)

        prepare, project = pairs.producer_to_projector(
            "widgets", pairs.pk_list("widget_set", to_attr="widgets")
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"widgets": [1, 2, 3]})


class AnnotateTestCase(TestCase):
    def test_annotate_with_arg(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner)
        Widget.objects.create(name="test 2", owner=owner)
        Widget.objects.create(name="test 3", owner=owner)

        prepare, project = pairs.producer_to_projector(
            "widget_count", pairs.annotate(Count("widget"))
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"widget_count": 3})

    def test_annotate_with_kwarg(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner)
        Widget.objects.create(name="test 2", owner=owner)
        Widget.objects.create(name="test 3", owner=owner)

        prepare, project = pairs.producer_to_projector(
            "widget_count", pairs.annotate(number_of_widgets=Count("widget"))
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"widget_count": 3})

    def test_transform_value_with_arg(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner)
        prepare, project = pairs.producer_to_projector(
            "has_many_widgets",
            pairs.annotate(Count("widget"), transform_value=lambda value: value > 5),
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"has_many_widgets": False})

    def test_transform_value_with_kwarg(self):
        Owner.objects.create(name="some long name")
        prepare, project = pairs.producer_to_projector(
            "has_long_name",
            pairs.annotate(
                name_length=Length("name"), transform_value=lambda value: value > 10
            ),
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"has_long_name": True})

    def test_complex_annotation(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner)
        Widget.objects.create(name="test 2", owner=owner)

        prepare, project = pairs.producer_to_projector(
            "test",
            pairs.annotate(
                test=(Count("widget") + Length("name")),
                transform_value=lambda value: value + 5,
            ),
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"test": 17})

    def test_multiple_args_raises_exception(self):
        with self.assertRaises(ValueError):
            pairs.annotate(Count("foo"), Count("bar"))

    def test_multiple_kwargs_raises_exception(self):
        with self.assertRaises(ValueError):
            pairs.annotate(foo=Count("foo"), bar=Count("bar"))

    def test_arg_and_kwarg_raises_exception(self):
        with self.assertRaises(ValueError):
            pairs.annotate(Count("foo"), bar=Count("bar"))


class CountTestCase(TestCase):
    def test_count(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner)
        Widget.objects.create(name="test 2", owner=owner)
        Widget.objects.create(name="test 3", owner=owner)

        prepare, project = pairs.producer_to_projector(
            "widget_count", pairs.count("widget")
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"widget_count": 3})


class SumTestCase(TestCase):
    def test_sum(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner, value=12)
        Widget.objects.create(name="test 2", owner=owner, value=34)
        Widget.objects.create(name="test 3", owner=owner, value=56)

        prepare, project = pairs.producer_to_projector(
            "widget_total_value", pairs.sum("widget__value")
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"widget_total_value": 102})


class HasTestCase(TestCase):
    def test_has_false(self):
        Owner.objects.create(name="test owner")

        prepare, project = pairs.producer_to_projector(
            "has_widget", pairs.has("widget")
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"has_widget": False})

    def test_has_true(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test", owner=owner)

        prepare, project = pairs.producer_to_projector(
            "has_widget", pairs.has("widget")
        )

        queryset = prepare(Owner.objects.all())
        result = project(queryset.first())
        self.assertEqual(result, {"has_widget": True})


class DiscardTestCase(TestCase):
    def test_discard_projector(self):
        pair = pairs.field("test")
        self.assertEqual(pairs.discard_projector(pair), pair[0])

    def test_discard_queryset_function(self):
        pair = pairs.field("test")
        self.assertEqual(pairs.discard_queryset_function(pair), pair[1])

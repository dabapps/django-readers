from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models import Case, Count, Value, When
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django_readers import qs
from tests.models import Category, LogEntry, Owner, Widget
from unittest import mock

import django

IS_5_2_OR_GREATER = django.VERSION >= (5, 2)


class QuerySetTestCase(TestCase):
    def test_filter(self):
        Widget.objects.create(name="first")
        Widget.objects.create(name="second")
        filtered = qs.filter(name="first")(Widget.objects.all())
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.get().name, "first")

    def test_pipe(self):
        for name in ["first", "second", "third"]:
            Widget.objects.create(name=name)

        prepare = qs.pipe(
            qs.filter(name__in=["first", "third"]),
            qs.exclude(name="third"),
            qs.include_fields("name"),
        )

        queryset = prepare(Widget.objects.all())

        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.get().name, "first")

    def test_noop(self):
        queryset = Widget.objects.all()
        before = str(queryset.query)
        queryset = qs.noop(queryset)
        after = str(queryset.query)
        self.assertEqual(before, after)

    def test_select_related_fields(self):
        Widget.objects.create(
            name="test widget", owner=Owner.objects.create(name="test owner")
        )

        prepare = qs.select_related_fields("owner__name")

        with CaptureQueriesContext(connection) as capture:
            widgets = list(prepare(Widget.objects.all()))

        self.assertEqual(len(capture.captured_queries), 1)

        self.assertEqual(
            capture.captured_queries[0]["sql"],
            "SELECT "
            '"tests_widget"."id", '
            '"tests_widget"."owner_id", '
            '"tests_owner"."id", '
            '"tests_owner"."name" '
            "FROM "
            '"tests_widget" '
            "LEFT OUTER JOIN "
            '"tests_owner" ON ("tests_widget"."owner_id" = "tests_owner"."id")',
        )

        with self.assertNumQueries(0):
            self.assertEqual(widgets[0].owner.name, "test owner")

    def test_prefetch_forward_relationship(self):
        Widget.objects.create(
            name="test widget", owner=Owner.objects.create(name="test owner")
        )

        prepare = qs.prefetch_forward_relationship(
            "owner", Owner.objects.all(), qs.include_fields("name")
        )

        with CaptureQueriesContext(connection) as capture:
            widgets = list(prepare(Widget.objects.all()))

        self.assertEqual(len(capture.captured_queries), 2)

        self.assertEqual(
            capture.captured_queries[0]["sql"],
            "SELECT "
            '"tests_widget"."id", '
            '"tests_widget"."owner_id" '
            "FROM "
            '"tests_widget"',
        )

        self.assertEqual(
            capture.captured_queries[1]["sql"],
            "SELECT "
            '"tests_owner"."id", '
            '"tests_owner"."name" '
            "FROM "
            '"tests_owner" '
            "WHERE "
            '"tests_owner"."id" ' + ("= 1" if IS_5_2_OR_GREATER else "IN (1)"),
        )

        with self.assertNumQueries(0):
            self.assertEqual(widgets[0].owner.name, "test owner")

    def test_prefetch_forward_relationship_only_loads_pk_by_default(self):
        Widget.objects.create(
            name="test widget", owner=Owner.objects.create(name="test owner")
        )

        prepare = qs.prefetch_forward_relationship("owner", Owner.objects.all())

        with CaptureQueriesContext(connection) as capture:
            list(prepare(Widget.objects.all()))

        self.assertEqual(len(capture.captured_queries), 2)

        self.assertEqual(
            capture.captured_queries[0]["sql"],
            "SELECT "
            '"tests_widget"."id", '
            '"tests_widget"."owner_id" '
            "FROM "
            '"tests_widget"',
        )

        self.assertEqual(
            capture.captured_queries[1]["sql"],
            "SELECT "
            '"tests_owner"."id" '
            "FROM "
            '"tests_owner" '
            "WHERE "
            '"tests_owner"."id" ' + ("= 1" if IS_5_2_OR_GREATER else "IN (1)"),
        )

    def test_prefetch_forward_relationship_with_to_attr(self):
        Widget.objects.create(
            name="test widget", owner=Owner.objects.create(name="test owner")
        )

        prepare = qs.prefetch_forward_relationship(
            "owner", Owner.objects.all(), qs.include_fields("name"), to_attr="attr"
        )

        widgets = list(prepare(Widget.objects.all()))

        with self.assertNumQueries(0):
            self.assertEqual(widgets[0].attr.name, "test owner")

    def test_prefetch_reverse_relationship(self):
        Widget.objects.create(
            name="test widget", owner=Owner.objects.create(name="test owner")
        )

        prepare = qs.pipe(
            qs.include_fields("name"),
            qs.prefetch_reverse_relationship(
                "widget_set", "owner", Widget.objects.all(), qs.include_fields("name")
            ),
        )

        with CaptureQueriesContext(connection) as capture:
            owners = list(prepare(Owner.objects.all()))

        self.assertEqual(len(capture.captured_queries), 2)

        self.assertEqual(
            capture.captured_queries[0]["sql"],
            "SELECT "
            '"tests_owner"."id", '
            '"tests_owner"."name" '
            "FROM "
            '"tests_owner"',
        )

        self.assertEqual(
            capture.captured_queries[1]["sql"],
            "SELECT "
            '"tests_widget"."id", '
            '"tests_widget"."name", '
            '"tests_widget"."owner_id" '
            "FROM "
            '"tests_widget" '
            "WHERE "
            '"tests_widget"."owner_id" IN (1)',
        )

        with self.assertNumQueries(0):
            self.assertEqual(owners[0].widget_set.all()[0].name, "test widget")

    def test_prefetch_reverse_generic_relationship(self):
        widget = Widget.objects.create(name="test widget")
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(widget),
            object_pk=widget.id,
            event="CREATED",
        )

        prepare = qs.pipe(
            qs.include_fields("name"),
            qs.prefetch_reverse_generic_relationship(
                "logs",
                "content_type",
                "object_pk",
                LogEntry.objects.all(),
                qs.include_fields("event"),
            ),
        )

        with CaptureQueriesContext(connection) as capture:
            widgets = list(prepare(Widget.objects.all()))

        self.assertEqual(len(capture.captured_queries), 2)

        self.assertEqual(
            capture.captured_queries[0]["sql"],
            "SELECT "
            '"tests_widget"."id", '
            '"tests_widget"."name" '
            "FROM "
            '"tests_widget"',
        )

        content_type_id = ContentType.objects.get_for_model(Widget).pk

        self.assertEqual(
            capture.captured_queries[1]["sql"],
            "SELECT "
            '"tests_logentry"."id", '
            '"tests_logentry"."content_type_id", '
            '"tests_logentry"."object_pk", '
            '"tests_logentry"."event" '
            "FROM "
            '"tests_logentry" '
            "WHERE "
            f'("tests_logentry"."content_type_id" = {content_type_id} AND '
            '"tests_logentry"."object_pk" IN '
            "('1'))",
        )

        with self.assertNumQueries(0):
            self.assertEqual(widgets[0].logs.all()[0].event, "CREATED")

    def test_prefetch_reverse_generic_relationship_with_to_attr(self):
        widget = Widget.objects.create(name="test widget")
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(widget),
            object_pk=widget.id,
            event="CREATED",
        )

        prepare = qs.pipe(
            qs.include_fields("name"),
            qs.prefetch_reverse_generic_relationship(
                "logs",
                "content_type",
                "object_pk",
                LogEntry.objects.all(),
                qs.include_fields("event"),
                to_attr="history",
            ),
        )

        widgets = list(prepare(Widget.objects.all()))

        with self.assertNumQueries(0):
            self.assertEqual(widgets[0].history[0].event, "CREATED")

    def test_prefetch_reverse_relationship_only_loads_pk_and_related_name_by_default(
        self,
    ):
        Widget.objects.create(
            name="test widget", owner=Owner.objects.create(name="test owner")
        )

        prepare = qs.prefetch_reverse_relationship(
            "widget_set", "owner", Widget.objects.all()
        )

        with CaptureQueriesContext(connection) as capture:
            list(prepare(Owner.objects.all()))

        self.assertEqual(len(capture.captured_queries), 2)

        self.assertEqual(
            capture.captured_queries[0]["sql"],
            'SELECT "tests_owner"."id" FROM "tests_owner"',
        )

        self.assertEqual(
            capture.captured_queries[1]["sql"],
            "SELECT "
            '"tests_widget"."id", '
            '"tests_widget"."owner_id" '
            "FROM "
            '"tests_widget" '
            "WHERE "
            '"tests_widget"."owner_id" IN (1)',
        )

    def test_prefetch_reverse_relationship_with_to_attr(self):
        Widget.objects.create(
            name="test widget", owner=Owner.objects.create(name="test owner")
        )

        prepare = qs.pipe(
            qs.include_fields("name"),
            qs.prefetch_reverse_relationship(
                "widget_set",
                "owner",
                Widget.objects.all(),
                qs.include_fields("name"),
                to_attr="attr",
            ),
        )

        owners = list(prepare(Owner.objects.all()))

        with self.assertNumQueries(0):
            self.assertEqual(owners[0].attr[0].name, "test widget")

    def test_prefetch_many_to_many_relationship(self):
        widget = Widget.objects.create(name="test widget")
        category = Category.objects.create(name="test category")

        widget.category_set.add(category)

        prepare = qs.pipe(
            qs.include_fields("name"),
            qs.prefetch_many_to_many_relationship(
                "category_set", Category.objects.all(), qs.include_fields("name")
            ),
        )

        with CaptureQueriesContext(connection) as capture:
            widgets = list(prepare(Widget.objects.all()))

        self.assertEqual(len(capture.captured_queries), 2)

        self.assertEqual(
            capture.captured_queries[0]["sql"],
            "SELECT "
            '"tests_widget"."id", '
            '"tests_widget"."name" '
            "FROM "
            '"tests_widget"',
        )

        self.assertEqual(
            capture.captured_queries[1]["sql"],
            "SELECT "
            '("tests_category_widget_set"."widget_id") '
            'AS "_prefetch_related_val_widget_id", '
            '"tests_category"."id", '
            '"tests_category"."name" '
            "FROM "
            '"tests_category" '
            "INNER JOIN "
            '"tests_category_widget_set" ON '
            '("tests_category"."id" = "tests_category_widget_set"."category_id") '
            "WHERE "
            '"tests_category_widget_set"."widget_id" IN (1)',
        )

        with self.assertNumQueries(0):
            self.assertEqual(widgets[0].category_set.all()[0].name, "test category")

    def test_prefetch_many_to_many_relationship_only_loads_pk_by_default(self):
        widget = Widget.objects.create(name="test widget")
        category = Category.objects.create(name="test category")

        widget.category_set.add(category)

        prepare = qs.prefetch_many_to_many_relationship(
            "category_set", Category.objects.all()
        )

        with CaptureQueriesContext(connection) as capture:
            list(prepare(Widget.objects.all()))

        self.assertEqual(len(capture.captured_queries), 2)

        self.assertEqual(
            capture.captured_queries[0]["sql"],
            'SELECT "tests_widget"."id" FROM "tests_widget"',
        )

        self.assertEqual(
            capture.captured_queries[1]["sql"],
            "SELECT "
            '("tests_category_widget_set"."widget_id") '
            'AS "_prefetch_related_val_widget_id", '
            '"tests_category"."id" '
            "FROM "
            '"tests_category" '
            "INNER JOIN "
            '"tests_category_widget_set" ON '
            '("tests_category"."id" = "tests_category_widget_set"."category_id") '
            "WHERE "
            '"tests_category_widget_set"."widget_id" IN (1)',
        )

    def test_prefetch_many_to_many_relationship_with_to_attr(self):
        widget = Widget.objects.create(name="test widget")
        category = Category.objects.create(name="test category")

        widget.category_set.add(category)

        prepare = qs.pipe(
            qs.include_fields("name"),
            qs.prefetch_many_to_many_relationship(
                "category_set",
                Category.objects.all(),
                qs.include_fields("name"),
                to_attr="attr",
            ),
        )

        widgets = list(prepare(Widget.objects.all()))

        with self.assertNumQueries(0):
            self.assertEqual(widgets[0].attr[0].name, "test category")

    def test_auto_prefetch_relationship(self):
        with mock.patch("django_readers.qs.prefetch_forward_relationship") as mock_fn:
            qs.auto_prefetch_relationship("owner")(Widget.objects.all())
            mock_fn.assert_called_once()

        with mock.patch("django_readers.qs.prefetch_reverse_relationship") as mock_fn:
            qs.auto_prefetch_relationship("thing")(Widget.objects.all())
            mock_fn.assert_called_once()

        with mock.patch(
            "django_readers.qs.prefetch_many_to_many_relationship"
        ) as mock_fn:
            qs.auto_prefetch_relationship("category_set")(Widget.objects.all())
            mock_fn.assert_called_once()

        with mock.patch(
            "django_readers.qs.prefetch_reverse_generic_relationship"
        ) as mock_fn:
            qs.auto_prefetch_relationship("logs")(Widget.objects.all())
            mock_fn.assert_called_once()

    def test_annotate_only_includes_fk_by_default(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="test 1", owner=owner)
        Widget.objects.create(name="test 2", owner=owner)

        prepare = qs.annotate(num_widgets=Count("widget"))

        with CaptureQueriesContext(connection) as capture:
            list(prepare(Owner.objects.all()))

        self.assertEqual(len(capture.captured_queries), 1)

        self.assertEqual(
            capture.captured_queries[0]["sql"],
            "SELECT "
            '"tests_owner"."id", '
            'COUNT("tests_widget"."id") AS "num_widgets" '
            'FROM "tests_owner" '
            'LEFT OUTER JOIN "tests_widget" '
            'ON ("tests_owner"."id" = "tests_widget"."owner_id") '
            "GROUP BY "
            '"tests_owner"."id"',
        )

    def test_alias(self):
        owner = Owner.objects.create(name="test owner")
        Widget.objects.create(name="first", owner=owner)
        Widget.objects.create(name="second", owner=owner)

        prepare = qs.pipe(
            qs.alias(widget_count=Count("widget")),
            qs.annotate(
                widget_description=Case(
                    When(widget_count=1, then=Value("has one widget")),
                    When(widget_count__gt=1, then=Value("has multiple widgets")),
                    default=Value("has no widgets"),
                )
            ),
        )

        with self.assertNumQueries(1):
            results = list(prepare(Owner.objects.all()))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].widget_description, "has multiple widgets")
        self.assertFalse(
            hasattr(results[0], "widget_count"),
            "The widget_count alias should not be present in the result",
        )

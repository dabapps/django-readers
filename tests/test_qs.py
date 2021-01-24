from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from djunc import qs
from tests.models import Owner, Widget


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
            widget = prepare(Widget.objects.all()).get()

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
            self.assertEqual(widget.owner.name, "test owner")

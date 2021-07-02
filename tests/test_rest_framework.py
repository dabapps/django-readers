from django.test import TestCase
from django_readers.rest_framework import SpecMixin
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.test import APIRequestFactory
from tests.models import Category, Group, Owner, Widget


class WidgetListView(SpecMixin, ListAPIView):
    queryset = Widget.objects.all()
    spec = [
        "name",
        {
            "owner": [
                "name",
                {
                    "group": [
                        "name",
                    ]
                },
            ]
        },
    ]


class CategoryDetailView(SpecMixin, RetrieveAPIView):
    queryset = Category.objects.all()
    spec = [
        "name",
        {
            "widget_set": [
                "name",
                {
                    "owner": [
                        "name",
                    ]
                },
            ]
        },
    ]


class RESTFrameworkTestCase(TestCase):
    def test_list(self):
        Widget.objects.create(
            name="test widget",
            owner=Owner.objects.create(
                name="test owner", group=Group.objects.create(name="test group")
            ),
        )

        request = APIRequestFactory().get("/")
        view = WidgetListView.as_view()

        with self.assertNumQueries(3):
            response = view(request)

        self.assertEqual(
            response.data,
            [
                {
                    "name": "test widget",
                    "owner": {
                        "name": "test owner",
                        "group": {
                            "name": "test group",
                        },
                    },
                }
            ],
        )

    def test_detail(self):
        category = Category.objects.create(name="test category")
        owner = Owner.objects.create(name="test owner")
        category.widget_set.add(Widget.objects.create(name="test 1", owner=owner))
        category.widget_set.add(Widget.objects.create(name="test 2", owner=owner))

        request = APIRequestFactory().get("/")
        view = CategoryDetailView.as_view()

        with self.assertNumQueries(3):
            response = view(request, pk=str(category.pk))

        self.assertEqual(
            response.data,
            {
                "name": "test category",
                "widget_set": [
                    {
                        "name": "test 1",
                        "owner": {"name": "test owner"},
                    },
                    {
                        "name": "test 2",
                        "owner": {"name": "test owner"},
                    },
                ],
            },
        )

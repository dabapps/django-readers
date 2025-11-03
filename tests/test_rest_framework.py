from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django_readers import pairs, qs
from django_readers.rest_framework import (
    out,
    serializer_class_for_spec,
    serializer_class_for_view,
    SpecMixin,
)
from rest_framework import serializers
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.test import APIRequestFactory
from tests.models import Category, Group, LogEntry, Owner, Widget
from textwrap import dedent
from typing import Optional


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
        {"logs": ["event"]},
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


upper_name = pairs.field("name", transform_value=lambda value: value.upper())


class RESTFrameworkTestCase(TestCase):
    def test_list(self):
        widget = Widget.objects.create(
            name="test widget",
            owner=Owner.objects.create(
                name="test owner", group=Group.objects.create(name="test group")
            ),
        )
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(widget),
            object_pk=widget.id,
            event="CREATED",
        )
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(widget),
            object_pk=widget.id,
            event="UPDATED",
        )
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(widget),
            object_pk=widget.id,
            event="DELETED",
        )

        request = APIRequestFactory().get("/")
        view = WidgetListView.as_view()

        with self.assertNumQueries(4):
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
                    "logs": [
                        {"event": "CREATED"},
                        {"event": "UPDATED"},
                        {"event": "DELETED"},
                    ],
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


class SpecToSerializerClassTestCase(TestCase):
    def test_basic_spec(self):
        spec = ["name"]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_nested_spec(self):
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

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                widget_set = CategoryWidgetSetSerializer(many=True, read_only=True):
                    name = CharField(allow_null=True, max_length=100, read_only=True, required=False)
                    owner = CategoryWidgetSetOwnerSerializer(allow_null=True, read_only=True):
                        name = CharField(max_length=100, read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_all_relationship_types(self):
        spec = [
            "name",
            {
                "group": [
                    "name",
                ]
            },
            {
                "widget_set": [
                    "name",
                    {
                        "category_set": [
                            "name",
                        ]
                    },
                    {
                        "thing": [
                            "name",
                            {
                                "related_widget": {
                                    "widget": [
                                        "name",
                                    ]
                                }
                            },
                        ]
                    },
                    {
                        "logs": [
                            "event",
                        ]
                    },
                ]
            },
        ]

        cls = serializer_class_for_spec("Owner", Owner, spec)
        expected = dedent(
            """\
            OwnerSerializer():
                name = CharField(max_length=100, read_only=True)
                group = OwnerGroupSerializer(allow_null=True, read_only=True):
                    name = CharField(max_length=100, read_only=True)
                widget_set = OwnerWidgetSetSerializer(many=True, read_only=True):
                    name = CharField(allow_null=True, max_length=100, read_only=True, required=False)
                    category_set = OwnerWidgetSetCategorySetSerializer(many=True, read_only=True):
                        name = CharField(max_length=100, read_only=True)
                    thing = OwnerWidgetSetThingSerializer(allow_null=True, read_only=True):
                        name = CharField(max_length=100, read_only=True)
                        related_widget = OwnerWidgetSetThingRelatedWidgetSerializer(allow_null=True, read_only=True, source='widget'):
                            name = CharField(allow_null=True, max_length=100, read_only=True, required=False)
                    logs = OwnerWidgetSetLogsSerializer(allow_null=True, many=True, read_only=True):
                        event = CharField(max_length=100, read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_nullable_relationship(self):
        spec = ["name", {"owner": ["name"]}]

        cls = serializer_class_for_spec("Widget", Widget, spec)

        expected = dedent(
            """\
            WidgetSerializer():
                name = CharField(allow_null=True, max_length=100, read_only=True, required=False)
                owner = WidgetOwnerSerializer(allow_null=True, read_only=True):
                    name = CharField(max_length=100, read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_duplicate_relationship_naming(self):
        spec = [
            {"widget_set": ["name"]},
            {"set_of_widgets": {"widget_set": ["name"]}},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                widget_set = CategoryWidgetSetSerializer(many=True, read_only=True):
                    name = CharField(allow_null=True, max_length=100, read_only=True, required=False)
                set_of_widgets = CategorySetOfWidgetsSerializer(many=True, read_only=True, source='widget_set'):
                    name = CharField(allow_null=True, max_length=100, read_only=True, required=False)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_serializer_class_for_view(self):
        class CategoryListView(SpecMixin, ListAPIView):
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

        cls = serializer_class_for_view(CategoryListView())

        expected = dedent(
            """\
            CategoryListSerializer():
                name = CharField(max_length=100, read_only=True)
                widget_set = CategoryListWidgetSetSerializer(many=True, read_only=True):
                    name = CharField(allow_null=True, max_length=100, read_only=True, required=False)
                    owner = CategoryListWidgetSetOwnerSerializer(allow_null=True, read_only=True):
                        name = CharField(max_length=100, read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_exception_raised_if_model_missing(self):
        class SomeListView(SpecMixin, ListAPIView):
            spec = ["name"]

        with self.assertRaises(ImproperlyConfigured):
            serializer_class_for_view(SomeListView())


class OutputFieldTestCase(TestCase):
    def test_output_field(self):
        spec = [
            "name",
            {"upper_name": out(serializers.CharField())(upper_name)},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                upper_name = CharField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_output_field_python_type(self):
        spec = [
            "name",
            {"upper_name": out(str)(upper_name)},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                upper_name = CharField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_output_field_decorator(self):
        @out(serializers.CharField())
        def hello():
            return lambda qs: qs, lambda _: "Hello"

        spec = [
            "name",
            {"hello": hello()},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                hello = CharField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_output_field_decorator_python_type(self):
        @out(Optional[str])
        def hello():
            return lambda qs: qs, lambda _: "Hello"

        spec = [
            "name",
            {"hello": hello()},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                hello = CharField(allow_null=True, read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_output_field_decorator_producer(self):
        @out(serializers.CharField())
        def produce_hello(_):
            return "Hello"

        hello = qs.noop, produce_hello

        spec = [
            "name",
            {"hello": hello},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                hello = CharField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_output_field_decorator_producer_python_type(self):
        @out(str)
        def produce_hello(_):
            return "Hello"

        hello = qs.noop, produce_hello

        spec = [
            "name",
            {"hello": hello},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                hello = CharField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_output_field_producer_return_type(self):
        def produce_hello() -> str:
            return "Hello"

        hello = qs.noop, produce_hello

        spec = [
            "name",
            {"hello": hello},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                hello = CharField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_output_field_decorator_producer_boolean(self):
        # this is a useful test case because booleans can't be subclassed
        # or have arbitrary attributes added to them.

        @out(serializers.BooleanField())
        def produce_bool(_):
            return True

        bool_pair = qs.noop, produce_bool

        spec = [
            "name",
            {"bool": bool_pair},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                bool = BooleanField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)
        self.assertTrue(produce_bool(None) is True)

    def test_output_field_decorator_producer_boolean_python_type(self):
        # this is a useful test case because booleans can't be subclassed
        # or have arbitrary attributes added to them.

        @out(bool)
        def produce_bool(_):
            return True

        bool_pair = qs.noop, produce_bool

        spec = [
            "name",
            {"bool": bool_pair},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                bool = BooleanField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)
        self.assertTrue(produce_bool(None) is True)

    def test_out_rrshift(self):
        spec = [
            "name",
            {"upper_name": upper_name >> out(serializers.CharField())},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                upper_name = CharField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_out_rrshift_python_type(self):
        spec = [
            "name",
            {"upper_name": upper_name >> out(str)},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                upper_name = CharField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_field_name_override(self):
        spec = [
            "name" >> out(serializers.IntegerField()),
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = IntegerField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_field_name_override_python_type(self):
        spec = [
            "name" >> out(int),
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = IntegerField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_out_kwargs(self):
        @out(serializers.CharField(), label="Hello label")
        def produce_hello(_):
            return "Hello"

        hello = qs.noop, produce_hello

        spec = [
            "name" >> out(help_text="Help for name"),
            {"aliased_name": "name" >> out(label="Label for aliased name")},
            {"upper_name": out(help_text="Help for upper name")(upper_name)},
            # This is a bit redundant (kwargs could just be passed to the field
            # directly) but should still work.
            {"hello": hello},
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(help_text='Help for name', max_length=100, read_only=True)
                aliased_name = CharField(label='Label for aliased name', max_length=100, read_only=True, source='name')
                upper_name = ReadOnlyField(help_text='Help for upper name')
                hello = CharField(label='Hello label', read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_out_raises_with_field_class(self):
        with self.assertRaises(TypeError):
            out(serializers.CharField)

    def test_output_field_is_ignored_when_calling_view(self):
        class WidgetListView(SpecMixin, ListAPIView):
            queryset = Widget.objects.all()
            spec = [
                "name",
                {"upper_name": out(serializers.CharField())(upper_name)},
                {
                    "owned_by": {
                        "owner": [
                            "name",
                            {"upper_name": out(serializers.CharField())(upper_name)},
                        ]
                    }
                },
            ]

        Widget.objects.create(
            name="test widget",
            owner=Owner.objects.create(name="test owner"),
        )

        request = APIRequestFactory().get("/")
        view = WidgetListView.as_view()

        response = view(request)

        self.assertEqual(
            response.data,
            [
                {
                    "name": "test widget",
                    "upper_name": "TEST WIDGET",
                    "owned_by": {
                        "name": "test owner",
                        "upper_name": "TEST OWNER",
                    },
                }
            ],
        )

    def test_out_with_projector_pair(self):
        @out(
            {
                "upper_name": serializers.CharField(),
                "name_length": serializers.IntegerField(),
            }
        )
        def upper_name_and_name_length():
            def project(instance):
                return {
                    "upper_name": instance.name.upper(),
                    "name_length": len(instance.name),
                }

            return qs.include_fields("name"), project

        spec = [
            "name",
            upper_name_and_name_length(),
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                upper_name = CharField(read_only=True)
                name_length = IntegerField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_out_with_projector_pair_python_type(self):
        @out(
            {
                "upper_name": str,
                "name_length": int,
            }
        )
        def upper_name_and_name_length():
            def project(instance):
                return {
                    "upper_name": instance.name.upper(),
                    "name_length": len(instance.name),
                }

            return qs.include_fields("name"), project

        spec = [
            "name",
            upper_name_and_name_length(),
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                upper_name = CharField(read_only=True)
                name_length = IntegerField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_out_with_projector_pair_projector_only(self):
        @out(
            {
                "upper_name": serializers.CharField(),
                "name_length": serializers.IntegerField(),
            }
        )
        def project(instance):
            return {
                "upper_name": instance.name.upper(),
                "name_length": len(instance.name),
            }

        upper_name_and_name_length = qs.include_fields("name"), project

        spec = [
            "name",
            upper_name_and_name_length,
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                upper_name = CharField(read_only=True)
                name_length = IntegerField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)

    def test_out_with_projector_pair_projector_only_python_type(self):
        @out(
            {
                "upper_name": str,
                "name_length": int,
            }
        )
        def project(instance):
            return {
                "upper_name": instance.name.upper(),
                "name_length": len(instance.name),
            }

        upper_name_and_name_length = qs.include_fields("name"), project

        spec = [
            "name",
            upper_name_and_name_length,
        ]

        cls = serializer_class_for_spec("Category", Category, spec)

        expected = dedent(
            """\
            CategorySerializer():
                name = CharField(max_length=100, read_only=True)
                upper_name = CharField(read_only=True)
                name_length = IntegerField(read_only=True)"""
        )
        self.assertEqual(repr(cls()), expected)


class CallableTestCase(TestCase):
    def test_call_producer_pair_with_request(self):
        def user_name(request):
            return lambda qs: qs, lambda _: request.user.name

        class WidgetListView(SpecMixin, ListAPIView):
            queryset = Widget.objects.all()
            spec = [
                "name",
                {
                    "user_name": out(serializers.CharField())(user_name),
                },
                {
                    "owned_by": {
                        "owner": [
                            "name",
                            {"user_name": out(serializers.CharField())(user_name)},
                        ]
                    }
                },
            ]

        Widget.objects.create(
            name="test widget",
            owner=Owner.objects.create(name="test owner"),
        )

        class FakeUser:
            def __init__(self, name):
                self.name = name
                self.is_active = True

        request = APIRequestFactory().get("/")
        request.user = FakeUser(name="Test User")
        view = WidgetListView.as_view()

        response = view(request)

        self.assertEqual(
            response.data,
            [
                {
                    "name": "test widget",
                    "user_name": "Test User",
                    "owned_by": {
                        "name": "test owner",
                        "user_name": "Test User",
                    },
                }
            ],
        )

    def test_undecorated_producer_pair_does_not_cause_error(self):
        def user_name(request):
            return lambda qs: qs, lambda _: request.user.name

        spec = [
            "name",
            {"user_name": user_name},
        ]

        serializer_class_for_spec("Widget", Widget, spec)

    def test_call_projector_pair_with_request(self):
        def user_name_and_id(request):
            return lambda qs: qs, lambda _: {
                "user_name": request.user.name,
                "user_id": request.user.id,
            }

        class WidgetListView(SpecMixin, ListAPIView):
            queryset = Widget.objects.all()
            spec = [
                "name",
                user_name_and_id,
                {
                    "owned_by": {
                        "owner": [
                            "name",
                            user_name_and_id,
                        ]
                    }
                },
            ]

        Widget.objects.create(
            name="test widget",
            owner=Owner.objects.create(name="test owner"),
        )

        class FakeUser:
            def __init__(self, id, name):
                self.name = name
                self.id = id
                self.is_active = True

        request = APIRequestFactory().get("/")
        request.user = FakeUser(id="12345", name="Test User")
        view = WidgetListView.as_view()

        response = view(request)

        self.assertEqual(
            response.data,
            [
                {
                    "name": "test widget",
                    "user_name": "Test User",
                    "user_id": "12345",
                    "owned_by": {
                        "name": "test owner",
                        "user_name": "Test User",
                        "user_id": "12345",
                    },
                }
            ],
        )

    def test_undecorated_projector_pair_does_not_cause_error(self):
        def user_name_and_id(request):
            return lambda qs: qs, lambda _: {
                "user_name": request.user.name,
                "user_id": request.user.id,
            }

        spec = [
            "name",
            user_name_and_id,
        ]

        serializer_class_for_spec("Widget", Widget, spec)

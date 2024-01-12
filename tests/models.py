from django.contrib.contenttypes.fields import GenericRelation
from django.db import models


class LogEntry(models.Model):
    content_type = models.ForeignKey(
        to="contenttypes.ContentType",
        on_delete=models.CASCADE,
        related_name="+",
    )
    object_pk = models.CharField(max_length=255)
    event = models.CharField(max_length=100)


class Group(models.Model):
    name = models.CharField(max_length=100)


class Owner(models.Model):
    name = models.CharField(max_length=100)
    group = models.ForeignKey(Group, null=True, on_delete=models.SET_NULL)


class Widget(models.Model):
    name = models.CharField(max_length=100, null=True)
    value = models.PositiveIntegerField(default=0)
    other = models.CharField(max_length=100, null=True)
    owner = models.ForeignKey(Owner, null=True, on_delete=models.SET_NULL)
    logs = GenericRelation(
        LogEntry, content_type_field="content_type", object_id_field="object_pk"
    )


class Thing(models.Model):
    name = models.CharField(max_length=100)
    size = models.CharField(max_length=10, choices=[("S", "Small"), ("L", "Large")])
    widget = models.OneToOneField(Widget, null=True, on_delete=models.SET_NULL)


class Category(models.Model):
    name = models.CharField(max_length=100)
    widget_set = models.ManyToManyField(Widget)

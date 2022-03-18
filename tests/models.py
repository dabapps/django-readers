from django.db import models


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


class Thing(models.Model):
    name = models.CharField(max_length=100)
    size = models.CharField(max_length=10, choices=[("S", "Small"), ("L", "Large")])
    widget = models.OneToOneField(Widget, null=True, on_delete=models.SET_NULL)


class Category(models.Model):
    name = models.CharField(max_length=100)
    widget_set = models.ManyToManyField(Widget)

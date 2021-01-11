from django.db import models


class Group(models.Model):
    name = models.CharField(max_length=100)


class Owner(models.Model):
    name = models.CharField(max_length=100)
    group = models.ForeignKey(Group, null=True, on_delete=models.SET_NULL)


class Widget(models.Model):
    name = models.CharField(max_length=100)
    other = models.CharField(max_length=100)
    owner = models.ForeignKey(Owner, null=True, on_delete=models.SET_NULL)

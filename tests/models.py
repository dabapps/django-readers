from django.db import models


class Widget(models.Model):
    name = models.CharField(max_length=100)
    other = models.CharField(max_length=100)

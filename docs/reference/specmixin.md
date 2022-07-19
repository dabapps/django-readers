If you use [django-rest-framework](https://www.django-rest-framework.org/), `django-readers` provides a view mixin that allows you to easily use a [spec](specs.md) to serialize your data:

```python
from django_readers.rest_framework import SpecMixin


class AuthorDetailView(SpecMixin, RetrieveAPIView):
    queryset = Author.objects.all()
    spec = [
        "id",
        "name",
        {
            "book_set": [
                "id",
                "title",
                "publication_date",
            ]
        },
    ]
```

This mixin is only suitable for use with `RetrieveAPIView` or `ListAPIView`. It doesn't use a "real" Serializer: it calls the `project` function that is the result of processing your `spec`. We recommend using separate views for endpoints that modify data, rather than combining these concerns into a single endpoint.

If your endpoint needs to provide dynamic behaviour based on the user making the request, you should instead override the `get_spec` method and return your spec.

If you need to override `get_queryset`, you must call `self.prepare` on the queryset that you return:

```python hl_lines="9"
class GoogleyAuthorListView(SpecMixin, ListAPIView):

    spec = [
       ...,
    ]

    def get_queryset(self):
        queryset = Author.objects.filter(email__contains="google.com")
        return self.prepare(queryset)
```

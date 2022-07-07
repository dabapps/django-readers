This tutorial assumes you understand the basics of Django (models, views, templates etc). If you don't, make sure you've been through [the Django tutorial](https://docs.djangoproject.com/) first. The section on Django REST framework assumes that you understand how REST framework works. Again, make sure you've read [the docs](https://www.django-rest-framework.org/) first.

## Example models

For the purposes of this tutorial, we're going to use a set of models representing **books**, **authors** and **publishers**. In this model, a book has exactly one publisher, but can have many authors. Here are the Django models we're using:


```python
class Publisher(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()


class Author(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()


class Book(models.Model):
    title = models.CharField(max_length=100)
    authors = models.ManyToManyField(Author)
    publisher = models.ForeignKey(Publisher)
    publication_date = models.DateField()
```

We're going to go through a step-by-step set of requirements from an imaginary client who has asked us to build a simple book listing application. We're going to assume the Django project itself has already been set up, and focus on a single view and a single template.

## Requirement 1: a list of book titles (without `django-readers`)

First, the client wants us to build a page containing a list of all of the books in the database, showing only their titles. The "standard" Django approach to this would be as follows:

```python
def book_list(request):
    queryset = Book.objects.all()
    return render("book_list.html", {"books": queryset})
```

```django
<ul>
{% for book in books %}
    <li>
        {{ book.title }}
    </li>
{% endfor %}
</ul>
```

Here we're passing the queryset of books itself into the template, and inside our `for` loop we have instances of the `Book` model. When we iterate over the queryset, a database query something like this will be executed:

```sql
SELECT "books_book"."id",
       "books_book"."title",
       "books_book"."publisher_id",
       "books_book"."publication_date"
FROM "books_book"
```

!!! note
    Notice that the `SELECT` part of the query is fetching more data than it really needs. We only actually need the `title` field, but we're also getting the `id`, `publisher_id` and `publication_date`. This is just how Django's ORM works: it has no way of knowing which fields you need when you run the query, so it just asks for all of them. This isn't normally a problem, but if your model has lots of fields (or large amounts of data in particular fields), it certainly can impact performance. You can control this behaviour with the `.only` and `.defer` queryset methods, but this is a manual optimisation and can be brittle.

## Requirement 2: add the publisher name for each book (without `django-readers`)

Now, the client wants us to show the name of the publisher after the book title. This looks like it should just involve a tweak to the HTML template, so we pass this work over to our frontend developer, who changes the template so it looks like this:

```django hl_lines="5"
<ul>
{% for book in books %}
    <li>
        {{ book.title }}
        published by {{ book.publisher.name }}
    </li>
{% endfor %}
</ul>
```

But there's a problem here. Django's ORM is being asked to _follow a relationship_ (from `Book` to `Publisher` via the `publisher` foreign key). In order to do that, it has to issue another query to the database to fetch all the details of the publisher:

```sql
SELECT "books_publisher"."id",
       "books_publisher"."name",
       "books_publisher"."address"
FROM "books_book"
WHERE "books_book"."id" = 1
```

Because we're following this relationship inside a loop in the template, the ORM will issue a query like this _for each book in the list_. This is the "[N+1 queries problem](https://stackoverflow.com/questions/97197/what-is-the-n1-selects-problem-in-orm-object-relational-mapping)": there's one query to fetch all the books, then N queries (where N is the number of books) to fetch the publisher for each book. This can be disastrous for performance.

Django provides tools to fix this. In this case, we'd probably use the `select_related` queryset method in the view, like this:

```python
def book_list(request):
    queryset = Book.objects.select_related("publisher")
    return render("book_list.html", {"books": queryset})
```

This tells the ORM to issue a `JOIN` to fetch all the data in one query:

```sql
SELECT "books_book"."id",
       "books_book"."title",
       "books_book"."publisher_id",
       "books_book"."publication_date",
       "books_publisher"."id",
       "books_publisher"."name",
       "books_publisher"."address"
FROM "books_book"
LEFT OUTER JOIN "books_publisher"
ON ("books_book"."publisher_id" = "books_publisher"."id")
```

The problem with this is that the view code and the template code are now _coupled_ in a very unpredictable and hard-to-reason-about way. A small, innocuous-looking change to the code in either the view or template can drastically impact the performance. This coupling problem only gets worse as the complexity of the application increases.

!!! note
    YAGNI, "You Aren't Gonna Need It", it's a [well-understood mantra](https://martinfowler.com/bliki/Yagni.html) in software development. It means that you should only make changes to your software (including adding abstraction and generalising code structures) when you are sure that you absolutely need them, and not before. Related to this is the famous quote from Donald Knuth: "premature optimization is the root of all evil". This suggests that usually performance concerns fall under YAGNI: you shouldn't spend time making code fast until its slowness becomes a real problem for users.

    As a counterpoint to this advice, Simon Willison coined the phrase [PAGNI](https://simonwillison.net/2021/Jul/1/pagnis/), "Probably Are Gonna Need It". PAGNI applies in situations "when the cost of adding something later is so dramatically expensive compared with the cost of adding it early on that it’s worth taking the risk [...] when you know from experience that an initial investment will pay off many times over."

    `django-readers` (and its sister project `django-zen-queries`) were built partly as a result of a strong belief (gained through many years of experience) that understanding and controlling your application's database querying behaviour firmly falls into the PAGNI category. This is particularly true of applications that you know are going to be complex: any code abstraction patterns you decide to follow in order to manage the complexity _must_ take into account query patterns or they are highly likely to cause terrible performance problems. This is the heart of the [object-relational impedence mismatch](https://en.wikipedia.org/wiki/Object%E2%80%93relational_impedance_mismatch).

`django-readers` takes a different approach. Rather than decoupling queryset building (in the view) from the use of the data (which happens in the template), we instead explicitly perform all data fetching in the view. The template then deals only with presentation: instead of passing a queryset into the template (and allowing the template code to access arbitary attributes or methods on the model instances) we instead extract precisely the data we need from the database, convert it into basic data structures (Python dictionaries) and pass those into the template instead.

This means that template authors can't blindly follow relationships and incur extra queries, because the attributes that express those relationships simply don't exist in the template context unless they are explictly fetched. But to mitigate the burden of having to fine-tune our querysets "by hand" for efficiency, we use a high-level "spec" to describe the fields and relationships we need, and `django-readers` is responsible for building the queryset and converting the model instances into dictionaries.

## Requirement 1 revisited: a list of book titles (with `django-readers`)

Let's go back to our initial requirement: just show a list of book titles. Remember that we only needed the `title` field, but Django wastefully extracted _all_ of the fields on the `Book` model from the database. `django-readers` fixes this:

```python
from django_readers import specs


def book_list(request):
    spec = [
        "title",
    ]
    prepare, project = specs.process(spec)
    queryset = prepare(Book.objects.all())
    return render(
        "book_list.html",
        {"books": [project(book) for book in queryset]},
    )
```

As you can see, at its simplest a `django-readers` spec is just a list of field names. `specs.process` takes the spec and returns a pair of _functions_, which (by convention) we call `prepare` and `project`.

!!! note
    `prepare` and `project` are `django-readers`-specific terms. There is one other `django-readers` concept beginning with P, `produce`, which will be introduced fully later, but here are their rough definitions to set the scene:

    A `prepare` function takes a queryset and returns another queryset with one or more modifications applied (like `prefetch_related` or `only`: just like chaining queryset methods). This process is called "preparing the queryset".

    A `produce` function (a "producer") takes a model instance and returns ("produces") a value derived from that instance. Often this is the value of an attribute on the model.

    A `project` function (a "projector") takes a model instance and returns a dictionary (the "projection") which maps one or more names (the dictionary keys) to one or more values derived from the instance (often the values of one or more attributes and possibly nested dictionaries representing related models). It _projects_ your data layer into your application's business logic domain. Think of the dictionary returned by a projector (the "projection") as the simplest possible domain object. Generally speaking, it's not necessary to write your own projector functions - you can simply wrap a producer function to bind the value it returns to a name.


The `prepare` function is responsible for building the queryset - it takes a queryset as an argument (in this case `Book.objects.all()`) and returns a new queryset which is fine-tuned to fetch only the data we're interested in.

When we evaluate the prepared queryset, Django can now issue a much more optimised query to the database:

```sql
SELECT "books_book"."id",
       "books_book"."title",
FROM "books_book"
```

We still need the ID (Django uses this to track the identity of the model instance so it's always included) but apart from that, we only get the `title` - just what we need.

The `project` function operates on model instances. It takes an instance as its argument and returns a dictionary containing only the fields we've asked for in the spec. So in this case, it might return:

```python
{"title": "Pro Django"}
```

We iterate over the queryset and call this `project` function on each model instance, and pass the resulting list of dictionaries into the template:

```python
[
    {"title": "Pro Django"},
    {"title": "Two Scoops of Django"},
    {"title": "Speed Up Your Django Tests"},
]
```

## Requirement 2 revisited: add the publisher name for each book (with `django-readers`)

Selecting only the required subset of fields from a model is a neat trick, but `django-readers` really comes into its own when dealing with relationships between models. A relationship in a `django-readers` spec is expressed as a dictionary with (usually) a single key and value, the key being the name of the relationship field on the model and the value being another spec, listing the fields we need from the model on the other side of the relationship.

To include the publisher name, our spec would look like this:

```python hl_lines="7-11"
from django_readers import specs


def book_list(request):
    spec = [
        "title",
        {
            "publisher": [
                "name",
            ]
        },
    ]
    prepare, project = specs.process(spec)
    queryset = prepare(Book.objects.all())
    return render(
        "book_list.html",
        {"books": [project(book) for book in queryset]},
    )
```

Now, the `prepare` function (as well as selecting only the `title` field) adds a `prefetch_related` to the `Book` queryset which fetches the related `Publisher`. By providing the list of fields we want from the `Publisher` too, `django-readers` can make sure it efficiently builds the related `Publisher` queryset in just the same way. Now we get two queries, one to fetch the books:

```sql
SELECT "books_book"."id",
       "books_book"."title",
       "books_book"."publisher_id"
FROM "books_book"
```

And one to fetch all the publishers for those books:

```sql
SELECT "books_publisher"."id",
       "books_publisher"."name"
FROM "books_publisher"
WHERE "books_publisher"."id" IN (1, 2, 3)
```

!!! note
    Note that `django-readers` _always_ uses `prefetch_related` to load relationships, even in circumstances where `select_related` would usually be used (ie `ForeignKey` and `OneToOneField`), resulting in one query per relationship. This approach allows the code to be "fractal": the tree of specs can be recursively applied to the tree of related querysets.

    Using `prefetch_related` for foreign key relationships does have some drawbacks: the "join" between books and publishers is performed in Python, rather than in the database, which can be slower and use more memory. Of course, using `prefetch_related` is still much better than doing nothing and emitting N queries!
    
    It is also quite possible to build queries with `django-readers` that _do_ use `select_related` (ie perform joins in the database), but this must be done in a more manual way, which we will cover elsewhere in the docs.

The `project` function then includes the fields we asked for from the related objects too, so after iterating over the queryset and projecting each instance, the value of the `books` variable in the template context will be:

```python hl_lines="4 8 12"
[
    {
        "title": "Pro Django",
        "publisher": {"name": "Apress"},
    },
    {
        "title": "Two Scoops of Django",
        "publisher": {"name": "Two Scoops Press"},
    },
    {
        "title": "Speed Up Your Django Tests",
        "publisher": {"name": "Gumroad"},
    },
]
```

## Requirement 3: Add author names for each book

This requirement is quite straightforward, as it's very similar to the previous requirement.

```django hl_lines="6-11"
<ul>
{% for book in books %}
    <li>
        {{ book.title }}
        published by {{ book.publisher.name }}
        Authors:
        <ul>
        {% for author in book.authors %}
            <li>{{ author.name }}</li>
        {% endfor %}
        </ul>
    </li>
{% endfor %}
</ul>
```

The spec changes to include the new relationship:

```python hl_lines="12-16"
from django_readers import specs


def book_list(request):
    spec = [
        "title",
        {
            "publisher": [
                "name",
            ]
        },
        {
            "authors": [
                "name",
            ]
        },
    ]
    prepare, project = specs.process(spec)
    queryset = prepare(Book.objects.all())
    return render(
        "book_list.html",
        {"books": [project(book) for book in queryset]},
    )
```

As you can see, foreign key relationships and many-to-many relationships are represented in a spec in exactly the same way.

The value of the `books` variable in the template context will now be:

```python hl_lines="5-7 12-15 20-22"
[
    {
        "title": "Pro Django",
        "publisher": {"name": "Apress"},
        "authors": [
            {"name": "Marty Alchin"},
        ],
    },
    {
        "title": "Two Scoops of Django",
        "publisher": {"name": "Two Scoops Press"},
        "authors": [
            {"name": "Daniel Roy Greenfeld"},
            {"name": "Audrey Roy Greenfeld"},
        ],
    },
    {
        "title": "Speed Up Your Django Tests",
        "publisher": {"name": "Gumroad"},
        "authors": [
            {"name": "Adam Johnson"},
        ],
    },
]
```

## Requirement 4: include a count of published books with each publisher

Now, the client wants to include a count of how many books each publisher has published alongside the name of the publisher. How would we accomplish this with `django-readers`?

So far, we've only seen two types of value inside a spec: strings (representing the name of a field on the model) and dictionaries with string keys and list values (representing a relationship to another model).

But we can also completely customise the spec to do whatever we want. This is how `django-readers` scales conceptually from very simple to arbitrarily complex requirements.

`django-readers` comes with a library of functions that can be used to add commonly-used aggregations to a spec, such as counting related objects. We add these to a spec using the same single-key-dictionary syntax.

```python hl_lines="10"
from django_readers import pairs, specs


def book_list(request):
    spec = [
        "title",
        {
            "publisher": [
                "name",
                {"published_book_count": pairs.count("book")},
            ]
        },
        {
            "authors": [
                "name",
            ]
        },
    ]
    prepare, project = specs.process(spec)
    queryset = prepare(Book.objects.all())
    return render(
        "book_list.html",
        {"books": [project(book) for book in queryset]},
    )
```

## Requirement 5: identifying "vintage" books

The client has a new requirement: for books that were published more than five years ago, they want to add a "vintage" label alongside the book title.

There are a few places we could put the business logic to implement this requirement, including in the view and in the template. Common best practice in the Django community would be to put this logic in a method on the `Book` model, like this:

```python hl_lines="1 10-13"
from datetime import date


class Book(models.Model):
    title = models.CharField(max_length=100)
    authors = models.ManyToManyField(Author)
    publisher = models.ForeignKey(Publisher)
    publication_date = models.DateField()

    def is_vintage(self):
        years_since_publication = date.today().year - self.publication_date.year
        return years_since_publication > 5
```

Putting business logic on the model is known as a "fat models" approach. However, experience has shown that there are problems with this, particularly in larger codebases (see [the Explanation page](explanation.md) for details).

`django-readers` encourages you to put logic like this in a standalone function. This function takes a model instance as its argument and returns a value. As described above, we call this type of function a `producer`.

```python
from datetime import date


def produce_is_vintage(book):
    years_since_publication = date.today().year - book.publication_date.year
    return years_since_publication > 5
```

Now, in order to make our database query efficient, we need to identify the _data dependencies_ of this producer function. Which fields from the model does it need to do its work? We can see that it uses one field from the model: the `publication_date`. So, we need to create a _queryset function_ that includes this field in the query. `django-readers` comes with a library of functions under `django_readers.qs` that help with creating queryset functions. In this case, we need the `include_fields` function:

```python hl_lines="2 5"
from datetime import date
from django_readers import qs


prepare_is_vintage = qs.include_fields("publication_date")


def produce_is_vintage(book):
    years_since_publication = date.today().year - book.publication_date.year
    return years_since_publication > 5
```

Finally, to express the dependency between the producer function and the queryset function, we put the two functions together in a tuple which we call a _reader pair_ (or, commonly, just a "pair"):

```python hl_lines="13"
from datetime import date
from django_readers import qs


prepare_is_vintage = qs.include_fields("publication_date")


def produce_is_vintage(book):
    years_since_publication = date.today().year - book.publication_date.year
    return years_since_publication > 5


is_vintage = (prepare_is_vintage, produce_is_vintage)
```

Now we have a created our custom pair, we can use it in our spec. We again use the dictionary syntax:

```python hl_lines="1-13 30"
from datetime import date
from django_readers import pairs, qs, specs


prepare_is_vintage = qs.include_fields("publication_date")


def produce_is_vintage(book):
    years_since_publication = date.today().year - book.publication_date.year
    return years_since_publication > 5


is_vintage = (prepare_is_vintage, produce_is_vintage)


def book_list(request):
    spec = [
        "title",
        {
            "publisher": [
                "name",
                {"published_book_count": pairs.count("book")},
            ]
        },
        {
            "authors": [
                "name",
            ]
        },
        {"is_vintage": is_vintage}
    ]
    prepare, project = specs.process(spec)
    queryset = prepare(Book.objects.all())
    return render(
        "book_list.html",
        {"books": [project(book) for book in queryset]},
    )
```

!!! note
    For this example, we've put the code for the pair (the prepare and produce function) in the same Python file as the view function. You may choose to put your `django-readers` code in a separate file, perhaps called `readers.py`. You can follow whichever naming convention makes sense for your project layout.

The value of the `books` variable in the template context will now be:

```python hl_lines="11 23 34"
[
    {
        "title": "Pro Django",
        "publisher": {
            "name": "Apress",
            "published_book_count": 1,
        },
        "authors": [
            {"name": "Marty Alchin"},
        ],
        "is_vintage": True,
    },
    {
        "title": "Two Scoops of Django",
        "publisher": {
            "name": "Two Scoops Press",
            "published_book_count": 1,
        },
        "authors": [
            {"name": "Daniel Roy Greenfeld"},
            {"name": "Audrey Roy Greenfeld"},
        ],
        "is_vintage": True,
    },
    {
        "title": "Speed Up Your Django Tests",
        "publisher": {
            "name": "Gumroad",
            "published_book_count": 1,
        },
        "authors": [
            {"name": "Adam Johnson"},
        ],
        "is_vintage": False,
    },
]
```

## Requirement 6: add an API endpoint to list books

Our client has now decided that it's time to build a JavaScript frontend for their website, and wants us to expose the data via an API endpoint rather than rendering the HTML on the server.

The best way to build APIs with Django is to use [Django REST framework](https://www.django-rest-framework.org/). `django-readers` provides a mixin which allows us to use a spec to define the "shape" of the data that we want our endpoint to return. As we've already seen, `django-readers` will extract this data from the database as efficiently as it can. This makes it very quick to build endpoints without compromising on performance.

We're going to illustrate this by re-using the spec from above. To avoid repeating the example code again, we're going to assume that the `is_vintage` pair is defined already.

```python
from django_readers.rest_framework import SpecMixin
from rest_framework.generics import ListAPIView


class BookListView(SpecMixin, ListAPIView):
    queryset = Book.objects.all()
    spec = [
        "title",
        {
            "publisher": [
                "name",
                {"published_book_count": pairs.count("book")},
            ]
        },
        {
            "authors": [
                "name",
            ]
        },
        {"is_vintage": is_vintage},
    ]
```

That's it! Once we've wired up this view in our `urls.py` we can start making requests to it. The JSON data returned from this endpoint will be exactly the same "shape" as the template context above:

```
GET /api/books/

HTTP 200 OK
Allow: GET, HEAD, OPTIONS
Content-Type: application/json
Vary: Accept
```

```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "title": "Pro Django",
      "publisher": {
        "name": "Apress",
        "published_book_count": 1
      },
      "authors": [
        {
          "name": "Marty Alchin"
        }
      ],
      "is_vintage": true
    },
    {
      "title": "Two Scoops of Django",
      "publisher": {
        "name": "Two Scoops Press",
        "published_book_count": 1
      },
      "authors": [
        {
          "name": "Daniel Roy Greenfeld"
        },
        {
          "name": "Audrey Roy Greenfeld"
        }
      ],
      "is_vintage": true
    },
    {
      "title": "Speed Up Your Django Tests",
      "publisher": {
        "name": "Gumroad",
        "published_book_count": 1
      },
      "authors": [
        {
          "name": "Adam Johnson"
        }
      ],
      "is_vintage": false
    }
  ]
}
```

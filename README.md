django-readers
==============

**A lightweight function-oriented toolkit for better organisation of business logic and efficient selection and projection of data in Django projects.**

Tested against Django 2.2, 3.2 and 4.0 on Python 3.6, 3.7, 3.8, 3.9 and 3.10

![Build Status](https://github.com/dabapps/django-readers/workflows/CI/badge.svg?branch=main)
[![pypi release](https://img.shields.io/pypi/v/django-readers.svg)](https://pypi.python.org/pypi/django-readers)

## Installation

Install from PyPI

    pip install django-readers

## Documentation

You can read the documentation at [https://www.django-readers.org](https://www.django-readers.org).

## Working on django-readers

After cloning the repo:

```shell
python -m venv env
source env/bin/activate
pip install -r dev-requirements.txt
```

(the following commands assume you have the virtualenv activated)

Running tests:

```shell
./runtests
```


Running code autoformatters:

```shell
./format
```

Working on the docs (built with [MkDocs](https://www.mkdocs.org/) and [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)):

```shell
pip install -r docs-requirements.txt
mkdocs serve
```

## Code of conduct

For guidelines regarding the code of conduct when contributing to this repository please review [https://www.dabapps.com/open-source/code-of-conduct/](https://www.dabapps.com/open-source/code-of-conduct/)

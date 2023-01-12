# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Add support for Django 4.1
- Drop support for Django 2.2

### Added
- In the Django REST framework layer, callables in a spec are now automatically called and passed the `request` object ([#76](https://github.com/dabapps/django-readers/pull/76))
- Supported added for generating a Django REST framework serializers from a spec, and for annotating custom pairs in a spec with their output field types. This enables automatic schema generation. ([#76](https://github.com/dabapps/django-readers/pull/76))

## [2.0.0] - 2022-07-19

### Changed
- **BACKWARDS INCOMPATIBLE**: The default value of the `distinct` argument for the `pairs.count` and `pairs.has` functions has changed from `True` to `False`. This now matches the default value of the `distinct` arguments to Django's `Count` annotation. To retain current behaviour, add `distinct=True` to all calls to these two functions in your codebase. For background on this decision, see [this discussion](https://github.com/dabapps/django-readers/discussions/66).

### Added
- Proper documentation! [https://www.django-readers.org](https://www.django-readers.org)
- New `pairs.annotate` function allowing you to annotate a queryset with aggregates, functions etc and produce the result.
- New `pairs.sum` function to annotate a queryset with the `Sum` aggregate function and produce the result.

## [1.1.0] - 2022-02-23

### Added
- New `pairs.discard_queryset_function` and `pairs.discard_projector` functions to discard one or other item in a reader pair.

### Changed
- `SpecMixin` now applies prepare function in `get_queryset`, not `filter_queryset`

## [1.0.0] - 2021-10-13

Initial stable release.

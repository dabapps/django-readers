# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New `pairs.discard_queryset_function` and `pairs.discard_projector` functions to discard one or other item in a reader pair.

### Changed
- `SpecMixin` now applies prepare function in `get_queryset`, not `filter_queryset`

## [1.0.0] - 2021-10-13

Initial stable release.

# Changelog

This project follows [Semantic Versioning](https://semver.org/). Release PRs update this changelog before publication.

## [Unreleased]

## 1.0.0 (2026-09-18)

These notes include the unpublished 0.5.0 work and later changes since PyPI 0.4.0.

### Breaking changes

- Use Python 3.11 or later. Python 3.9 and 3.10 are no longer supported.
- Read datum metadata from `station.datums`. `datums` is not a supported Data API product.
- Use `if not station.data_inventory` to detect an unavailable inventory. The attribute now always exists, even after a SOAP failure.

### Features

- Fetch derived products with `Station.get_derived_product()`. Supported products include sea level trends, projections, flood counts, extreme water levels, and regional frequency analysis.
- Fetch daily extrema with `Station.get_data(product="daily_max_min")`. Use `max_min_type` to select minima or maxima. The default interval is hourly.
- Import `COOPSAPIError` directly from `noaa_coops`. The existing import from `noaa_coops.station` remains available.
- Retain harmonic constituents, superseded datums, and additional station metadata fields.
- Access offsets for every current-prediction bin through `current_pred_offsets_by_bin`.

### Fixes

- Reject invalid derived-product parameters before a network request.
- Require a datum for `ofs_water_level` requests.
- Raise `COOPSAPIError` for NOAA error payloads returned with HTTP 200.
- Respect product-specific limits when splitting requests into date ranges. One-minute predictions use a 30-day limit.
- Avoid empty final requests when a date range divides evenly into request blocks.
- Preserve tide-prediction offsets for stations without datums. Correct the metadata request parameters for offsets and units.
- Use consistent columns for daily extrema returned at different intervals.
- Retry transient REST and SOAP errors. Apply timeouts to HTTP requests.
- Report partial date-range failures with a warning and `DataFrame.attrs["missing_blocks"]`.
- Combine response blocks once instead of repeatedly copying accumulated data.
- Handle missing SOAP inventory fields without an uncaught `KeyError`.
- Raise `ValueError` for unsupported date formats.

### Development

- Build packages with `uv` and Hatchling.
- Run offline product tests with recorded NOAA responses.
- Run lint, type checks, and tests for Python 3.11 through 3.13 in CI.
- Run a nightly live SOAP inventory test and track failures in GitHub issues.
- Prepare reviewed release PRs with automated version bumps and release notes.
- Publish release artifacts through `uv` with PyPI Trusted Publishing.

## 0.4.0 - 2024-08-03

The last published version before the release automation setup is [0.4.0 on PyPI](https://pypi.org/project/noaa-coops/0.4.0/).

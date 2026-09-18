# Changelog

This project follows [Semantic Versioning](https://semver.org/). Release PRs update this changelog before publication.

## Unreleased

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

## 1.0.0 (2026-09-18)


### ⚠ BREAKING CHANGES

* drop Python 3.10 support ahead of its October 2026 end of life

### Features

* add CITATION.cff for software citation support ([#71](https://github.com/GClunies/noaa_coops/issues/71)) ([f0db03e](https://github.com/GClunies/noaa_coops/commit/f0db03e5beebee11f159fff2b6a0674792c2f51a))
* add DPAPI derived-product support via Station.get_derived_product() ([#4](https://github.com/GClunies/noaa_coops/issues/4)) ([1e3d4ee](https://github.com/GClunies/noaa_coops/commit/1e3d4ee98a136797b2c760780645374ff34c2335))
* **api:** add daily_max_min product support and fix json dispatch ([a141783](https://github.com/GClunies/noaa_coops/commit/a1417836573e35702f114d2aca6934d0386e3775))
* drop Python 3.10 support ahead of its October 2026 end of life ([0c77dee](https://github.com/GClunies/noaa_coops/commit/0c77dee0fda803573bffd270d8fc879280beb6fc))
* rename RFA product alias, reject htf_seasonal/annual dates, reset DataFrame indexes ([80c3736](https://github.com/GClunies/noaa_coops/commit/80c3736997010c4cc74bc9ff9a2d7d1a815ee9d6))
* route SOAP DataInventory through retrying session ([6e74863](https://github.com/GClunies/noaa_coops/commit/6e74863d1ef197d74fbe9d598c3b41593e813dc2))
* validate scenario parameter for slr_projections ([acdbae6](https://github.com/GClunies/noaa_coops/commit/acdbae6f38afac425a8d8c3071476714a38f1c2e))


### Bug Fixes

* add missing product daily_max_min in ALL_PRODUCTS, add PRODUCT_LIMITS ([178323e](https://github.com/GClunies/noaa_coops/commit/178323eceb694fae05d6d41c4941d45ca6e93214))
* add missing product daily_max_min to product registry and add PRODUCT_LIMITS to _products.py ([b7f71a2](https://github.com/GClunies/noaa_coops/commit/b7f71a269d785524f856c266d44a155494b7802e))
* add ofs_water_level to DATUM_REQUIRED set ([a6fe700](https://github.com/GClunies/noaa_coops/commit/a6fe700172ef613fe6e8e9f817d1743d6fd40bcf))
* **changelog:** update PRODUCT_LIMITS usage and pagination support to unreleased section ([8d685bb](https://github.com/GClunies/noaa_coops/commit/8d685bb92a8527b4d67395ce1d8660ee2a46bc96))
* correct per-product pagination limits, add support for one_minute_water_level and reduce API calls ([1327cfb](https://github.com/GClunies/noaa_coops/commit/1327cfb4938da22f77e53483ba2c386b01a5ad6c))
* **daily_max_min:** add ruff formatting, drop duplicate product guard, update validators for testing ([701e1c0](https://github.com/GClunies/noaa_coops/commit/701e1c0d45fbae402d46b7b18dc48fc001217467))
* **examples:** use a dynamic date window for currents demos ([a35944e](https://github.com/GClunies/noaa_coops/commit/a35944e91d69a835e3e7d3f1629dd23c120bfe32))
* **examples:** use dynamic date window for currents demos ([ed28592](https://github.com/GClunies/noaa_coops/commit/ed28592ec10690650f1ff7a99f486b166aebd04e))
* improve URL building error handling and update product parameters, remove datums (not supported by datagetter endpoint) ([9d13eda](https://github.com/GClunies/noaa_coops/commit/9d13eda6473d6e79100f02164d7fd8be85b63950))
* keep public product name in DPAPI no-list error message ([16acf78](https://github.com/GClunies/noaa_coops/commit/16acf78943ac987390a0417c64fdcf50197b2f3c))
* **metadata:** fix station-type misclassification, restore lost offsets, and multi-bin data loss ([ef0e6e9](https://github.com/GClunies/noaa_coops/commit/ef0e6e9ee693424f0c0146706ff8f9fe8b9dde3c))
* **metadata:** store all station attributes and stop dropping records ([0b8d183](https://github.com/GClunies/noaa_coops/commit/0b8d183ca82243fe2d318800ed040813825b560f))
* **pagination:** use PRODUCT_LIMITS for per-product block sizes ([05d98dc](https://github.com/GClunies/noaa_coops/commit/05d98dc50d6d1a243425053edbc8ae0c4cf2d8b9))
* raise clear COOPSAPIError when a DPAPI response has no list to parse ([65a7723](https://github.com/GClunies/noaa_coops/commit/65a77237c46e84d5603736462c1c6444beb280c5))
* raise clear COOPSAPIError when a DPAPI response has no list to parse ([6ed3ded](https://github.com/GClunies/noaa_coops/commit/6ed3ded72be2495cedf377f397998faa066c683d)), closes [#113](https://github.com/GClunies/noaa_coops/issues/113)
* raise COOPSAPIError on non-200 mdapi responses ([4d0c140](https://github.com/GClunies/noaa_coops/commit/4d0c140557574eee6a993a38332bdfda41dbf267))
* raise COOPSAPIError on non-200 mdapi responses ([64f30af](https://github.com/GClunies/noaa_coops/commit/64f30af2a9711bfd6ccbbac2500dd079bb85b6b7))
* raise KeyError for unexpected record keys in daily_max_min flattener ([97cddff](https://github.com/GClunies/noaa_coops/commit/97cddff498d1952be0569fced4e7dd32c6ad6305))
* raise KeyError for unexpected record keys in daily_max_min flattener ([998246a](https://github.com/GClunies/noaa_coops/commit/998246a17465d9d5e022af23b35151197d7f1072)), closes [#115](https://github.com/GClunies/noaa_coops/issues/115)
* require datum for ofs_water_level product ([4023585](https://github.com/GClunies/noaa_coops/commit/4023585d6e8c32f0db9bfa0a3cfd53645f35e8ce))
* restore 200-with-error check, fix fetch_in_blocks max_min_type passthrough, map record_type to min/max ([c615b49](https://github.com/GClunies/noaa_coops/commit/c615b496847f4ca77b1dd4070f6e50d540b1130e))
* **station:** skip SOAP DataInventory for non-7-digit station IDs ([263317b](https://github.com/GClunies/noaa_coops/commit/263317b33149354f672e608ce04c169f4ed1715f))
* validate affil, projection_year, report_year, and year in DPAPI requests ([6ecc85e](https://github.com/GClunies/noaa_coops/commit/6ecc85e20801458809c22a26d82dec7ae8953af8))
* validate affil, projection_year, report_year, and year in DPAPI requests ([daf8e0c](https://github.com/GClunies/noaa_coops/commit/daf8e0c91a77db7fae16229e8001a98a3605d866)), closes [#112](https://github.com/GClunies/noaa_coops/issues/112)

## 0.4.0 - 2024-08-03

The last published version before the release automation setup is [0.4.0 on PyPI](https://pypi.org/project/noaa-coops/0.4.0/).

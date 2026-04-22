# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.0] - 2026-04-22

Major modernization release. Every layer of the project was touched — build
system, CI/CD, internal structure, testing, and docs. Behavior for existing
users is almost entirely unchanged; two small backward-compatible behavioral
changes are called out under *Changed* below.

### Added

- **Module-level HTTP session** with automatic retries on transient failures
  (`429`, `500`, `502`, `503`, `504`) via a `urllib3.util.retry.Retry` adapter
  (`noaa_coops/_http.py`). All calls — including `get_stations_from_bbox` —
  share the session's connection pool and retry policy.
- **Warn-and-continue** behavior on multi-block fetches: when one block in a
  multi-month fetch fails, a `RuntimeWarning` is emitted and
  `df.attrs["missing_blocks"]` is populated with `{begin, end, error}` entries
  instead of silently dropping the block.
- **Declarative product registry** (`noaa_coops/_products.py`) replacing the
  historical 186-line `_check_product_params` if/elif tree + 150-line
  `_build_request_url` if/elif tree. Adding a new NOAA product is now a
  one-place change.
- **Public export**: `COOPSAPIError` is now importable as
  `from noaa_coops import COOPSAPIError` (the old
  `from noaa_coops.station import COOPSAPIError` path still works).
- **Offline test suite** using [pytest-recording](https://github.com/kiwicom/pytest-recording)
  VCR cassettes. Default `pytest` runs in ~1.5s with zero network calls.
- **Nightly live canary** (`.github/workflows/nightly.yml`) runs `pytest -m
  live` daily at 06:00 UTC. On failure, opens a tracking issue so NOAA drift
  is visible without flooding the inbox.
- **Manual publish workflows** mirroring the PyPA pattern:
  `.github/workflows/test-publish.yml` publishes to TestPyPI,
  `.github/workflows/publish.yml` publishes to PyPI + creates the
  `v{VERSION}` tag + cuts a GitHub Release with an auto-generated changelog
  from `git log`. Both `workflow_dispatch`.
- **Dependabot** configured for `github-actions` and the `uv` ecosystems.
- **pre-commit** hooks (`.pre-commit-config.yaml`) — ruff check + format +
  standard hygiene hooks. Free auto-fix PRs via pre-commit.ci.

### Changed

- **Build backend swapped to hatchling.** Version is read from
  `noaa_coops/__init__.py` by `hatchling.build`. No more `poetry-core`.
- **CI swapped to `uv` + `hatchling`.** Jobs: `lint` (ruff), `typecheck`
  (mypy), and `test` (pytest matrix across Python 3.10 – 3.13 on
  `ubuntu-latest`).
- **Added HTTP timeouts everywhere.** Every `requests.get` / `_SESSION.get`
  passes `timeout=(5.0, 30.0)` (connect, read). No more hangs on stalled NOAA
  endpoints.
- **Narrower exception handling.** Bare `except:` in `Station.__init__`
  replaced with `(requests.RequestException, zeep.exceptions.Error,
  AttributeError, TypeError)` + a `logging.warning`. `KeyboardInterrupt` and
  `SystemExit` now propagate correctly.
- **Internal module split.** `station.py` shrunk from 825 lines to ~350.
  New internal modules: `_exceptions.py`, `_endpoints.py`, `_http.py`,
  `_parsing.py`, `_products.py`, `_metadata.py`, plus the public `api.py`.
  All previous import paths continue to work.
- **`pyproject.toml` converted to PEP 621** `[project]` table with
  classifiers, keywords, and `[project.urls]` so the PyPI page renders useful
  metadata.
- **`station.data_inventory` is always set.** An empty dict `{}` now
  indicates either (a) the station ID is not eligible for SOAP
  `DataInventory` — NOAA only supports 7-digit numeric IDs, so
  currents/PORTS stations like `s09010` always produce `{}` by design —
  or (b) an eligible ID had a transient SOAP failure. Callers using
  `hasattr(station, 'data_inventory')` should switch to
  `if not station.data_inventory:`.
- **SOAP `DataInventory` retries transient failures.** Calls now go through
  a dedicated `requests.Session` (`_SOAP_SESSION`) that retries POST as
  well as GET on `429`/`5xx` responses. Gives the data-inventory path the
  same resiliency the REST path already had.
- **Skip SOAP `DataInventory` for non-7-digit station IDs.**
  `Station.__init__` now short-circuits the SOAP call for alphanumeric
  currents/PORTS IDs (e.g. `s09010`, `PUG1515`) that NOAA's SOAP service
  would reject deterministically with a `Wrong Station ID` fault. Emits a
  single `logging.INFO` message explaining the skip so users debugging an
  empty `data_inventory` can see it's expected, without warning-level
  noise on every currents `Station(...)`.

### Fixed

- **O(n²) memory in multi-block fetches.** The multi-block loop used to
  rebuild the full DataFrame on every iteration via
  `df = pd.concat([df, df_block])`. Now appends to a list and concatenates
  once at the end.
- **Silent `KeyError` crash in `get_data_inventory`.** If the SOAP response
  lacked a `"parameter"` key, the error escaped the narrow catch in
  `Station.__init__` and crashed construction. Now handled locally via
  `try/except (KeyError, TypeError)`.
- **`_parse_known_date_formats` `UnboundLocalError` trap.** The old
  `match = False` flag pattern (set only in the `except` branch) could raise
  `UnboundLocalError` in edge cases. Rewritten as a clean for/try/continue
  loop that raises `ValueError` after exhausting all known formats.
- **`stale --cov=reflekt` config.** pytest coverage was pointing at the
  wrong project. Fixed to `--cov=noaa_coops`.
- **`examples/readme_demo.py` currents demo.** Replaced the hardcoded
  `20210414-15` window (for which NOAA no longer returns data at station
  `s09010`) with a computed two-day UTC window ending yesterday, so the
  demo stays fresh against NOAA's rolling real-time availability.

### Removed

- **Python 3.9 support.** 3.9 went EOL in October 2025 and the modern testing
  stack (vcrpy 8.x, urllib3 2.x, types-requests 2.32.4+) requires ≥3.10.
  Supported versions: 3.10, 3.11, 3.12, 3.13.
- **Dead files.** `.bumpversion.cfg` (stuck at `0.1.9` targeting nonexistent
  `setup.py`), `.flake8` (superseded by ruff), `mypy.ini` (migrated into
  `pyproject.toml`), `pytest.ini` (same), old `poetry.lock`, and a 96-line
  `if __name__ == "__main__":` debug block in `station.py`.
- **Third-party publish action.** Replaced `JRubics/poetry-publish` with the
  PyPA-official `pypa/gh-action-pypi-publish`.
- **`examples/currents_example.py`** — consolidated into
  `examples/readme_demo.py`, which already exercised the same Oakland
  currents scenario. `readme_demo.py` is now the single entry point for the
  full feature set.

## [0.4.0] - 2023-xx-xx

Earlier releases are documented in the
[GitHub release history](https://github.com/GClunies/noaa_coops/releases).

<!-- Links -->
[Unreleased]: https://github.com/GClunies/noaa_coops/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/GClunies/noaa_coops/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/GClunies/noaa_coops/releases/tag/v0.4.0

# Contributing

Thanks for wanting to contribute.

## Development environment

This project uses [uv](https://docs.astral.sh/uv/) and [hatchling](https://hatch.pypa.io/latest/).
Install `uv`, then:

```bash
git clone https://github.com/GClunies/noaa_coops.git
cd noaa_coops
uv sync --locked --all-extras --group dev
```

That creates a `.venv/` and installs the runtime deps plus the dev toolchain
(`pytest`, `pytest-cov`, `pytest-recording`, `mypy`, `ruff`, `responses`,
type stubs).

## Running tests

```bash
# Default: offline, deterministic, <2s. Replays recorded VCR cassettes.
uv run pytest

# Run the nightly live canary locally (hits the real NOAA API):
uv run pytest -m live

# Re-record cassettes after intentional NOAA drift or a new test:
uv run pytest --record-mode=rewrite           # rebuild every cassette
uv run pytest --record-mode=new_episodes      # record only new calls
```

Cassettes live at `tests/cassettes/test_station/*.yaml`. Commit them
alongside any test changes that touch the live path.

## Lint, format, typecheck

```bash
uv run ruff check .
uv run ruff format .
uv run mypy noaa_coops
```

These all run in CI on every PR. Pre-commit is also wired up via
[pre-commit.ci](https://pre-commit.ci) — style issues get auto-fixed on
inbound PRs.

## Pull request checklist

Before requesting review:

- [ ] Tests pass: `uv run pytest`
- [ ] Ruff clean: `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Mypy clean: `uv run mypy noaa_coops`
- [ ] New or modified behavior has test coverage
- [ ] If you touched the live API path, re-recorded cassettes
- [ ] PR description explains the why, not just the what

## Release process

Releases are cut manually via the GitHub Actions UI.

1. Bump `__version__` in `noaa_coops/__init__.py` (e.g. `0.5.0` → `0.6.0`).
2. Update `CHANGELOG.md` — move the **Unreleased** section under the new
   version with today's date, and start a fresh `## [Unreleased]` header.
3. PR, review, merge to `main`.
4. Actions → **Test Publish** → *Run workflow*. Confirms the wheel installs
   cleanly from TestPyPI.
5. Actions → **Publish** → *Run workflow*. Publishes to PyPI, creates the
   `v{VERSION}` git tag, and cuts a GitHub Release with a changelog
   auto-generated from `git log $PREV_TAG..HEAD`.

Each step validates semver format and refuses to run if the tag already
exists.

## Nightly canary

`.github/workflows/nightly.yml` runs `pytest -m live` on a daily cron. If it
fails, it opens (or updates) a `nightly-canary`-labeled issue — real NOAA
drift is visible without spamming the inbox.

## Reporting bugs

Open an [issue](https://github.com/GClunies/noaa_coops/issues) with the bug
report template. Include the Python version, `noaa_coops` version, and a
minimal reproduction.

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

```text
Merge a feature or fix PR
    → Release Please updates the release PR
    → Review the version and changelog after CI passes
    → Merge the release PR
    → Create the tag and GitHub release
    → Test and build the tagged source
    → Publish the same artifacts to PyPI with uv
    → Verify installation from PyPI
```

### Version policy

The first stable release is 1.0.0. Later releases follow [Semantic Versioning](https://semver.org/).

| Change | PR title example | Release |
| --- | --- | --- |
| Compatible bug fix | `fix: preserve tide prediction offsets` | Patch |
| Compatible performance improvement | `perf: reduce memory use for long requests` | Patch |
| Compatible feature | `feat: add a derived products client` | Minor |
| Incompatible API or Python support change | `feat!: require Python 3.12 or later` | Major |
| Internal tests, documentation, or tooling | `test: cover missing datum validation` | No release by itself |

Use Conventional Commits for PR titles. Squash-merge PRs so their titles become commit subjects. Keep each title focused on one user-visible outcome.

For a breaking change, add `!` to the title and a `BREAKING CHANGE:` paragraph to the PR body. Explain the incompatibility and the required migration. Preserve that paragraph in the squash commit message.

Review compatibility, not only commit labels. Removed methods, changed return schemas, and dropped Python versions require a major release after 1.0.0. New optional behavior can use a minor release. A correction to documented behavior can use a patch release.

### Release preparation

Release Please maintains one release PR from changes on `main`. The PR updates `pyproject.toml`, `CITATION.cff`, the release manifest, and `CHANGELOG.md`. Automation runs `uv lock` on that branch and starts CI for its final commit.

`pyproject.toml` is the package version source. `noaa_coops.__version__` reads installed distribution metadata. Use `uv sync` before importing the package from a source checkout.

Do not bump versions in ordinary feature PRs. Do not maintain a second set of release notes. Review and correct the generated changelog in the release PR. Later automation updates can regenerate those notes, so verify the final diff before merging.

1. Review the proposed version against the public API changes.

2. Review the changelog for user-visible changes and migration instructions.

3. Verify that CI passed for the latest release PR commit.

4. Squash-merge the release PR without changing its release title.

5. Verify that the Publish workflow succeeds and PyPI lists the expected version.

The first release includes the unpublished 0.5.0 work and subsequent changes. The earlier 0.5.0 changelog heading did not represent a PyPI release.

The initial configuration explicitly requests 1.0.0. Automation removes that override in the first release PR. Later releases use the manifest and Conventional Commits.

### One-time service configuration

Configure these services before merging the first release PR. Repository files cannot register a PyPI Trusted Publisher.

| Service | Required configuration |
| --- | --- |
| GitHub Actions | Allow Actions to create pull requests. The workflows declare their required permissions. |
| GitHub merge configuration | Enable squash merges. Disable merge commits and rebase merges. Use the PR title and body for squash commit messages. |
| GitHub branch protection | Require a pull request and current CI checks before merging to `main`. Include the PR title check. |
| GitHub tag protection | Protect `v*` tags against updates and deletion. Allow the release workflow to create tags. |
| GitHub environment `pypi` | Allow tags matching `v*` only. Require maintainer approval. |
| GitHub environment `testpypi` | Allow branches matching `release-please--branches--main*` only. Require maintainer approval. |
| PyPI Trusted Publisher | Project `noaa-coops`, owner `GClunies`, repository `noaa_coops`, workflow `publish.yml`, environment `pypi`. |
| TestPyPI Trusted Publisher | Project `noaa-coops`, owner `GClunies`, repository `noaa_coops`, workflow `test-publish.yml`, environment `testpypi`. |

The workflows use `uv publish --trusted-publishing always`. They do not use `PYPI_TOKEN` or `TEST_PYPI_TOKEN`. After Trusted Publishing succeeds, remove the unused token secrets and revoke their tokens.

See the [PyPI registration guide](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) and the [uv publication guide](https://docs.astral.sh/uv/guides/package/).

### TestPyPI rehearsal

Run **Test Publish** manually against the release PR branch before merging. Supply its full commit SHA as `expected_sha`. This optional rehearsal does not create a production release. TestPyPI requires its own Trusted Publisher registration.

### Failures and retries

A GitHub release exists before PyPI publication. Its existence does not prove that PyPI received the package. The Publish workflow verifies the tagged commit and installs the published version before reporting success.

If publication fails, use **Re-run failed jobs** on the original workflow run. The retry uses the retained build artifacts. Do not move the tag or change files under the same version.

If automatic dispatch fails, run **Publish** manually against the existing version tag. Supply that tag and its full commit SHA. The workflow rejects a different commit or inconsistent package metadata.

If PyPI already contains a file, only identical bytes are safe to retry. A conflicting file requires investigation, not an overwrite. If retained artifacts expire, recover the original artifacts before retrying a partial upload.

If installation verification fails after upload, verify PyPI availability before retrying. The upload can succeed even when a later verification step fails.

## Nightly canary

`.github/workflows/nightly.yml` runs `pytest -m live` on a daily cron. If it
fails, it opens (or updates) a `nightly-canary`-labeled issue — real NOAA
drift is visible without spamming the inbox.

## Reporting bugs

Open an [issue](https://github.com/GClunies/noaa_coops/issues) with the bug
report template. Include the Python version, `noaa_coops` version, and a
minimal reproduction.

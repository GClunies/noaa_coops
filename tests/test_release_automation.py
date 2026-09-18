from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import textwrap
import tomllib
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "release.py"


def run_pr_validation(
    title: str, body: str = "", actor: str = "", head_ref: str = ""
) -> subprocess.CompletedProcess[str]:
    workflow = SCRIPT.parents[1] / ".github" / "workflows" / "pull_request.yml"
    inline = (
        workflow.read_text()
        .split("python - <<'PY'\n", 1)[1]
        .split("\n          PY", 1)[0]
    )
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(inline)],
        env=os.environ
        | {
            "PR_TITLE": title,
            "PR_BODY": body,
            "PR_ACTOR": actor,
            "PR_HEAD": head_ref,
        },
        text=True,
        capture_output=True,
        check=False,
    )


def run_release(
    *args: str, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    "title",
    [
        "fix: reject stale release dispatches",
        "feat(release)!: require stable tags",
        "chore(deps): update uv",
    ],
)
def test_validate_pr_accepts_conventional_titles(title: str) -> None:
    result = run_pr_validation(title, "BREAKING CHANGE: Migrate now.")

    assert result.returncode == 0, result.stderr


def test_validate_pr_rejects_nonconventional_title() -> None:
    result = run_pr_validation("Update release workflow")

    assert result.returncode != 0
    assert "Conventional Commit" in result.stderr


def test_validate_pr_requires_breaking_migration_paragraph() -> None:
    result = run_pr_validation("feat!: remove legacy API", "BREAKING CHANGE:\n\n")

    assert result.returncode != 0
    assert "migration" in result.stderr


def test_validate_pr_allows_canonical_release_please_bot_pr() -> None:
    result = run_pr_validation(
        "chore(main): release 1.0.0",
        actor="github-actions[bot]",
        head_ref="release-please--branches--main--components--noaa-coops",
    )

    assert result.returncode == 0, result.stderr


def write_release_repository(root: Path, version: str = "1.2.3") -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "noaa-coops"\nversion = "{version}"\n'
    )
    (root / "CITATION.cff").write_text(f'version: "{version}"\n')
    (root / "uv.lock").write_text(
        f'version = 1\n[[package]]\nname = "noaa-coops"\nversion = "{version}"\n'
    )
    (root / ".release-please-manifest.json").write_text(json.dumps({".": version}))
    (root / "release-please-config.json").write_text('{"packages": {".": {}}}')
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{version}] - 2026-09-18\n\n### Fixed\n\n- Correct release validation.\n\n## [1.2.2]\n"
    )


def test_validate_repository_checks_all_version_sources_and_release_notes(
    tmp_path: Path,
) -> None:
    write_release_repository(tmp_path)
    notes = tmp_path / "notes.md"
    notes.write_text(
        "## [1.2.3] - 2026-09-18\n\n### Fixed\n\n- Correct release validation.\n"
    )

    result = run_release(
        "validate-repository",
        "--root",
        str(tmp_path),
        "--tag",
        "v1.2.3",
        "--release-notes",
        str(notes),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.2.3"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda root: (root / "CITATION.cff").write_text('version: "1.2.2"\n'),
            "CITATION",
        ),
        (
            lambda root: (root / "uv.lock").write_text(
                'version = 1\n[[package]]\nname = "noaa-coops"\nversion = "1.2.2"\n'
            ),
            "uv.lock",
        ),
        (lambda root: None, "at least 1.0.0"),
    ],
)
def test_validate_repository_rejects_inconsistent_or_prestable_versions(
    tmp_path: Path, mutate, message: str
) -> None:
    version = "0.9.0" if message == "at least 1.0.0" else "1.2.3"
    write_release_repository(tmp_path, version)
    mutate(tmp_path)

    result = run_release(
        "validate-repository", "--root", str(tmp_path), "--tag", f"v{version}"
    )

    assert result.returncode != 0
    assert message in result.stderr


@pytest.mark.parametrize("heading", ["## Unreleased", "## [Unreleased]"])
@pytest.mark.parametrize("generated_first", [True, False])
def test_bootstrap_changelog_uses_trusted_base_notes(
    tmp_path: Path, heading: str, generated_first: bool
) -> None:
    source = tmp_path / "base.md"
    source.write_text(
        f"# Changelog\n\n{heading}\n\n### Features\n\n- Curated capability.\n\n"
        "## 0.4.0 - 2024-08-03\n\n- Previous release.\n"
    )
    changelog = tmp_path / "CHANGELOG.md"
    generated = "## 1.0.0 (2026-09-18)\n\n### Features\n\n- generated duplicate\n\n"
    original = source.read_text()
    changelog.write_text(
        generated + original if generated_first else original + generated
    )
    result = run_release(
        "bootstrap-changelog",
        "--path",
        str(changelog),
        "--source",
        str(source),
        "--version",
        "1.0.0",
    )
    assert result.returncode == 0, result.stderr
    updated = changelog.read_text()
    assert "## [Unreleased]\n\n## 1.0.0 (2026-09-18)" in updated
    assert updated.count("- Curated capability.") == 1
    assert "generated duplicate" not in updated
    assert "- Previous release." in updated
    repeat = run_release(
        "bootstrap-changelog",
        "--path",
        str(changelog),
        "--source",
        str(source),
        "--version",
        "1.0.0",
    )
    assert repeat.returncode == 0, repeat.stderr
    assert changelog.read_text() == updated


def test_validate_artifacts_checks_wheel_and_sdist_metadata(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "noaa_coops-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "noaa_coops-1.2.3.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: noaa-coops\nVersion: 1.2.3\n",
        )
    pkg_info = tmp_path / "PKG-INFO"
    pkg_info.write_text("Metadata-Version: 2.4\nName: noaa-coops\nVersion: 1.2.3\n")
    with tarfile.open(dist / "noaa_coops-1.2.3.tar.gz", "w:gz") as archive:
        archive.add(pkg_info, arcname="noaa_coops-1.2.3/PKG-INFO")

    result = run_release(
        "validate-artifacts", "--dist", str(dist), "--version", "1.2.3"
    )

    assert result.returncode == 0, result.stderr


def test_release_please_configuration_bootstraps_stable_semver() -> None:
    root = Path(__file__).parents[1]
    config = json.loads((root / "release-please-config.json").read_text())
    manifest = json.loads((root / ".release-please-manifest.json").read_text())

    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    package = config["packages"]["."]
    assert package["release-type"] == "python"
    if manifest:
        assert manifest == {".": project["version"]}
        assert "release-as" not in package
    else:
        assert package["release-as"] == "1.0.0"
    assert package["include-v-in-tag"] is True
    assert package["include-component-in-tag"] is False
    assert [section["type"] for section in package["changelog-sections"]] == [
        "feat",
        "fix",
        "perf",
    ]


def test_release_workflows_pin_dispatched_commits_and_trusted_publish() -> None:
    workflows = Path(__file__).parents[1] / ".github" / "workflows"
    ci = (workflows / "pull_request.yml").read_text()
    release = (workflows / "release.yml").read_text()
    publish = (workflows / "publish.yml").read_text()

    assert 'test "$GITHUB_SHA" = "$EXPECTED_SHA"' in ci
    assert '-f expected_sha="$FINAL_SHA"' in release
    assert '--ref "$RELEASE_TAG"' in release
    assert 'test "$GITHUB_REF" = "refs/tags/$RELEASE_TAG"' in publish
    assert "uv publish --trusted-publishing always" in publish
    assert "environment: pypi" in publish
    assert "id-token: write" in publish


@pytest.mark.parametrize(
    ("filename", "contents", "message"),
    [
        (".release-please-manifest.json", '{".": "1.2.2"}', "manifest"),
        (
            "release-please-config.json",
            '{"packages": {".": {"release-as": "1.0.0"}}}',
            "override",
        ),
        (
            "CHANGELOG.md",
            "## 1.2.30 (2026-09-18)\n\n- Wrong version.\n",
            "dated section",
        ),
        ("CHANGELOG.md", "## 1.2.3\n\n- Missing date.\n", "dated section"),
        ("CHANGELOG.md", "## 1.2.3 (2026-09-18)\n", "no notes"),
    ],
)
def test_validate_repository_rejects_invalid_release_metadata(
    tmp_path: Path, filename: str, contents: str, message: str
) -> None:
    write_release_repository(tmp_path)
    (tmp_path / filename).write_text(contents)
    result = run_release(
        "validate-repository", "--root", str(tmp_path), "--tag", "v1.2.3"
    )
    assert result.returncode == 1
    assert message in result.stderr


def test_validate_repository_rejects_tag_mismatch(tmp_path: Path) -> None:
    write_release_repository(tmp_path)
    result = run_release(
        "validate-repository", "--root", str(tmp_path), "--tag", "v1.2.4"
    )
    assert result.returncode == 1
    assert "does not match" in result.stderr


def test_changelog_cli_extracts_reviewed_section(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    section = "## [1.2.3](https://example.com/compare) (2026-09-18)\n\n- Reviewed correction.\n"
    changelog.write_text(
        "# Changelog\n\n" + section + "\n## 1.2.2 (2026-09-17)\n\n- Older note.\n"
    )
    result = run_release(
        "changelog-section", "--path", str(changelog), "--version", "1.2.3"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == section


def test_repository_rejects_unreviewed_release_notes(tmp_path: Path) -> None:
    write_release_repository(tmp_path)
    notes = tmp_path / "notes.md"
    notes.write_text("Generated but not reviewed notes.\n")
    result = run_release(
        "validate-repository",
        "--root",
        str(tmp_path),
        "--tag",
        "v1.2.3",
        "--release-notes",
        str(notes),
    )
    assert result.returncode == 1
    assert "do not equal" in result.stderr

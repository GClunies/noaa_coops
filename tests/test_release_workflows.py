from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SETUP_UV = "uses: astral-sh/setup-uv@"


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text()


def test_release_please_uses_one_manifest_mode_with_bootstrap_override() -> None:
    release = workflow("release.yml")

    assert release.count("googleapis/release-please-action@") == 1
    assert "issues: write" in release
    assert (
        "release-as"
        not in release.split("uses: googleapis/release-please-action@", 1)[1].split(
            "steps.", 1
        )[0]
    )
    assert 'del(.packages["."]["release-as"])' in release


def test_release_preparation_uses_trusted_main_and_no_credentials() -> None:
    release = workflow("release.yml")
    prepare = release.split("- name: Prepare release pull request", 1)[1].split(
        "- name: Push prepared release pull request", 1
    )[0]

    assert "persist-credentials: false" in release
    assert "git fetch origin main:refs/remotes/origin/main" in prepare
    assert 'scripts/release.py" bootstrap-changelog' in prepare
    assert '--source "$GITHUB_WORKSPACE/CHANGELOG.md"' in prepare
    assert "GH_TOKEN:" not in prepare
    assert "gh auth setup-git" not in prepare
    assert release.index(SETUP_UV) < release.index("uv lock")
    for allowed in (
        "pyproject.toml",
        "uv.lock",
        "CITATION.cff",
        "CHANGELOG.md",
        ".release-please-manifest.json",
        "release-please-config.json",
    ):
        assert allowed in prepare
    assert "scripts/release.py bootstrap-changelog" not in prepare
    assert "CITATION.cff .release-please-manifest.json" not in prepare


def test_release_api_validation_requires_bot_and_canonical_branch() -> None:
    release = workflow("release.yml")

    assert 'test "$AUTHOR" = "github-actions[bot]"' in release
    assert "release-please--branches--main" in release
    assert 'test "$HEAD_REPOSITORY" = "$GITHUB_REPOSITORY"' in release
    assert 'test "$BASE" = main' in release
    assert "gh run list" not in release
    assert "gh run watch" not in release


def test_privileged_actions_are_pinned_and_publish_roles_are_split() -> None:
    all_workflows = "\n".join(
        workflow(name)
        for name in (
            "release.yml",
            "publish.yml",
            "test-publish.yml",
            "pull_request.yml",
        )
    )
    for action in re.findall(r"uses:\s+(\S+)", all_workflows):
        assert re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", action)

    publish = workflow("publish.yml")
    oidc = publish.split("\n  publish:", 1)[1].split("\n  attach-assets:", 1)[0]
    assets = publish.split("\n  attach-assets:", 1)[1]
    assert "id-token: write" in oidc
    assert "contents: write" not in oidc
    assert "contents: write" in assets
    assert "needs: [validate, publish]" in assets
    assert (
        'gh release upload "$RELEASE_TAG" "$FILE" --repo "$GITHUB_REPOSITORY"' in assets
    )


def test_publish_syncs_notes_from_the_tagged_changelog_before_oidc() -> None:
    publish = workflow("publish.yml")

    assert "changelog-section" in publish
    assert "gh release edit" in publish
    assert 'test "$ACTUAL_NOTES" = "$EXPECTED_NOTES"' in publish
    assert "--release-notes" not in publish
    assert "needs: [validate, build, notes-sync]" in publish
    assert "set(noaa_coops.__all__)" not in publish


def test_testpypi_accepts_only_the_canonical_open_release_pr() -> None:
    rehearsal = workflow("test-publish.yml")

    assert "github-actions[bot]" in rehearsal
    assert "release-please--branches--main" in rehearsal
    assert 'test "$HEAD_REPOSITORY" = "$GITHUB_REPOSITORY"' in rehearsal
    assert 'test "$BASE" = main' in rehearsal
    assert 'test "$STATE" = open' in rehearsal
    assert 'test "$HEAD_SHA" = "$EXPECTED_SHA"' in rehearsal
    assert 'test "$GITHUB_REF" = "refs/heads/$HEAD_REF"' in rehearsal
    assert "git merge-base --is-ancestor origin/main" in rehearsal
    assert "validate-repository --tag" in rehearsal
    build_step = rehearsal.split("- name: Run release checks and build", 1)[1].split(
        "- name: Retain immutable distributions", 1
    )[0]
    assert "EXPECTED_SHA: ${{ inputs.expected_sha }}" in build_step
    assert "--no-deps --index-url https://test.pypi.org/simple" in rehearsal
    assert "requirements.txt" in rehearsal


def test_pr_title_check_reruns_on_edits_without_base_helper_dependency() -> None:
    ci = workflow("pull_request.yml")

    assert "types: [opened, synchronize, reopened, edited]" in ci
    title_job = ci.split("\n  pr-title:", 1)[1].split("\n  lint:", 1)[0]
    assert "scripts/release.py" not in title_job
    assert "PR_TITLE" in title_job
    assert "BREAKING CHANGE" in title_job

"""Validate release inputs and artifacts without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class ReleaseError(ValueError):
    pass


def version_tuple(version: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(version)
    if not match:
        raise ReleaseError(f"{version!r} is not strict SemVer")
    return tuple(map(int, match.groups()))


def citation_version(path: Path) -> str:
    matches = re.findall(
        r"(?m)^version:\s*['\"]?([^'\"\s#]+)['\"]?\s*(?:#.*)?$",
        path.read_text(),
    )
    if len(matches) != 1:
        raise ReleaseError("CITATION.cff must contain one top-level version")
    return matches[0]


def lock_version(path: Path) -> str:
    document = tomllib.loads(path.read_text())
    matches = [
        package.get("version")
        for package in document.get("package", [])
        if package.get("name") == "noaa-coops"
    ]
    if len(matches) != 1 or not isinstance(matches[0], str):
        raise ReleaseError("uv.lock must contain one noaa-coops package version")
    return matches[0]


def changelog_section(path: Path, version: str) -> str:
    """Return the dated section for an exact version, or reject missing notes."""
    version_tuple(version)
    text = path.read_text()
    escaped = re.escape(version)
    heading = re.search(
        rf"(?m)^## (?:\[{escaped}\](?:\([^\n]*\))?|{escaped})"
        r"[ \t]+(?:-[ \t]+)?\(?\d{4}-\d{2}-\d{2}\)?[ \t]*$",
        text,
    )
    if not heading:
        raise ReleaseError(f"CHANGELOG.md has no dated section for {version}")
    next_heading = re.search(r"(?m)^## ", text[heading.end() :])
    end = heading.end() + next_heading.start() if next_heading else len(text)
    section = text[heading.start() : end].strip()
    if not text[heading.end() : end].strip():
        raise ReleaseError(f"CHANGELOG.md has no notes for {version}")
    return section + "\n"


def validate_repository(args: argparse.Namespace) -> None:
    root = Path(args.root)
    project = tomllib.loads((root / "pyproject.toml").read_text())
    version = project.get("project", {}).get("version")
    if not isinstance(version, str):
        raise ReleaseError("pyproject.toml must define project.version")
    parsed = version_tuple(version)
    if parsed < (1, 0, 0):
        raise ReleaseError("release version must be at least 1.0.0")
    if args.tag != f"v{version}":
        raise ReleaseError(f"tag {args.tag!r} does not match project version {version}")
    if citation_version(root / "CITATION.cff") != version:
        raise ReleaseError("CITATION.cff version does not match pyproject.toml")
    if lock_version(root / "uv.lock") != version:
        raise ReleaseError("uv.lock version does not match pyproject.toml")
    manifest = json.loads((root / ".release-please-manifest.json").read_text())
    if manifest != {".": version}:
        raise ReleaseError("release manifest version does not match pyproject.toml")
    config = json.loads((root / "release-please-config.json").read_text())
    if "release-as" in config["packages"]["."]:
        raise ReleaseError("remove the bootstrap release-as override before merging")
    section = changelog_section(root / "CHANGELOG.md", version)
    if args.release_notes:
        notes = Path(args.release_notes).read_text().strip() + "\n"
        if notes != section:
            raise ReleaseError(
                "GitHub release notes do not equal the dated CHANGELOG section"
            )
    print(version)


def bootstrap_changelog(args: argparse.Namespace) -> None:
    """Move trusted base notes under the generated first-release heading.

    Release Please can insert its generated section before or after Unreleased.
    Read curated notes from the base instead of inferring that insertion order.
    """
    path = Path(args.path)
    header = changelog_section(path, args.version).splitlines()[0]
    source = Path(args.source).read_text()
    unreleased = re.search(r"(?m)^## (?:\[Unreleased\]|Unreleased)[ \t]*$", source)
    if not unreleased:
        raise ReleaseError("the base changelog requires an Unreleased section")
    remainder = source[unreleased.end() :]
    next_heading = re.search(r"(?m)^## ", remainder)
    end = next_heading.start() if next_heading else len(remainder)
    curated = remainder[:end].strip()
    if not curated:
        raise ReleaseError("the first release requires curated Unreleased notes")
    path.write_text(
        source[: unreleased.start()]
        + "## [Unreleased]\n\n"
        + header
        + "\n\n"
        + curated
        + "\n\n"
        + remainder[end:].lstrip("\n")
    )


def metadata_version(contents: bytes, artifact: str) -> str:
    version = BytesParser().parsebytes(contents).get("Version")
    name = BytesParser().parsebytes(contents).get("Name", "")
    if re.sub(r"[-_.]+", "-", name).lower() != "noaa-coops":
        raise ReleaseError(f"{artifact} is not the noaa-coops distribution")
    if not version:
        raise ReleaseError(f"{artifact} metadata has no Version")
    return version


def validate_artifacts(args: argparse.Namespace) -> None:
    dist = Path(args.dist)
    wheels = list(dist.glob("*.whl"))
    sdists = list(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ReleaseError("dist must contain exactly one wheel and one sdist")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(names) != 1:
            raise ReleaseError("wheel must contain exactly one METADATA file")
        wheel_version = metadata_version(archive.read(names[0]), wheels[0].name)
    with tarfile.open(sdists[0]) as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.name.endswith("/PKG-INFO")
        ]
        if len(members) != 1:
            raise ReleaseError("sdist must contain exactly one PKG-INFO file")
        extracted = archive.extractfile(members[0])
        if extracted is None:
            raise ReleaseError("sdist PKG-INFO is not a regular file")
        sdist_version = metadata_version(extracted.read(), sdists[0].name)
    if wheel_version != args.version or sdist_version != args.version:
        raise ReleaseError(
            f"artifact versions must both equal {args.version}: "
            f"wheel={wheel_version}, sdist={sdist_version}"
        )


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    subcommands = command.add_subparsers(dest="command", required=True)

    repository = subcommands.add_parser("validate-repository")
    repository.add_argument("--root", default=".")
    repository.add_argument("--tag", required=True)
    repository.add_argument("--release-notes")
    repository.set_defaults(function=validate_repository)

    bootstrap = subcommands.add_parser("bootstrap-changelog")
    bootstrap.add_argument("--path", required=True)
    bootstrap.add_argument("--source", required=True)
    bootstrap.add_argument("--version", required=True)
    bootstrap.set_defaults(function=bootstrap_changelog)

    section = subcommands.add_parser("changelog-section")
    section.add_argument("--path", required=True)
    section.add_argument("--version", required=True)
    section.set_defaults(
        function=lambda args: print(
            changelog_section(Path(args.path), args.version), end=""
        )
    )

    artifacts = subcommands.add_parser("validate-artifacts")
    artifacts.add_argument("--dist", required=True)
    artifacts.add_argument("--version", required=True)
    artifacts.set_defaults(function=validate_artifacts)
    return command


def main() -> int:
    args = parser().parse_args()
    try:
        args.function(args)
    except (
        OSError,
        ReleaseError,
        tomllib.TOMLDecodeError,
        json.JSONDecodeError,
        tarfile.TarError,
        zipfile.BadZipFile,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Integration tests for local wheel and sdist artifacts."""

from __future__ import annotations

import email
import os
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_ARTIFACT_BYTES = 5 * 1024 * 1024
FORBIDDEN_ARTIFACT_PARTS = (
    "tests/",
    ".git/",
    ".venv/",
    "models/",
    ".pytest_cache/",
    "doctor.txt",
)


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    dist_dir = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        ["uv", "build", "--no-sources", "--out-dir", str(dist_dir)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    assert len(wheels) == 1, wheels
    assert len(sdists) == 1, sdists
    return wheels[0], sdists[0]


def _metadata_from_wheel(wheel: Path) -> email.message.Message:
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith("METADATA")]
        assert metadata_names
        return email.message_from_bytes(archive.read(metadata_names[0]))


def test_wheel_metadata_and_entry_point(artifacts: tuple[Path, Path]) -> None:
    wheel, _sdist = artifacts
    metadata = _metadata_from_wheel(wheel)
    assert metadata["Name"] == "ceia-aisdk"
    assert metadata["Version"]
    assert metadata["Requires-Python"].replace(" ", "") == ">=3.11,<3.14"
    classifiers = metadata.get_all("Classifier") or []
    assert "Operating System :: POSIX :: Linux" in classifiers
    extras = metadata.get_all("Provides-Extra") or []
    assert "cuda" in extras
    with zipfile.ZipFile(wheel) as archive:
        entry_text = "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith("entry_points.txt")
        )
    assert "ceia-aisdk" in entry_text
    assert "ceia_aisdk.cli:app" in entry_text


def test_artifact_contents_exclude_tests_and_runtime_assets(artifacts: tuple[Path, Path]) -> None:
    wheel, sdist = artifacts
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    assert any(name.startswith("ceia_aisdk/") for name in names)
    assert not any(any(part in name for part in FORBIDDEN_ARTIFACT_PARTS) for name in names)
    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = archive.getnames()
    assert any(name.endswith("pyproject.toml") for name in sdist_names)
    assert any(
        "/src/ceia_aisdk/" in name or name.endswith("/src/ceia_aisdk") for name in sdist_names
    )
    assert not any("/tests/" in name for name in sdist_names)


def test_artifact_size_budget(artifacts: tuple[Path, Path]) -> None:
    wheel, sdist = artifacts
    assert wheel.stat().st_size <= MAX_ARTIFACT_BYTES
    assert sdist.stat().st_size <= MAX_ARTIFACT_BYTES


def test_twine_and_wheel_contents(artifacts: tuple[Path, Path]) -> None:
    wheel, sdist = artifacts
    twine = subprocess.run(
        ["uv", "run", "twine", "check", str(wheel), str(sdist)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert twine.returncode == 0, twine.stdout + twine.stderr
    contents = subprocess.run(
        ["uv", "run", "check-wheel-contents", str(wheel)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert contents.returncode == 0, contents.stdout + contents.stderr


def test_isolated_wheel_and_sdist_smoke(artifacts: tuple[Path, Path]) -> None:
    wheel, sdist = artifacts
    for artifact in (wheel, sdist):
        version = subprocess.run(
            [
                "uv",
                "run",
                "--isolated",
                "--no-project",
                "--offline",
                "--with",
                str(artifact),
                "python",
                "-c",
                "import ceia_aisdk; print(ceia_aisdk.__version__)",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert version.returncode == 0, version.stderr
        assert version.stdout.strip()
    help_result = subprocess.run(
        [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--offline",
            "--with",
            str(wheel),
            "ceia-aisdk",
            "--help",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "doctor" in help_result.stdout


def test_no_publication_command_is_invoked(artifacts: tuple[Path, Path]) -> None:
    del artifacts
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "uv publish" not in pyproject
    assert "twine upload" not in pyproject
    workflows = REPO_ROOT / ".github" / "workflows"
    if workflows.exists():
        for path in workflows.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            assert "uv publish" not in text
            assert "twine upload" not in text
    assert os.environ.get("UV_PUBLISH_TOKEN") in {None, ""}

"""Contract tests for LLM packaging, README phrases, and artifact contents."""

from __future__ import annotations

import email
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_has_fifteen_minute_pip_quickstart() -> None:
    text = README.lower()
    assert "pip install ceia-aisdk" in text
    assert "15" in README and "minute" in text
    assert "llm/small" in text
    assert "not thread-safe" in text or "not thread safe" in text
    assert "linux" in text and "x86_64" in text
    assert "windows" in text
    assert "not" in text
    assert "[cuda]" in text or "ceia-aisdk[cuda]" in text
    assert "wheel" in text
    assert "not" in text


def test_readme_documents_chat_stream_session_and_cpu_override() -> None:
    assert ".chat" in README or "chat(" in README
    assert ".stream" in README or "stream(" in README
    assert ".session" in README or "session(" in README
    assert 'device="cpu"' in README or 'device = "cpu"' in README
    assert "medium" in README
    assert "uv " in README


def test_readme_does_not_promise_windows() -> None:
    lowered = README.lower()
    assert "windows support" not in lowered
    assert "linux x86_64" in lowered


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    import subprocess

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
    assert len(wheels) == 1
    assert len(sdists) == 1
    return wheels[0], sdists[0]


def test_wheel_and_sdist_include_llm_and_exclude_weights(
    artifacts: tuple[Path, Path],
) -> None:
    wheel, sdist = artifacts
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    assert any(
        "ceia_aisdk/llm/" in name or name.endswith("ceia_aisdk/llm/__init__.py") for name in names
    )
    assert not any(name.endswith(".gguf") for name in names)
    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = archive.getnames()
    assert any("/llm/" in name for name in sdist_names)
    assert not any(name.endswith(".gguf") for name in sdist_names)


def test_wheel_linux_classifier_and_cuda_extra(artifacts: tuple[Path, Path]) -> None:
    wheel, _sdist = artifacts
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith("METADATA")]
        metadata = email.message_from_bytes(archive.read(metadata_names[0]))
    classifiers = metadata.get_all("Classifier") or []
    assert "Operating System :: POSIX :: Linux" in classifiers
    assert not any("Windows" in item for item in classifiers)
    extras = metadata.get_all("Provides-Extra") or []
    assert "cuda" in extras
    requires = metadata.get_all("Requires-Dist") or []
    assert any("llama-cpp-python" in item and "extra == 'cuda'" in item for item in requires)

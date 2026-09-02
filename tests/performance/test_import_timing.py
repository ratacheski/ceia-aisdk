"""Fresh-process import timing and forbidden-backend checks."""

from __future__ import annotations

import statistics
import subprocess
import sys

_IMPORT_SAMPLES = 20
_P95_LIMIT_SECONDS = 0.200
_FORBIDDEN = (
    "torch",
    "llama_cpp",
    "faster_whisper",
    "piper",
    "typer",
    "rich",
)


def _run_fresh(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True)


def test_fresh_import_exposes_version_without_backends() -> None:
    code = f"""
import sys
import ceia_aisdk
forbidden = {list(_FORBIDDEN)!r}
loaded = [name for name in forbidden if name in sys.modules]
print(ceia_aisdk.__version__)
raise SystemExit(1 if loaded else 0)
"""
    result = _run_fresh(code)
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip()


def test_fresh_import_p95_is_within_budget() -> None:
    code = """
import time
start = time.perf_counter()
import ceia_aisdk
elapsed = time.perf_counter() - start
assert ceia_aisdk.__version__
print(f"{elapsed:.6f}")
"""
    samples: list[float] = []
    for _ in range(_IMPORT_SAMPLES):
        result = _run_fresh(code)
        assert result.returncode == 0, result.stderr
        samples.append(float(result.stdout.strip()))
    p95 = statistics.quantiles(samples, n=20)[-1]
    assert p95 <= _P95_LIMIT_SECONDS, (
        f"import p95 {p95:.3f}s exceeds {_P95_LIMIT_SECONDS:.3f}s; samples={samples}"
    )

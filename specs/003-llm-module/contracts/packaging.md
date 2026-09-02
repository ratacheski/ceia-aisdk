# Packaging Contract: First Public Release

**Feature**: `003-llm-module`
**Version**: `ceia-aisdk==0.1.0`
**Channel**: public PyPI only

## Versioning

- Development on this feature MAY keep `0.1.0.dev0` in `pyproject.toml`.
- The publish task MUST set `project.version` to `0.1.0` before `uv build` and `uv publish`.
- Test-index uploads do not satisfy FR-020.

## Artifacts

`uv build` MUST produce a wheel and an sdist that:

- install as `ceia-aisdk`;
- expose `ceia_aisdk` and the `ceia-aisdk` console script;
- include the bundled catalog YAML;
- include `ceia_aisdk.llm`;
- do **not** include GGUF, `.bin` weight payloads, or cache directories;
- declare `Requires-Python: >=3.11,<3.14`;
- keep classifiers that state POSIX/Linux and MUST NOT claim Windows.

`check-wheel-contents` MUST fail if a `.gguf` file is present.

## Dependencies

- Main dependencies include a CPU-capable `llama-cpp-python` pin so
  `pip install ceia-aisdk` can first-chat without a compiler.
- `[project.optional-dependencies] cuda` is no longer an empty reservation. It is the
  documented extra name for GPU onboarding. Because public PyPI does not host a CUDA build of
  the backend, the extra MAY re-declare the backend package and MUST be accompanied by ≤ 20
  lines of English install instructions (prebuilt extra index if the team provides one,
  otherwise `CMAKE_ARGS="-DGGML_CUDA=on"` rebuild).
- The 15-minute KPI clock excludes that CUDA rebuild.

## Project Page (README)

The README uploaded to PyPI MUST, in English:

- show the 15-minute CPU quickstart from `pip install ceia-aisdk` to
  `LLM().chat("Say only: ok")`;
- state Linux x86_64 only and not promise Windows;
- state the launch default `llm/small`;
- show how to select `medium` and `device="cpu"`;
- document `.chat`, `.stream`, `.session`;
- document the `[cuda]` extra and that compile time is outside the 15-minute path;
- state that instances are not thread-safe;
- state that model weights are downloaded into `~/.ceia-aisdk` and are not inside the wheel;
- use `pip` for end-user install examples and `uv` for contributor examples.

## Publication Process

Contributor sequence (all through `uv` except the end-user pip examples in README):

1. Quality gates green (`uv lock --check`, lint, tests, `uv build`).
2. Set version `0.1.0`.
3. `uv build --no-sources`.
4. Inspect artifacts (Twine, check-wheel-contents, no weights).
5. `uv publish` to public PyPI (credentials per maintainer process).
6. Verify the project page and that `pip install ceia-aisdk==0.1.0` resolves.

## Out of Scope

- Windows wheels, Apple Silicon, ROCm, Vulkan.
- Embedding `llm/small` in the wheel.
- A second distribution name for CUDA.

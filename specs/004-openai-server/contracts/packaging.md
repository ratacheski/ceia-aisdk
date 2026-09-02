# Packaging Contract: Server Extra and `0.2.0`

**Feature**: `004-openai-server`
**Version**: `ceia-aisdk==0.2.0`
**Channel**: public PyPI only

## Versioning

- Development on this feature MAY keep `0.2.0.dev0` in `pyproject.toml`.
- The publish task MUST set `project.version` to `0.2.0` before `uv build` and `uv publish`.
- Test-index uploads do not satisfy FR-023.
- Distribution name remains `ceia-aisdk` (not a second package).

## Extra

```toml
[project.optional-dependencies]
server = [
    "fastapi>=0.115",
    "uvicorn>=0.32",
]
```

`Provides-Extra: server` MUST appear in `0.2.0` metadata. It MUST NOT have been part of the
`0.1.0` user contract. `[cuda]` remains.

The extra MUST be sufficient to import FastAPI and uvicorn and to run `ceia-aisdk serve` on
Linux x86_64 with a supported Python.

`openai` is a **dev** test dependency, not a `[server]` runtime requirement.

## Artifacts

`uv build` MUST produce a wheel and an sdist that:

- install as `ceia-aisdk`;
- expose `ceia_aisdk`, `ceia_aisdk.server`, and the `ceia-aisdk` console script;
- include the bundled catalog YAML;
- do **not** include GGUF, `.bin` weight payloads, cache directories, binaries, or installers;
- declare `Requires-Python: >=3.11,<3.14`;
- keep POSIX/Linux classifiers and MUST NOT claim Windows.

`check-wheel-contents` MUST fail if a `.gguf` file is present.

## Project Page (README)

The README uploaded to PyPI MUST, in English, keep the 15-minute CPU first-chat quickstart and
add a serving section that documents:

- `pip install "ceia-aisdk[server]"`;
- `ceia-aisdk serve` default `http://127.0.0.1:11434/v1`;
- opaque aliases (`llm/small`, never Hugging Face names);
- stream and non-stream chat;
- OpenAI `tools` / `tool_calls` on the same chat route; the client executes tools;
- optional `--token` and default localhost CORS / `--cors`;
- queue depth 8 and HTTP 429;
- bind conflict remediation (`--port` or stop the occupant);
- TLS via reverse proxy, not native TLS;
- Linux x86_64 only;
- that voice, vision, RAG, and the app launcher are out of this slice;
- `pip` for end-user install examples and `uv` for contributor examples.

## Publication Process

Contributor sequence (all through `uv` except end-user pip examples in README):

1. Quality gates green (`uv lock --check`, lint, tests, `uv build`).
2. Set version `0.2.0`.
3. `uv build --no-sources`.
4. Inspect artifacts (Twine, check-wheel-contents, no weights).
5. `uv publish` to public PyPI.
6. Verify the project page and that `pip install "ceia-aisdk[server]==0.2.0"` resolves.

## Out of Scope

- Windows wheels, Apple Silicon, ROCm, Vulkan.
- Embedding weights or a desktop binary.
- A second distribution name for the server.
- Waiting for PRDs 03–05 before this publish.

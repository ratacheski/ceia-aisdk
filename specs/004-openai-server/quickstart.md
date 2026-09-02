# Quickstart Validation: OpenAI-Compatible Local Server

**Feature**: `004-openai-server`

This guide validates the completed PRD-06 implementation. It is not an implementation guide and
does not replace the automated test suite. Prior checks in
[001-sdk-foundations/quickstart.md](../../001-sdk-foundations/quickstart.md),
[002-model-registry/quickstart.md](../../002-model-registry/quickstart.md), and
[003-llm-module/quickstart.md](../../003-llm-module/quickstart.md) remain applicable.

## Prerequisites

- Linux x86_64
- `uv`
- Completed `001-sdk-foundations`, `002-model-registry`, and `003-llm-module`
- Tiny GGUF fixture for generation tests (`scripts/fetch-llm-test-fixture.sh`)
- Production `llm/small` plus a real OpenAI client against port 11434 are manual on the
  reference machine

The examples use Python 3.13.

## 1. Synchronize Dependencies

```bash
uv python install 3.13
uv sync --python 3.13 --locked --all-groups --all-extras
uv lock --check
```

Expected outcome:

- `[server]` extra resolves FastAPI and uvicorn;
- lockfile is unchanged after `--check`;
- no production weights are downloaded during sync.

## 2. Import Budget Still Holds

```bash
uv run python -c "import ceia_aisdk, sys; assert 'fastapi' not in sys.modules and 'uvicorn' not in sys.modules and 'llama_cpp' not in sys.modules; print(ceia_aisdk.__version__)"
```

Expected outcome:

- `ServerError` is importable from `ceia_aisdk`;
- package root still does not import `ceia_aisdk.server`.

```bash
uv run pytest tests/contract/test_package_api.py tests/contract/test_server_import_budget.py tests/performance/test_import_timing.py
```

## 3. CLI Help and Doctor Extras

```bash
uv run ceia-aisdk --help
uv run ceia-aisdk serve --help
uv run ceia-aisdk doctor
```

Expected outcome:

- root help lists `serve`;
- serve help documents `--host`, `--port`, `--token`, `--cors`, `--debug`, default
  `127.0.0.1:11434`, and that tools use `/v1/chat/completions`;
- doctor `optional_groups` includes `server`.

```bash
uv run pytest tests/contract/test_cli_help.py tests/contract/test_serve_cli_help.py tests/integration/test_doctor.py
```

## 4. Unit Matrix (Pool, Messages, Missing Extra)

```bash
uv run pytest tests/unit/test_llm_tool_calls.py tests/unit/test_server_pool.py tests/unit/test_server_messages.py tests/unit/test_server_errors.py tests/unit/test_server_missing_extra.py
```

Expected outcome:

- waiter 9 of a busy alias is rejected at cap 8;
- `complete` returns structured tool calls on a fake backend; `LLM.chat` still returns `str`;
- image parts are classified as 400; `tools` on a non-`tool_use` alias raise `CapabilityError`;
- missing extra surfaces `ServerError` mentioning `ceia-aisdk[server]`.

## 5. ASGI Integration (Tiny GGUF)

```bash
./scripts/fetch-llm-test-fixture.sh
uv run pytest tests/integration/test_serve_models_chat.py tests/integration/test_serve_stream.py tests/integration/test_serve_tools.py tests/integration/test_serve_auth_cors.py tests/integration/test_serve_queue.py tests/integration/test_serve_adaptive.py tests/integration/test_serve_openai_client.py tests/integration/test_serve_bind.py
```

Expected outcome:

- `/v1/models` lists only opaque aliases and returns quickly;
- non-stream chat returns nonempty text;
- stream has ≥ 1 `data:` chunk;
- missing Bearer with token configured → 401;
- default CORS does not allow a foreign origin;
- 429 after 8 waiters;
- embeddings/audio → 501; vision in chat → 400;
- tool-call JSON shape and a `role: tool` follow-up succeed on a `tool_use` alias (fake or recording);
- official client or httpx completes `/v1` chat;
- occupied port → `ServerError` with `--port` remediation.

## 6. Packaging Without Weights

```bash
uv build --no-sources
uv run pytest tests/contract/test_server_packaging.py tests/integration/test_installed_artifacts.py
```

Expected outcome:

- metadata declares extra `server`;
- artifacts contain `ceia_aisdk.server` and no `.gguf`;
- isolated install without the extra still forbids FastAPI on `import ceia_aisdk` and explains
  the extra on `serve`.

## 7. Quality Gates

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pydoclint src
uv run pytest
uv build --no-sources
```

All contributor commands use `uv`.

## 8. Manual Reference Checklist (not CI)

On a Linux x86_64 machine with the `[server]` extra:

1. `pip install "ceia-aisdk[server]"` from the public index (or a local wheel standing in before
   publish).
2. `ceia-aisdk serve` → ready log shows `http://127.0.0.1:11434/v1`.
3. `GET /v1/models` within 2 s, only opaque aliases.
4. Official OpenAI client `base_url=http://127.0.0.1:11434/v1` completes a chat against
   `llm/small` (cached or after obtain).
5. Send `tools` for a `tool_use` alias; if the model requests a call, confirm `tool_calls` and
   that the process did not execute the function. Follow up with `role: tool`.
6. `--token secret` rejects requests without Bearer (401).
7. With another process on 11434, start fails with `--port` / stop-occupant remediation.
8. Confirm INFO logs do not print prompts.

## 9. Publish `0.2.0`

After gates and the manual serve checklist:

```bash
# version in pyproject.toml is 0.2.0
uv build --no-sources
uv publish
```

Expected outcome: `ceia-aisdk==0.2.0` on the public index, `[server]` extra installable, README
serve section visible, Linux classifiers only, no weights in the files.

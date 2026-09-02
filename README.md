# CEIA AI SDK

Local GGUF chat for Linux x86_64. Install from PyPI, construct `LLM()`, and
get a completion from `llm/small` in about 15 minutes on CPU, including the
model download. CUDA compilation is outside that 15-minute path.

This package supports **Linux x86_64** only. It does not promise Windows
support.

Model weights are downloaded into `~/.ceia-aisdk` at runtime. They are **not**
inside the wheel or source distribution. `LLM` instances are **not thread-safe**.

## 15-minute CPU quickstart

```bash
pip install ceia-aisdk
python -c 'from ceia_aisdk.llm import LLM; print(LLM().chat("Say only: ok"))'
```

The first call uses the launch default `llm/small@latest`, obtains the local
file through the registry, and returns a nonempty string. On a TTY, obtain
progress is shown. Later calls reuse the cache.

Select medium or force CPU:

```python
from ceia_aisdk.llm import LLM

LLM("medium").chat("Say only: ok")
LLM(device="cpu").chat("Say only: ok")
```

Streaming and a short session:

```python
from ceia_aisdk.llm import LLM

model = LLM(device="cpu")
print("".join(model.stream("Say only: ok")))
session = model.session(system="Be brief.")
session.send("My name is Ada.")
print(session.send("What is my name?"))
```

Async callers use `AsyncLLM`. Generation runs in a worker thread because the
llama.cpp binding is blocking:

```python
import asyncio
from ceia_aisdk.llm import AsyncLLM

async def main() -> None:
    model = AsyncLLM(device="cpu")
    print(await model.chat("Say only: ok"))

asyncio.run(main())
```

## CUDA extra

GPU onboarding uses the `[cuda]` extra. Public PyPI does not host a CUDA build
of `llama-cpp-python`, so install the extra and then rebuild or install a
CUDA-capable binding. Compile time is **not** part of the 15-minute CPU path.

```bash
pip install "ceia-aisdk[cuda]"
CMAKE_ARGS="-DGGML_CUDA=on" pip install --force-reinstall --no-cache-dir llama-cpp-python
```

If the project publishes a prebuilt extra index, install from that index
instead of compiling. `ceia-aisdk doctor` reports GPU visibility and, separately,
whether the CUDA inference binding is present (`cuda_binding=yes|no`).

## CLI

```bash
ceia-aisdk --help
ceia-aisdk doctor
ceia-aisdk model --help
```

## Configuration

`AISDKConfig` keeps four fields: `device`, `cache_dir`, `log_level`, `offline`.
LLM defaults live in a sibling `[llm]` table:

```toml
[core]
device = "auto"
cache_dir = "~/.ceia-aisdk"
log_level = "WARNING"
offline = false

[llm]
default_alias = "llm/small@latest"
context_length = 8192
```

Environment overrides: `CEIA_AISDK_DEVICE`, `CEIA_AISDK_LLM_DEFAULT_ALIAS`,
`CEIA_AISDK_LLM_CONTEXT_LENGTH`, `CEIA_AISDK_OFFLINE`.

## Contributor setup

Install `uv`, then synchronize the locked environment:

```bash
uv python install 3.13
uv sync --python 3.13 --locked --all-groups --all-extras
uv lock --check
```

All contributor commands in this repository run through `uv`. End-user install
examples use `pip`.

```bash
uv run pytest
uv build --no-sources
```

Fetch the tiny GGUF used by real-backend tests:

```bash
./scripts/fetch-llm-test-fixture.sh
```

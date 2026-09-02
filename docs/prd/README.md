# PRD Program — CEIA AI SDK (`ceia-aisdk`)

**Vision source:** [docs/plans/2026-07-29-ai-sdk-x86-design.md](../plans/2026-07-29-ai-sdk-x86-design.md)
**Program date:** 2026-09-01
**Positioning:** public product on PyPI — Python library + CLI, Linux x86_64, competing with Ollama/LM Studio on the *embeddable in code* axis.
**Anchor KPI:** time-to-first-chat ≤ 15 min on a clean Linux x86_64 system, CPU, working network, **starting from `pip install ceia-aisdk` from the public index**.
**Target OS for this series:** Linux x86_64 only (Ubuntu 22.04+ as the reference). Windows and Apple Silicon are out of scope.
**Channel:** PyPI only. No binary, installer, or store.

This directory is the requirements source of truth. Speckit comes **later** — the PRDs are the contract for now; specify/plan/tasks only when the team requests them. When the time comes, **one PRD = one Speckit feature**.

## Incremental scope (mandatory)

The original plan treats the multimodal scope as an “uncut v1.” That is a product vision, not a delivery slice. The PRDs below deliver the vision **in sequence**, each one shippable and testable.

Explicit cuts from the plan (discovery on 2026-09-01):

| Plan item | Destination in the program |
|---|---|
| Ed25519 + official mirrors + `CatalogSignatureError` | Out of the MVP. Bundled catalog + `sha256`. Returns as a future feature, not as a PRD in this series. |
| `vision.ocr()` / `vision.detect()` (ONNX) | Out of the MVP. Vision = `Vision.describe` only. |
| Docs as a standalone stage 10 | **There is no docs PRD.** Each PRD includes the documentation increment for that slice. |
| CUDA auto-detect + `[cuda]` extra | **Included.** The first demo requires real CUDA inference in PRD 02. |
| Mirrored sync + async APIs | **Included**, starting with PRD 02 (not 00). |
| Open WebUI + OpenClaw app launcher | **Included** in PRD 07, after the server. OpenClaw is P1 in 07, not on the critical path to first-chat. |
| Windows + dual-matrix CI | **Out of this series.** Linux x86_64 only. Windows becomes a future PRD, not silent “best effort.” |
| PyInstaller / Briefcase / `bundle create` | **Out.** Single channel = PyPI. PRD 08 [retired](08-packaging.md). |

## Ratified decisions (2026-09-01)

These diverge from the original plan and apply to all PRDs.

1. **`LLM()` defaults to `llm/small` at launch.** Medium is available only through config or `LLM("medium")`.
2. **No `LicenseError`.** License metadata is informational.
3. **Foundations without a registry.**
4. **OpenClaw is P1 in PRD 07.** Critical path = library + `serve` + Open WebUI.
5. **Tool use is P1 in PRD 02** and does not block first-chat.
6. **Linux x86_64 only.** No Windows support, CI, or templates in this series.
7. **Speckit does not start yet.** Constitution and specify remain for an explicit next step.
8. **Distribution only through PyPI.** No binary, installer, or `bundle create`. `--essentials` populates the cache; it is not a release.
9. **First public PyPI release = completion of PRD 02**, version **0.1.0**. PRDs 00 and 01 are not uploaded to the index (only `pip install -e .` from the repository). PRDs 03–07 republish the same package (minor versions, in merge order).

## PyPI publishing

| Milestone | Action | Rationale |
|---|---|---|
| PRD 00–01 | No upload to public PyPI. Metadata (`name`, Linux classifiers, `requires-python`) is already in `pyproject.toml`. TestPyPI is optional and used only to rehearse the pipeline. | A package without `LLM().chat()` is noise: `pip install ceia-aisdk` does not fulfill the promise. |
| **PRD 02** | **First publish: `ceia-aisdk==0.1.0`** (library + CLI + registry + LLM + `[cuda]` extra). Classifiers: POSIX/Linux, Python 3.11–3.13. PyPI README = 15-minute quickstart. | First slice in which the anchor KPI can be measured by an external user. |
| PRD 03–07 | New *minor* version of the same project for each merged PRD (`0.2.0`, `0.3.0`, …). Extras `[server]` and `[apps]` appear only in the version that delivers them. | A single product on PyPI; incremental features, not new packages. |

There is no “desktop” release. Models are **not** included in the wheel — only the SDK is; weights are placed in the cache through the registry.

## Delivery order

| # | PRD | Speckit slug | Depends on | Visible increment | PyPI |
|---|---|---|---|---|---|
| 00 | [Foundations](00-foundations.md) | `sdk-foundations` | — | `pip install -e .` + `doctor` | Not published |
| 01 | [Model registry](01-model-registry.md) | `model-registry` | 00 | `model pull/list/info` + cache | Not published |
| 02 | [LLM](02-llm.md) | `llm-module` | 00, 01 | `LLM().chat()` ≤15 min; `[cuda]` extra | **`0.1.0` (first)** |
| 03 | [Voice](03-voice.md) | `voice-stt-tts` | 00, 01 | `STT` + `TTS` | Next minor |
| 04 | [Vision](04-vision.md) | `vision-describe` | 02 | `Vision.describe` | Next minor |
| 05 | [RAG](05-rag.md) | `rag-module` | 01, 02 | `RAG.add` / `ask` / `retrieve` | Next minor |
| 06 | [Server](06-server.md) | `openai-server` | 02 (+ 03–05 if already available) | `ceia-aisdk serve` | Minor + `[server]` extra |
| 07 | [App launcher](07-app-launcher.md) | `app-launcher` | 06 | `app install openwebui` | Minor + `[apps]` extra |
| — | [08 Packaging](08-packaging.md) | — | — | Retired | — |

PRDs 03–05 may proceed in parallel after 02, provided they do not block 06. PRD 06 must expose only modules that have already been implemented. The *minor* number follows merge order, not the PRD number.

## Speckit (deferred)

When authorized by the team: ratify [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) (it is still a template), and only then run `/speckit-specify` for each PRD, in the order shown in the table.

## Technical baseline

- Python **3.11–3.13**, x86_64, **Linux** (Ubuntu 22.04+ as the reference).
- CI: Linux only, starting with PRD 00.
- Out of scope: Windows, Apple Silicon, ROCm, Vulkan, desktop packaging.
- Release channel: PyPI only (`ceia-aisdk` + extras). First public index release in PRD 02.

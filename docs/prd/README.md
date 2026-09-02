# Programa de PRDs — CEIA AI SDK (`ceia-aisdk`)

**Fonte de visão:** [docs/plans/2026-07-29-ai-sdk-x86-design.md](../plans/2026-07-29-ai-sdk-x86-design.md)
**Data do programa:** 2026-09-01
**Posicionamento:** produto público no PyPI — lib + CLI Python, Linux x86_64, competindo com Ollama/LM Studio no eixo *embutível em código*.
**KPI âncora:** time-to-first-chat ≤ 15 min em Linux x86_64 limpo, CPU, rede ok, **a partir de `pip install ceia-aisdk` no índice público**.
**OS alvo desta série:** Linux x86_64 apenas (Ubuntu 22.04+ como referência). Windows e Apple Silicon estão fora.
**Canal:** só PyPI. Sem binário, instalador ou loja.

Este diretório é a fonte de requisitos. Speckit entra **depois** — os PRDs são o contrato agora; specify/plan/tasks só quando o time pedir. Quando for a hora, **um PRD = uma feature Speckit**.

## Recorte incremental (obrigatório)

O plano original trata o escopo multimodal como “v1 sem cortes”. Isso é visão de produto, não fatia de entrega. Os PRDs abaixo entregam a visão **em série**, cada um shippável e testável.

Cortes explícitos vs. o plano (descoberta 2026-09-01):

| Item do plano | Destino no programa |
|---|---|
| Ed25519 + mirrors oficiais + `CatalogSignatureError` | Fora do MVP. Catálogo bundled + `sha256`. Volta como feature futura, não como PRD desta série. |
| `vision.ocr()` / `vision.detect()` (ONNX) | Fora do MVP. Visão = só `Vision.describe`. |
| Docs como etapa 10 isolada | **Não há PRD de docs.** Cada PRD inclui o incremento de documentação daquela fatia. |
| CUDA auto-detect + extra `[cuda]` | **Dentro.** Primeiro demo exige inferência CUDA real no PRD 02. |
| Sync + async espelhados | **Dentro**, a partir do PRD 02 (não no 00). |
| App launcher Open WebUI + OpenClaw | **Dentro**, no PRD 07, depois do server. OpenClaw é P1 do 07, não do caminho crítico até first-chat. |
| Windows + CI matriz dual | **Fora desta série.** Linux x86_64 only. Windows vira PRD futuro, não “best effort” silencioso. |
| PyInstaller / Briefcase / `bundle create` | **Fora.** Canal único = PyPI. PRD 08 [retirado](08-packaging.md). |

## Decisões ratificadas (2026-09-01)

Divergem do plano original e valem para todos os PRDs.

1. **`LLM()` defaulta para `llm/small` no lançamento.** Medium só via config ou `LLM("medium")`.
2. **Sem `LicenseError`.** Metadata de licença é informativa.
3. **Foundations sem registry.**
4. **OpenClaw é P1 do PRD 07.** Caminho crítico = lib + `serve` + Open WebUI.
5. **Tool-use é P1 no PRD 02**, não bloqueia first-chat.
6. **Linux x86_64 only.** Sem suporte, CI ou templates Windows nesta série.
7. **Speckit ainda não começa.** Constitution e specify ficam para um próximo passo explícito.
8. **Distribuição só via PyPI.** Sem binário, instalador ou `bundle create`. `--essentials` é cache, não release.
9. **Primeiro PyPI público = fechamento do PRD 02**, versão **0.1.0**. Os PRDs 00 e 01 não sobem ao índice (só `pip install -e .` no repo). 03–07 republicam o mesmo pacote (minor, na ordem de merge).

## Publicação PyPI

| Momento | Ação | Por quê |
|---|---|---|
| PRD 00–01 | Sem upload ao PyPI público. Metadata (`name`, classifiers Linux, `requires-python`) já no `pyproject.toml`. TestPyPI opcional só para ensaiar o pipeline. | Pacote sem `LLM().chat()` é ruído: `pip install ceia-aisdk` não cumpre a promessa. |
| **PRD 02** | **Primeiro publish: `ceia-aisdk==0.1.0`** (lib + CLI + registry + LLM + extra `[cuda]`). Classifiers: POSIX/Linux, Python 3.11–3.13. README do PyPI = quickstart de 15 min. | Primeira fatia em que o KPI âncora é mensurável pelo usuário externo. |
| PRD 03–07 | Novo *minor* do mesmo projeto a cada PRD merged (`0.2.0`, `0.3.0`, …). Extras `[server]` e `[apps]` só aparecem na versão que os entrega. | Um único produto no PyPI; features incrementais, não pacotes novos. |

Não existe release “desktop”. Modelos **não** vão no wheel — só o SDK; pesos caem no cache via registry.

## Ordem de entrega

| # | PRD | Slug Speckit | Depende de | Incremento visível | PyPI |
|---|---|---|---|---|---|
| 00 | [Foundations](00-foundations.md) | `sdk-foundations` | — | `pip install -e .` + `doctor` | Não publica |
| 01 | [Model registry](01-model-registry.md) | `model-registry` | 00 | `model pull/list/info` + cache | Não publica |
| 02 | [LLM](02-llm.md) | `llm-module` | 00, 01 | `LLM().chat()` ≤15 min; extra `[cuda]` | **`0.1.0` (primeiro)** |
| 03 | [Voz](03-voice.md) | `voice-stt-tts` | 00, 01 | `STT` + `TTS` | Minor seguinte |
| 04 | [Visão](04-vision.md) | `vision-describe` | 02 | `Vision.describe` | Minor seguinte |
| 05 | [RAG](05-rag.md) | `rag-module` | 01, 02 | `RAG.add` / `ask` / `retrieve` | Minor seguinte |
| 06 | [Server](06-server.md) | `openai-server` | 02 (+ 03–05 se já existirem) | `ceia-aisdk serve` | Minor + extra `[server]` |
| 07 | [App launcher](07-app-launcher.md) | `app-launcher` | 06 | `app install openwebui` | Minor + extra `[apps]` |
| — | [08 Packaging](08-packaging.md) | — | — | Retirado | — |

PRDs 03–05 podem avançar em paralelo depois do 02, desde que não bloqueiem o 06. O 06 deve expor só os módulos já implementados. O número *minor* segue a ordem de merge, não o número do PRD.

## Speckit (adiado)

Quando o time autorizar: ratificar [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) (ainda é template) e só então `/speckit-specify` por PRD, na ordem da tabela.

## Baseline técnico

- Python **3.11–3.13**, x86_64, **Linux** (Ubuntu 22.04+ de referência).
- CI: Linux only a partir do PRD 00.
- Fora: Windows, Apple Silicon, ROCm, Vulkan, empacotamento desktop.
- Canal de release: PyPI apenas (`ceia-aisdk` + extras). Primeiro índice público no PRD 02.

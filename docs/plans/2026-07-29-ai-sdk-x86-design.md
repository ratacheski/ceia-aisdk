# Design: SDK de IA local para PCs x86

**Data:** 2026-07-29
**Atualizado:** 2026-09-01
**Status:** Design validado — pronto para planejamento de implementação
**Nome oficial:** `ceia-aisdk`

| Superfície | Identificador |
|---|---|
| Produto | CEIA AI SDK |
| PyPI / CLI | `ceia-aisdk` |
| Import Python | `ceia_aisdk` |
| Cache e config | `~/.ceia-aisdk/` |
| Env vars | `CEIA_AISDK_*` |
| Logging | `ceia_aisdk.*` |
| Org HuggingFace | `ceia-aisdk` |

Classes internas (`AISDKConfig`, `AISDKError` e subclasses) mantêm o prefixo curto `AISDK` — o acrônimo ainda descreve o produto.

---

## TL;DR

SDK Python para PCs x86 (Windows/Linux) que entrega capabilities multimodais de IA local — LLM, STT, TTS, visão computacional e RAG — com API modular por domínio, defaults inteligentes e escape hatches para customização. Distribuído via `pip` como `ceia-aisdk`, com registry de modelos opaco e versionado (catálogo assinado Ed25519, pesos numa org HuggingFace com mirrors e o mesmo `sha256`), modo servidor OpenAI-compat, e um app launcher que instala Open WebUI e OpenClaw apontando para o servidor local. Backends escolhidos por maturidade: `llama-cpp-python`, `faster-whisper`, `piper-tts`, `sentence-transformers`, `lancedb`. Hardware alvo: CPU + auto-detecção de NVIDIA CUDA. Modelos são lazy no primeiro uso de cada módulo; `ceia-aisdk model pull --essentials` prepara o conjunto mínimo offline.

---

## 1. Visão e princípios norteadores

### Visão

Um SDK Python para PCs x86 (Windows/Linux) que entrega capabilities multimodais de IA local (LLM, STT, TTS, visão, RAG) com API modular, zero-config nos defaults e escape hatches para quem precisa customizar.

### Personas atendidas

- **Dev hobbyista / prototipador** — quer 3 linhas de código e "just works". Consumo típico: `pip install ceia-aisdk` → `from ceia_aisdk.llm import LLM` → conversar.
- **Dev de produto** — quer embutir em app desktop (via PyInstaller/Briefcase). Precisa de controle sobre modelo, cache path, logging e distribuição confiável.
- **Usuário final** — nunca vê o SDK diretamente. Consome apps de referência que empacotam o SDK e escondem tudo.

### Três camadas do produto

1. **Lib Python** (`import ceia_aisdk`) — para devs consumirem em código.
2. **Server mode** (`ceia-aisdk serve`) — expõe API HTTP OpenAI-compatible, permitindo que qualquer cliente do ecossistema (LangChain, LibreChat, Continue, etc.) use o SDK como backend local.
3. **App launcher** (`ceia-aisdk app install <nome>`) — instala frontends OSS pré-configurados apontando para o servidor local. Habilita "produto pronto" para end-user em minutos. Apps de referência do v1: **Open WebUI** (chat) e **OpenClaw** (agente).

### Cinco princípios de design

1. **Defaults inteligentes acima de configuração.** Toda função pública funciona sem argumentos.
2. **API modular por domínio.** `ceia_aisdk.llm`, `ceia_aisdk.stt`, `ceia_aisdk.tts`, `ceia_aisdk.vision`, `ceia_aisdk.rag` — cada um autocontido; import não puxa o resto.
3. **Sync-first, async-parallel.** Todo método público tem versão sync (`.chat`) e async (`.achat`) espelhadas, como `openai` e `httpx`.
4. **Hardware transparente.** Auto-detect CUDA na inicialização, cai para CPU sem alarme. Dev pode forçar via `device="cpu"` ou env var.
5. **Modelos são artefatos versionados e opacos.** Aliases estáveis (`llm/small@N`), download on-demand com checksum, cache determinístico, e o modelo real por trás nunca é exposto publicamente.

### Não-objetivos

- Não substitui LangChain/LlamaIndex — não é framework de agentes.
- Não roda em Apple Silicon como target primário (x86 first).
- Não faz fine-tuning — só inferência.
- Não hospeda servidor por padrão (embora exista modo servidor opcional).

---

## 2. Arquitetura e módulos

### Layout do pacote Python

```
ceia_aisdk/
├── __init__.py          # exporta helpers de topo (versão, config)
├── config.py            # AISDKConfig (paths, device, log level)
├── hardware.py          # detect_cuda(), get_device(), memory_info()
├── registry/            # catálogo de modelos + resolver + downloader
│   ├── catalog.py       # aliases curados (opaco) → arquivos internos
│   ├── downloader.py    # HTTP + resume + progress bar + failover de mirrors
│   ├── signing.py       # verificação Ed25519 do catálogo
│   └── cache.py         # ~/.ceia-aisdk/models/ layout, lockfiles
├── llm/                 # texto + visão (via LLaVA/MiniCPM-V)
│   ├── model.py         # class LLM (sync)
│   └── async_model.py   # class AsyncLLM (asyncio)
├── stt/                 # faster-whisper wrapper
├── tts/                 # Piper wrapper
├── vision/              # atalho para LLM visual + módulos ONNX (OCR, detect)
├── rag/                 # LanceDB + BGE-small + loaders (PDF/DOCX/MD/TXT)
├── server/              # FastAPI: rotas OpenAI-compat
│   └── openai_compat.py # /v1/chat/completions, /v1/embeddings, /v1/audio/*
├── apps/                # launcher de apps OSS
│   ├── registry.py      # catálogo de apps (openwebui, openclaw)
│   └── runner.py        # install, configure, run, uninstall
└── cli.py               # comando `ceia-aisdk` (Typer)
```

### Backends escolhidos

| Domínio | Backend | Formato | Notas |
|---|---|---|---|
| LLM + visão | `llama-cpp-python` | GGUF | Cobre chat + LLaVA/MiniCPM-V no mesmo runtime, CUDA + CPU nativos |
| STT | `faster-whisper` | CTranslate2 | ~4x mais rápido que openai/whisper, CUDA nativo |
| TTS | `piper-tts` | ONNX | Leve, boa qualidade, PT-BR disponível |
| Embeddings | `sentence-transformers` + `onnxruntime` | ONNX | BGE-small default (~130MB), roda em CPU |
| Vector store | `lancedb` | arquivo local | Zero setup, single file |
| Visão específica (OCR/detect) | `onnxruntime` | ONNX | YOLO, PaddleOCR opcionais |
| Server HTTP | `FastAPI` + `uvicorn` | — | Rotas OpenAI-compat |
| CLI | `Typer` + `Rich` | — | UX moderna |

### Dependências opcionais (extras)

- `ceia-aisdk[cuda]` — força build do `llama-cpp-python` com CUDA.
- `ceia-aisdk[server]` — inclui FastAPI/uvicorn.
- `ceia-aisdk[apps]` — inclui runner de apps.

**Instalação base:** `pip install ceia-aisdk` (~50 MB, só SDK + bindings). Modelos são pulled on-demand.

---

## 3. Registry de modelos e ciclo de vida

### Aliases opacos e versionados

Todo alias curado carrega uma versão (`@N`) que fixa o artefato de forma **imutável**. Uma vez publicada, `llm/medium@3` nunca muda de arquivo — é reproduzível para sempre. O modelo real por trás **nunca** é exposto na API pública.

```python
LLM()                    # alias default (llm/medium@latest para a versão do SDK)
LLM("small")             # alias sem versão → resolve para @latest da versão instalada
LLM("small@2")           # pinning explícito, congela contra atualizações
LLM("hf://TheBloke/...") # bypass total (dev assume responsabilidade)
LLM("/path/local.gguf")  # bring-your-own
```

### Update policy

`@latest` de cada alias é fixado pela versão do SDK instalada. Atualizar de `ceia-aisdk 1.4` para `1.5` pode mudar o modelo atrás de `llm/medium`, mas dentro da mesma versão do SDK nunca muda. Elimina o "modelo silenciosamente atualizado de madrugada".

### Catálogo interno vs. metadata pública

Arquivo interno (`ceia_aisdk/registry/_internal_catalog.yaml`, não exposto na API pública):

```yaml
llm/medium@3:
  _internal:
    repo: <hidden>
    file: <hidden>
    sha256: <hidden>
    mirrors:
      - https://huggingface.co/ceia-aisdk/...
      - https://<mirror-2>/...
  public:
    license_family: apache-2.0
    commercial_use: true
    context_length: 32768
    size_gb: 4.3
    capabilities: [chat, tool_use, multilingual]
    quantization_class: standard
```

`ceia-aisdk model info llm/medium@3` retorna **apenas a parte `public`**. Nunca a `_internal`. O submódulo `_internal_catalog` fica atrás de underscore para deixar claro "não é API".

### Metadata pública exposta

- `license_family` (apache-2.0, mit, llama-community, gemma, custom, ...)
- `commercial_use` (bool)
- `context_length`
- `size_gb`
- `capabilities` (lista: chat, tool_use, multilingual, vision, ...)
- `quantization_class` (compact, standard, high-quality)

Motivo: usuários deployando comercialmente precisam saber a licença. Compliance fica com o usuário; SDK expõe o mínimo necessário para ele decidir.

### Cache no disco (opaco)

```
~/.ceia-aisdk/
├── models/
│   ├── llm/
│   │   └── medium-v3.bin      # nome opaco, sem referência ao modelo real
│   ├── stt/
│   └── ...
├── registry.lock              # snapshot da versão do catálogo
└── config.toml
```

Nota: um `strings` no arquivo GGUF ainda pode vazar metadata embutida pelos autores originais. Isso é aceitável — não estamos protegendo contra atacante determinado, só evitando dependência acidental por parte do dev.

### Hospedagem, mirrors e failover

Fonte primária dos pesos curados: **organização HuggingFace `ceia-aisdk`**. HF cobre resume (range requests), CDN global e o fluxo que empresas e firewalls já conhecem.

Cada artefato no catálogo declara uma lista ordenada de URLs com o **mesmo `sha256`**:

1. HuggingFace (`huggingface.co/ceia-aisdk/...`) — primário.
2. Um ou mais mirrors oficiais (mesmo objeto, mesmo checksum). Podem ser outro endpoint HF, object storage ou CDN; a identidade do arquivo é o hash, não o host.
3. Se todos falharem: `DownloadError` com `.remediation` apontando para `CEIA_AISDK_CATALOG` e modo offline.

Política de failover do downloader:

- Tenta o próximo mirror só após erro de rede, HTTP 5xx, timeout ou checksum inválido.
- Checksum inválido **não** é silenciado — o arquivo parcial é descartado e o próximo mirror é tentado.
- Sem BitTorrent: complexidade, UX e superfície legal desproporcionais ao ganho.
- Empresas / air-gap: `CEIA_AISDK_CATALOG` aponta para um catálogo próprio (HTTP ou path local). O downloader respeita as URLs daquele catálogo e não tenta a org pública.

O catálogo bundled no wheel é a fonte de verdade da versão instalada. Refresh remoto do catálogo é opt-in (`CEIA_AISDK_CATALOG=https://...`) e só é aceito se a assinatura Ed25519 for válida.

### Assinatura e verificação do catálogo

O catálogo é um artefato de confiança: ele diz *o que* baixar e *qual hash* aceitar. Sem assinatura, um MITM em `CEIA_AISDK_CATALOG` (ou um mirror de catálogo) poderia trocar URL e checksum juntos.

- Algoritmo: **Ed25519**.
- Chave pública embarcada no wheel (`ceia_aisdk/registry/keys/catalog.pub`). Rotação = nova versão do SDK.
- Todo catálogo publicado tem `catalog.yaml` + `catalog.yaml.sig`.
- Catálogo bundled: verificado na primeira carga do registry (integridade já reforçada pelo wheel/PyPI).
- Catálogo remoto ou path via `CEIA_AISDK_CATALOG`: **assinatura obrigatória**. Rejeitado com `CatalogSignatureError` se faltar `.sig`, se a chave não bater ou se o payload divergir.
- Escape hatch: `CEIA_AISDK_ALLOW_UNSIGNED_CATALOG=1` aceita catálogo sem assinatura e emite warning explícito (air-gap / lab). Default: off.
- `ceia-aisdk model verify` revalida assinatura do catálogo em uso **e** o `sha256` de cada artefato em cache.

### Download e integridade

- CLI: `ceia-aisdk model pull llm/small`, ou lazy no primeiro uso da API.
- HTTP com resume (range requests), progress bar via Rich, checksum obrigatório, failover conforme acima.
- Mirrors e catálogo privado via `CEIA_AISDK_CATALOG`.

### Bundle essenciais (não automático)

`pip install ceia-aisdk` **não** baixa modelos. Cada módulo, no primeiro uso, puxa só o alias default daquele domínio (`LLM()` → `llm/medium`, `STT()` → `stt/fast`, etc.).

Para preparar um conjunto mínimo offline (CI, demo, máquina sem rede depois):

```bash
ceia-aisdk model pull --essentials
```

Aliases do bundle essentials (sempre as versões `@latest` pinadas pela versão do SDK):

| Alias | Papel | Ordem de grandeza |
|---|---|---|
| `llm/small` | chat viável em CPU | ~1–2 GB |
| `stt/fast` | transcrição | ~150 MB |
| `tts/pt-br` | voz PT-BR (default do bundle; `tts/en-us` entra se `CEIA_AISDK_TTS_LOCALE=en-us`) | ~60 MB |
| `embed/default` | RAG / embeddings | ~130 MB |

`ceia-aisdk bundle create` continua sendo o mecanismo para *packagers* escolherem um manifesto arbitrário (não só essentials) e embutirem os pesos no artefato do app.

### Comandos de gestão

- `ceia-aisdk model list`
- `ceia-aisdk model pull <alias>`
- `ceia-aisdk model pull --essentials`
- `ceia-aisdk model rm <alias>`
- `ceia-aisdk model info <alias>` — mostra só metadata pública
- `ceia-aisdk model verify` — re-checa assinatura do catálogo + integridade dos arquivos
- `ceia-aisdk model where <alias>` — imprime caminho no cache

### Trade-off assumido

Devs que precisam debugar profundamente vão usar `hf://` URLs explícitas ou modelos locais. É o preço da opacidade — registrado nas docs.

---

## 4. API concreta por módulo

Sync/async espelhados; zero-config no default; escape hatches disponíveis.

### LLM (texto + tool use)

```python
from ceia_aisdk.llm import LLM

llm = LLM()                                     # llm/medium@latest, auto-device
resp = llm.chat("Explica RAG em uma frase")     # str

for chunk in llm.stream("Escreve um haiku"):    # iterador de str
    print(chunk, end="", flush=True)

# Sessão multi-turn
chat = llm.session(system="Você é conciso.")
chat.send("Oi")
chat.send("Me lembra o que perguntei antes?")

# Async espelhado
from ceia_aisdk.llm import AsyncLLM
llm = AsyncLLM()
resp = await llm.chat("...")
async for chunk in llm.stream("..."):
    ...
```

### STT (áudio → texto)

```python
from ceia_aisdk.stt import STT

stt = STT()                                          # stt/fast@latest
text = stt.transcribe("audio.wav")                   # str
result = stt.transcribe("audio.wav", timestamps=True)

# Streaming de microfone
for partial in stt.stream_microphone():
    print(partial)
```

### TTS (texto → áudio)

```python
from ceia_aisdk.tts import TTS

tts = TTS(voice="pt-br")                             # tts/pt-br@latest
tts.speak("Olá, mundo").play()
tts.speak("Olá").save("out.wav")
```

### Visão (imagem + prompt)

```python
from ceia_aisdk.vision import Vision

v = Vision()                                         # vision/small@latest
answer = v.describe("foto.jpg", prompt="O que está errado nessa configuração?")

# Utilitários específicos (ONNX)
from ceia_aisdk.vision import ocr, detect
texto = ocr("nota-fiscal.png")
boxes = detect("garagem.jpg", classes=["car", "person"])
```

### RAG (zero-config)

```python
from ceia_aisdk.rag import RAG

kb = RAG("meu-kb")                                   # ~/.ceia-aisdk/rag/meu-kb
kb.add("./docs/")                                    # PDF, MD, DOCX, TXT, HTML
kb.add("https://exemplo.com/pagina.html")
answer = kb.ask("Como configurar X?")                # resposta + sources

# Escape hatch para só retrieval
chunks = kb.retrieve("Como configurar X?", top_k=5)
```

### Servidor OpenAI-compat (CLI)

```bash
ceia-aisdk serve --port 11434 --host 127.0.0.1
# Qualquer cliente OpenAI aponta base_url para localhost:11434
```

### App launcher (CLI)

Apps de referência do v1, ambos OSS e apontando ao `ceia-aisdk serve`:

| App | Papel | Instalação | Fontes |
|---|---|---|---|
| `openwebui` | Chat multimodal no browser | Docker (preferencial) ou pip | [Open WebUI](https://github.com/open-webui/open-webui) |
| `openclaw` | Agente self-hosted (canais + Control UI + tools) | npm (`openclaw@latest`) | [openclaw/openclaw](https://github.com/openclaw/openclaw) · [docs](https://docs.openclaw.ai) · MIT |

OpenClaw (v2026.8.x / 2.0) aceita provider OpenAI-compat via `baseUrl`. O runner grava em `~/.openclaw/openclaw.json` um provider local:

```json5
{
  models: {
    mode: "merge",
    providers: {
      ceia: {
        baseUrl: "http://127.0.0.1:11434/v1",
        api: "openai-completions",
        apiKey: "ceia-local",
        models: [{ id: "llm/medium", name: "CEIA medium" }]
      }
    }
  },
  agents: { defaults: { model: { primary: "ceia/llm/medium" } } }
}
```

Usa-se `openai-completions` (`/v1/chat/completions`), não o dialecto nativo do Ollama. Tool calling precisa estar correto nessa rota — é contrato do modo servidor.

```bash
ceia-aisdk app list                    # openwebui, openclaw
ceia-aisdk app install openwebui       # baixa e configura apontando ao server local
ceia-aisdk app install openclaw
ceia-aisdk app run openwebui           # abre no browser
ceia-aisdk app stop openwebui
```

---

## 5. Cross-cutting concerns

### Configuração em camadas

Precedência do mais forte para o mais fraco:

1. Kwargs por chamada: `LLM(device="cpu", cache_dir="/tmp")`
2. Env vars: `CEIA_AISDK_DEVICE`, `CEIA_AISDK_CACHE_DIR`, `CEIA_AISDK_LOG_LEVEL`, `CEIA_AISDK_CATALOG`, `CEIA_AISDK_OFFLINE`, `CEIA_AISDK_ALLOW_UNSIGNED_CATALOG`, `CEIA_AISDK_TTS_LOCALE`
3. Arquivo de config: `~/.ceia-aisdk/config.toml`
4. Defaults do SDK

```toml
# ~/.ceia-aisdk/config.toml
[core]
device = "auto"          # auto | cpu | cuda | cuda:0
cache_dir = "~/.ceia-aisdk"
log_level = "INFO"
offline = false          # se true, falha em vez de tentar download

[llm]
default_alias = "medium"
context_length = 8192

[server]
host = "127.0.0.1"       # NUNCA 0.0.0.0 por default
port = 11434
require_token = false
```

### Detecção de hardware

Na primeira chamada de cada módulo, `get_device()`:

- Tenta importar `torch.cuda` / checar `nvidia-smi` e `cuda_runtime`.
- Se disponível: verifica VRAM livre; se não couber o modelo pedido, cai para CPU com warning.
- Log claro: `[ceia_aisdk.hardware] Using device: cuda:0 (RTX 3060, 12GB VRAM, 8.2GB free)`.
- CLI `ceia-aisdk doctor` imprime detecção completa, versões de bindings, drivers e sanity checks. Vira o comando de "abrir issue".

### Logging & observabilidade

- `logging` padrão do Python, namespace `ceia_aisdk.*`. Silent por default (`WARNING`).
- Callback opcional para métricas: `ceia_aisdk.set_metrics_hook(fn)` recebe eventos `{event, module, alias, duration_ms, tokens, ...}` — dev pluga em Prometheus/OpenTelemetry.
- **Telemetria out-of-the-box: zero.** Nada é enviado para servidor externo sem opt-in explícito (`CEIA_AISDK_TELEMETRY=1`). Local-first significa privacy-first.

### Hierarquia de erros

```
AISDKError                   # raiz
├── ModelNotFoundError       # alias inexistente
├── DownloadError            # rede, checksum, disco cheio, mirrors esgotados
├── CatalogSignatureError    # catálogo remoto sem sig válida
├── DeviceError              # CUDA OOM, driver mismatch
├── BackendError             # falha do llama.cpp/whisper/etc.
└── LicenseError             # tentativa de uso comercial de modelo não-comercial
```

Cada erro tem `.remediation` (string amigável): `"CUDA OOM. Try a smaller alias like 'llm/small' or set device='cpu'."`

### Thread-safety & concorrência

- Instâncias de `LLM/STT/TTS` **não** são thread-safe (backend nativo compartilhado). Docstrings deixam explícito.
- Concorrência real: `AsyncLLM` (asyncio) ou pool de instâncias.
- Server mode gerencia pool internamente — dev não vê.

### Segurança do server mode

- Bind em `127.0.0.1` por default (nunca `0.0.0.0`).
- `--token <segredo>` habilita Bearer auth.
- CORS restrito por default (localhost); flag `--cors <origins>` afrouxa explicitamente.
- Sem persistência de conversas no server; stateless entre requests.

### Empacotamento para apps end-user

- Guia + templates com PyInstaller e Briefcase.
- App empacotado herda cache do SDK; pode incluir "modelos essenciais" pré-baixados via `ceia-aisdk bundle create`.

---

## 6. Etapas de desenvolvimento

Ordem por dependência técnica. Escopo completo — sem cortes de MVP nem prazos.

### Etapa 1 — Fundações

Base sobre a qual tudo se apoia.

- Setup do repo (`pyproject.toml` com nome `ceia-aisdk`, extras, CI matriz Linux/Windows).
- Sistema de config em camadas (`AISDKConfig`, env vars `CEIA_AISDK_*`, TOML em `~/.ceia-aisdk/`).
- Módulo `hardware.py` (detecção CUDA, VRAM, escolha de device com fallback).
- Hierarquia de erros (`AISDKError` + subclasses com `.remediation`, incluindo `CatalogSignatureError`).
- Logging namespaced (`ceia_aisdk.*`).
- CLI base com `Typer`, comando `ceia-aisdk`, subcomando `ceia-aisdk doctor`.

### Etapa 2 — Registry e cache de modelos

Pré-requisito de todos os módulos de inferência.

- Schema do catálogo interno (YAML) com aliases versionados (`@N` imutável) e lista de mirrors por artefato.
- Camada de metadata pública (opacidade — só `license_family`, capabilities, size).
- Assinatura Ed25519 (`catalog.yaml.sig`), chave pública no wheel, rejeição de catálogo remoto unsigned (salvo escape hatch).
- Resolver de aliases (`llm/medium` → `llm/medium@N`).
- Downloader com resume, checksum, failover de mirrors, progress bar.
- Cache manager (`~/.ceia-aisdk/models/`, lockfiles, cleanup).
- Subcomandos CLI: `model pull/list/rm/info/verify/where` e `model pull --essentials`.

### Etapa 3 — Módulo LLM

Primeiro backend real; valida toda a infra anterior.

- Integração `llama-cpp-python` com auto-device.
- `LLM` sync: `.chat`, `.stream`, `.session`, tool-use.
- `AsyncLLM` espelhado.
- Curadoria dos aliases `llm/small|medium|large@N` no catálogo interno.

### Etapa 4 — Módulos de voz

Reutilizam registry/cache da Etapa 2.

- STT via `faster-whisper` (transcribe, timestamps, stream de microfone) — sync + async.
- TTS via `piper-tts` (speak → play/save) — sync + async.
- Aliases `stt/fast|accurate@N`, `tts/pt-br|en-us@N`.

### Etapa 5 — Módulo de visão

Depende do backend LLM da Etapa 3.

- Multimodal via `Vision().describe(image, prompt)` reaproveitando runtime da Etapa 3 com LLaVA/MiniCPM-V.
- Utilitários ONNX independentes: `vision.ocr()`, `vision.detect()`.
- Aliases `vision/small@N`, `vision/ocr@N`, `vision/detect@N`.

### Etapa 6 — Módulo RAG

Depende do LLM (para `.ask`); `.retrieve` é independente.

- Backend de embeddings via `sentence-transformers` / ONNX (aliases `embed/default@N`, `embed/multilingual@N`).
- Integração `lancedb` (KB por nome, arquivo local).
- Loaders (PDF, DOCX, MD, TXT, HTML) + chunking recursivo.
- API `RAG.add / ask / retrieve / list / delete`.

### Etapa 7 — Modo servidor

Depende dos módulos anteriores; expõe tudo via HTTP.

- FastAPI + uvicorn como extra opcional (`ceia-aisdk[server]`).
- Rotas OpenAI-compat: `/v1/chat/completions` (SSE stream + tool calling), `/v1/embeddings`, `/v1/audio/transcriptions`, `/v1/audio/speech`, `/v1/models` (retorna só aliases opacos).
- Bearer auth opcional, CORS restrito, bind localhost por default.
- Pool interno de instâncias com backpressure.

### Etapa 8 — App launcher

Depende do modo servidor (Etapa 7).

- Registry de apps (YAML: método de instalação por app — docker / pip / npm / git+script).
- Runner: install, configure para apontar ao server local, run, stop, status, uninstall.
- Configs bundled:
  - **Open WebUI** — Docker, `OPENAI_API_BASE_URL=http://127.0.0.1:11434/v1`.
  - **OpenClaw** — npm, provider `ceia` com `baseUrl` local e `api: openai-completions` (ver §4).
- Subcomandos CLI `app list/install/run/stop/status/uninstall`.

### Etapa 9 — Suporte a empacotamento

Independente das últimas etapas; pode ir em paralelo.

- Comando `ceia-aisdk bundle create` (gera manifesto de modelos pré-baixados).
- `ceia-aisdk model pull --essentials` como atalho do manifesto mínimo.
- Template PyInstaller.
- Template Briefcase.
- Guia de distribuição para apps end-user.

### Etapa 10 — Documentação e exemplos

Transversal, mas ganha corpo depois de cada etapa acima.

- Referência de API (mkdocs-material).
- Quickstarts por módulo.
- Cookbooks (assistente de voz, chat com documentos, análise de screenshots).
- Docs específicas: opacidade, licenças, empacotamento, troubleshooting, verificação do catálogo.

---

## Log de decisões

| # | Decisão | Alternativas descartadas |
|---|---|---|
| 1 | Público-alvo: devs e usuários finais (via apps) | Apenas devs; apenas pesquisadores |
| 2 | Linguagem: Python com apps de referência empacotados | Rust/C++ com bindings; Node/TS; C#/Go |
| 3 | Escopo: multimodal completo desde o v1 | Focar em LLM+RAG; focar em voz; focar em visão |
| 4 | Hardware: CPU + NVIDIA CUDA auto-detect | Só CPU; multi-backend (ROCm/Vulkan); mini-PC/edge |
| 5 | Distribuição de modelos: registry on-demand (estilo Ollama) | Bundled; híbrido; bring-your-own-model |
| 6 | Estilo de API: módulos separados por domínio | Funcional; façade unificada; múltiplos coexistindo |
| 7 | RAG: zero-config | Config em camadas; componentes componíveis; wrapper de LangChain |
| 8 | Concorrência: sync + async paralelos (`chat`/`achat`) | Sync + streaming opcional; streaming-first; async-first |
| 9 | Catálogo: curados + custom por URL/path | Só curados; catálogo aberto tipo HF |
| 10 | Opacidade: aliases versionados imutáveis (`@N`) | Full opaque; opaco com backdoor; runtime opaco + doc revela |
| 11 | Metadata pública: só família de licença + capabilities | Esconder também licença; expor tudo |
| 12 | Produto em 3 camadas: lib + server + app launcher | Só lib; lib + app único |
| 13 | Nome oficial: `ceia-aisdk` (import `ceia_aisdk`) | `aisdk` (PyPI ocupado + genérico); `aisdk-local` |
| 14 | Apps bundled: Open WebUI + OpenClaw | Continue; Aider; Open Interpreter; adiar o agente |
| 15 | Pesos: org HF `ceia-aisdk` + mirrors no catálogo + `CEIA_AISDK_CATALOG` | Só HF; CDN própria como primária; torrent; só self-host no v1 |
| 16 | Catálogo assinado Ed25519; remoto unsigned só com escape hatch | Confiar só no wheel; adiar assinatura |
| 17 | Sem download na instalação; lazy por módulo + `model pull --essentials` | Auto-baixar essentials no primeiro import; nenhum bundle nomeado |

---

## Questões resolvidas (2026-09-01)

Todas as questões abertas do design original foram fechadas nesta revisão.

- **Nome definitivo.** Produto/PyPI/CLI: `ceia-aisdk`. Import: `ceia_aisdk`. Cache: `~/.ceia-aisdk`. Env: `CEIA_AISDK_*`. `aisdk` no PyPI está ocupado por um stub de 2021 e colide conceitualmente com o AI SDK da Vercel.
- **Agente de código OSS.** OpenClaw confirmado ([github.com/openclaw/openclaw](https://github.com/openclaw/openclaw), MIT, [docs.openclaw.ai](https://docs.openclaw.ai), v2026.8.x / 2.0). Aceita `baseUrl` OpenAI-compat; o launcher configura o provider `ceia` contra `ceia-aisdk serve`. Segundo app: Open WebUI.
- **Mirrors do catálogo.** Org HuggingFace `ceia-aisdk` como primário; cada artefato lista mirrors com o mesmo `sha256`; failover automático; `CEIA_AISDK_CATALOG` para air-gap. Sem torrent.
- **Assinatura do catálogo.** Ed25519, chave pública no wheel, `catalog.yaml.sig` obrigatório em catálogo remoto. `CEIA_AISDK_ALLOW_UNSIGNED_CATALOG=1` é o escape hatch. `model verify` cobre sig + checksums. Novo erro: `CatalogSignatureError`.
- **Bundle essenciais.** Nenhum download silencioso no `pip install`. Lazy no primeiro uso de cada módulo. `ceia-aisdk model pull --essentials` baixa `llm/small`, `stt/fast`, `tts/pt-br` (ou `tts/en-us` via locale) e `embed/default`.

# PRD 02 — Módulo LLM

| Campo | Valor |
|---|---|
| ID | `PRD-02` |
| Status | Draft |
| Slug Speckit | `llm-module` |
| Depende de | PRD-00, PRD-01 |
| Desbloqueia | PRD 04, 05, 06; **primeiro PyPI** |
| PyPI | **`ceia-aisdk==0.1.0` — primeiro upload público.** |
| Plano de origem | Etapa 3 |

---

### 1. Executive Summary

- **Problem Statement**: O produto público só existe quando um dev faz `from ceia_aisdk.llm import LLM` e recebe uma resposta local. Sem isso, foundations e registry são infra invisível.
- **Proposed Solution**: Módulo `ceia_aisdk.llm` sobre `llama-cpp-python`, com `LLM` / `AsyncLLM`, chat, stream, session, device auto (CPU + CUDA), aliases `llm/small|medium|large@N`, e **publicação do pacote no PyPI como 0.1.0**.
- **Success Criteria**:
  - Em Linux x86_64 limpo, CPU, rede ok: do `pip install ceia-aisdk` **no PyPI público** (runtime CPU do llama-cpp incluso ou puxado como dep) até a primeira string de `LLM().chat("Diga apenas: ok")` em **≤ 15 minutos**, incluindo o pull de `llm/small`.
  - `ceia-aisdk==0.1.0` está no índice; classifiers declaram Linux; a página do PyPI mostra o quickstart e “Linux x86_64 only”.
  - A mesma chamada com `ceia-aisdk[cuda]` numa GPU NVIDIA com VRAM ≥ necessidade de `llm/small` conclui no device `cuda` (log contém `cuda`); se VRAM não couber, cai para CPU com WARNING e ainda devolve string.
  - `LLM().chat` e o primeiro token de `LLM().stream` em `llm/small` CPU: primeiro token ≤ 10 s após o modelo já residente em RAM (warm).
  - Import `ceia_aisdk` continua sem carregar `llama_cpp`; só `from ceia_aisdk.llm import LLM` (ou a primeira chamada) carrega o backend.
  - Matriz de testes: chat, stream, session (2 turnos com memória), device forçado `cpu`, e pelo menos 1 teste de `AsyncLLM` no mesmo comportamento.

---

### 2. User Experience & Functionality

- **User Personas**: hobbyista que descobriu o pacote no PyPI; script que pina `llm/small@2` e `device="cpu"`; usuário CUDA que espera “just works”.

- **User Stories**:

  **US-02-1 — First chat zero-config**
  - As a desenvolvedor, I want to instanciar `LLM()` e chamar `.chat` so that eu valide o SDK em minutos.
  - **Acceptance Criteria**:
    - **Default de lançamento: `llm/small@latest`**, não `medium`. Contestação ao plano: 4.3 GB quebra o KPI de 15 min em banda doméstica típica.
    - `config.toml [llm] default_alias = "medium"` e `LLM("medium")` continuam válidos.
    - Retorno de `.chat` é `str` não vazio para prompt de smoke.
    - Primeiro uso dispara `ensure_local` (PRD 01) com progress no TTY.
    - Offline + miss → `DownloadError`; não há hang > 1 s tentando rede se `offline`.

  **US-02-2 — Stream e sessão**
  - As a desenvolvedor, I want to stream e multi-turn so that o SDK sirva um chat real.
  - **Acceptance Criteria**:
    - `.stream(prompt)` é iterador de `str`; concatenação == conteúdo que `.chat` produziria sob mesma seed/temperature fixas no teste (ou equivalência documentada se o backend não for bit-stable — nesse caso o teste checa ≥ 1 chunk e texto final não vazio).
    - `.session(system=...)` mantém histórico; o segundo `.send` evidencia o primeiro (fixture com pergunta factual curta).
    - Thread-safety: docstring e docs dizem “não é thread-safe”.

  **US-02-3 — Async espelhado**
  - As a desenvolvedor, I want to `AsyncLLM` com `.chat` / `.stream` / sessão so that eu embuta em asyncio.
  - **Acceptance Criteria**:
    - Mesma semântica da classe sync.
    - Não bloquear o event loop no hot path de tokens além do permitido pelo binding (documentar se `llama-cpp-python` força executor). Teste: `asyncio` + timeout.

  **US-02-4 — CUDA de verdade**
  - As a desenvolvedor com NVIDIA, I want to `pip install ceia-aisdk[cuda]` so that a inferência use a GPU sem eu escolher flags do llama.cpp.
  - **Acceptance Criteria**:
    - Extra `[cuda]` instala/builda o binding com CUDA (pin e receita no README; wheel pré-buildado se o time conseguir — senão doc de compile ≤ 20 linhas).
    - `device="auto"` + GPU ok → layers na GPU; `doctor` após o extra mostra binding CUDA = yes.
    - OOM → `DeviceError` com remediation (`llm/small` ou `device="cpu"`), ou fallback CPU se ainda não começou a gerar.
    - O relógio de 15 min **não** inclui compile CUDA. CUDA é gate de qualidade, não do KPI âncora.

  **US-02-5 — Tool use (P1, não P0)**
  - As a desenvolvedor, I want to passar tools no chat so that o servidor (PRD 06) possa expor tools depois.
  - **Acceptance Criteria**:
    - API de tools alinhada ao formato OpenAI-ish (nome, json schema, chamada → resultado).
    - Pelo menos 1 teste com tool stub (`get_weather`) em que o modelo curado do catálogo *ou* um fixture/gravação demonstre o loop. Se o alias default não for confiável para tools, o teste usa um alias `llm/medium` marcado `capabilities: [tool_use]` e fica P1 — **não bloqueia** o merge do first-chat.
    - Aliases sem `tool_use` levantam erro claro se tools forem passadas.

  **US-02-6 — Publicar 0.1.0 no PyPI**
  - As a desenvolvedor externo, I want to `pip install ceia-aisdk` sem clonar o repo so that o produto exista de fato.
  - **Acceptance Criteria**:
    - Versão `0.1.0` no índice público.
    - Extra `[cuda]` instalável via `pip install ceia-aisdk[cuda]`.
    - Página do projeto declara Linux x86_64; não promete Windows.
    - Wheel/sdist **não** inclui pesos GGUF.

- **Non-Goals**:
  - Fine-tuning, embeddings (PRD 05), visão (PRD 04), server HTTP (PRD 06).
  - Multi-backend (vLLM, Ollama como runtime).
  - Garantir qualidade de bench vs GPT-cloud.
  - Default `medium` no `LLM()`.
  - Binário, instalador, bundle de pesos no wheel.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**:
  - Runtime: `llama-cpp-python` (GGUF).
  - Registry: `ensure_local("llm/small|medium|large")`.
  - Hardware: `get_device()` + `size_gb` do catálogo para fallback de VRAM.
- **Evaluation Strategy**:
  - Smoke obrigatório: prompt fixo, assert em substring ou regex (`ok` / não-vazio + max 64 tokens).
  - Golden de sessão: 2 turnos, assert de correferência simples.
  - Benchmark informal (não-gate): tokens/s CPU vs CUDA na máquina de referência; registrar no `doctor` ou log DEBUG.
  - Tool-use: teste P1 com modelo capable ou skip explícito se o artefato de CI for stub.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/llm/model.py` (`LLM`), `async_model.py` (`AsyncLLM`).
  - Construtor: resolve alias → `ensure_local` → instancia o binding com n_ctx de config (`[llm] context_length`, default 8192).
  - Fallback VRAM: se `size_gb` > livre * margem (documentar 0.9), device efetivo = cpu + WARNING.
- **Integration Points**:
  - Catálogo com três aliases LLM curados (artefatos reais ou placeholders até a org HF existir; CI usa fixture GGUF tiny).
  - CLI: nenhum subcomando novo obrigatório além do que o 01 já tem; quickstart no README.
- **Security & Privacy**:
  - Prompts não saem da máquina. Sem telemetria de conteúdo.
  - Instância não thread-safe — documentar risco de corrida, não “consertar” com lock global silencioso.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **P0 (gate do 0.1.0)**: `LLM` sync chat/stream/session + default `small` + CPU + extra `[cuda]` na máquina de referência + **upload PyPI** + README do índice.
  - **P1** (pode ir no 0.1.0 ou no primeiro patch): `AsyncLLM` + tool-use + fallback VRAM. Tool-use **não** bloqueia o 0.1.0.
  - **Depois**: default `medium` só se p95 pull+chat < 15 min na banda-alvo (TBD Mbps). Minors 03–07 no mesmo projeto PyPI.
- **Technical Risks**:
  - Build CUDA do `llama-cpp-python` é a falha #1 de onboarding. Mitigação: wheels documentados; `doctor` distingue “GPU visível” vs “binding sem CUDA”.
  - GGUF tiny de CI não prova qualidade. Mitigação: smoke de CI + checklist manual com alias real.
  - Default `small` vs plano (`medium`): divergência consciente; reverter exige atualizar este PRD e o KPI.

**Speckit:** feature `llm-module`. A spec deve separar P0/P1 nos critérios de aceite.

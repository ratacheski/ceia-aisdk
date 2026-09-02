# PRD 06 — Modo servidor OpenAI-compat

| Campo | Valor |
|---|---|
| ID | `PRD-06` |
| Status | Draft |
| Slug Speckit | `openai-server` |
| Depende de | PRD-02; expõe 03–05 se já merged |
| Desbloqueia | PRD 07; qualquer cliente do ecossistema |
| PyPI | Minor seguinte + extra `[server]` no mesmo pacote. |
| Plano de origem | Etapa 7 |

---

### 1. Executive Summary

- **Problem Statement**: Lib Python sozinha não ganha de Ollama no ecossistema. Sem HTTP OpenAI-compat, Continue, LibreChat e LangChain não apontam para o SDK.
- **Proposed Solution**: Extra `ceia-aisdk[server]` com FastAPI/uvicorn, `ceia-aisdk serve`, rotas `/v1/*` OpenAI-compat, bind localhost, token opcional, pool interno.
- **Success Criteria**:
  - `ceia-aisdk serve` (com extra) escuta `127.0.0.1:11434` e `GET /v1/models` devolve só aliases opacos, nunca nomes HF, em ≤ 2 s após ready.
  - `POST /v1/chat/completions` sem stream e com `stream: true` (SSE) reproduzem o comportamento do `LLM` do PRD 02 para o mesmo prompt (texto não vazio; stream tem ≥ 1 chunk `data:`).
  - Cliente oficial `openai` Python (ou httpx) com `base_url=http://127.0.0.1:11434/v1` completa um chat em teste de integração.
  - Bind default nunca é `0.0.0.0`. Request sem Bearer quando `--token` foi passado → 401 em 100% dos casos.
  - Rotas de módulos não instalados/não implementados → 404 ou 501 com corpo JSON estável, sem traceback.

---

### 2. User Experience & Functionality

- **User Personas**: hobbyista que aponta o cliente OpenAI para localhost; serviço Python que sobe `ceia-aisdk serve`; operador que liga `--token`.

- **User Stories**:

  **US-06-1 — Subir o server**
  - As a desenvolvedor, I want to `ceia-aisdk serve` so that qualquer cliente OpenAI fale com o SDK.
  - **Acceptance Criteria**:
    - Extra `[server]` puxa FastAPI + uvicorn. Sem o extra, o comando explica como instalar.
    - Flags: `--host` (default 127.0.0.1), `--port` (11434), `--token`, `--cors`.
    - Ready log contém URL absoluta.

  **US-06-2 — Chat completions + models**
  - As a desenvolvedor, I want to `/v1/chat/completions` e `/v1/models` so that eu substitua um endpoint OpenAI.
  - **Acceptance Criteria**:
    - Campos mínimos: `model`, `messages`, `stream`, `temperature`, `max_tokens`.
    - `model` é alias opaco (`llm/small` etc.).
    - Sem persistência de conversa no server; cada request é stateless além do pool do modelo.

  **US-06-3 — Rotas dos outros módulos (adaptativo)**
  - As a desenvolvedor, I want to embeddings e áudio se os PRDs 03/05 existirem so that o server cresça sem retrabalho.
  - **Acceptance Criteria**:
    - Se PRD 05 merged: `/v1/embeddings`.
    - Se PRD 03 merged: `/v1/audio/transcriptions`, `/v1/audio/speech`.
    - Visão: se o cliente mandar image_url/base64 em chat e o PRD 04 existir, o server encaminha; senão 400 claro.
    - Tools no schema OpenAI só se P1 do PRD 02 estiver feito; senão 400 “tools not available”.

  **US-06-4 — Segurança localhost**
  - As a operador, I want to o server não abrir a LAN por default so that um `serve` não exponha a GPU na rede.
  - **Acceptance Criteria**:
    - Default 127.0.0.1. CORS default só origens localhost.
    - `--cors` explícito para afrouxar.
    - Token: header `Authorization: Bearer`.

- **Non-Goals**:
  - Compat 100% com cada campo obscuro da API OpenAI (assistants, batches, files, fine-tune).
  - Auth multi-user, TLS nativo (reverse proxy é doc).
  - UI web própria.
  - App launcher (PRD 07).
  - Redistribuir o SDK como binário; o extra `[server]` é só dependência pip.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: FastAPI, uvicorn, módulos já entregues. Pool de instâncias LLM (e outros) com fila.
- **Evaluation Strategy**:
  - Teste `TestClient`/httpx: models, chat, stream SSE, 401.
  - Teste de backpressure: N requests paralelos > tamanho do pool → 429 ou espera com timeout documentado (escolher **429 após fila máxima**, valor na spec, ex. queue=8).
  - Contrato OpenAI: validar JSON schema das respostas happy-path.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/server/openai_compat.py` + entry `serve`.
  - Pool: 1 instância default do alias pedido; não thread-safe por instância (já no 02) — o server serializa ou isola.
- **Integration Points**:
  - Porta 11434 de propósito (drop-in vs Ollama). Conflito se Ollama estiver no ar → erro de bind com remediation “mude `--port` ou pare o Ollama”.
  - Extra `[server]` declarado neste PRD (não no 00).
- **Security & Privacy**:
  - Localhost + token opcional + CORS fechado.
  - Sem logar `messages` em INFO. DEBUG pode, atrás de flag.
  - Stateless: não gravar histórico em disco.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **P0**: serve + `/v1/models` + `/v1/chat/completions` (stream e não) + auth/CORS + extra `[server]` no PyPI.
  - **P1**: embeddings/audio/vision/tools conforme módulos presentes.
- **Technical Risks**:
  - Colisão com Ollama na 11434 — desejável para compat, ruim para “os dois ao mesmo tempo”. Mitigação: mensagem de bind.
  - Tool calling “OpenAI-compat” é onde os clientes quebram. Mitigação: P1 explícito; não anunciar tools no `/v1/models` até existir.

**Contestação:** não atrasar o server até voz/visão/RAG/OpenClaw. Lib + serve é o segundo demo público, não o launcher.

**Speckit:** feature `openai-server`.

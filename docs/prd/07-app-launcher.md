# PRD 07 — App launcher

| Campo | Valor |
|---|---|
| ID | `PRD-07` |
| Status | Draft |
| Slug Speckit | `app-launcher` |
| Depende de | PRD-06 |
| Desbloqueia | persona “usuário final” (UI), sem mudar o canal do SDK |
| PyPI | Minor seguinte + extra `[apps]`. O SDK continua só no pip; as apps não vão no wheel. |
| Plano de origem | Etapa 8 |

---

### 1. Executive Summary

- **Problem Statement**: End-user não `import`a o SDK. Sem um caminho “instala o chat e abre o browser”, a terceira camada do plano não existe — mas ela **não** é o que faz o PyPI ganhar do Ollama.
- **Proposed Solution**: Extra `ceia-aisdk[apps]`, catálogo de apps e CLI `ceia-aisdk app *`. P0: Open WebUI via Docker apontando ao server local. P1: OpenClaw via npm com provider `ceia`.
- **Success Criteria**:
  - `ceia-aisdk app install openwebui` + `app run openwebui` sobe o WebUI e um HTTP GET na UI (porta documentada) devolve 200 em ≤ 3 min com Docker já instalado e `serve` no ar.
  - Config gravada aponta `OPENAI_API_BASE_URL` (ou equivalente) para `http://127.0.0.1:11434/v1` sem o usuário editar arquivo.
  - `app stop` / `uninstall` encerram o container/processo e removem o estado gerenciado pelo SDK; `status` reflete running/stopped.
  - Sem Docker: `install openwebui` falha em ≤ 2 s com remediation (“instale Docker Engine”).
  - OpenClaw: critérios P1 — `install` + config `baseUrl` no `openclaw.json`; não bloqueia o merge do P0.

---

### 2. User Experience & Functionality

- **User Personas**: usuário final guiado por um README; hobbyista que quer UI; o plano cita OpenClaw como agente.

- **User Stories**:

  **US-07-1 — Listar e instalar Open WebUI (P0)**
  - As a usuário, I want to `app install openwebui` so that eu tenha chat no browser contra o SDK.
  - **Acceptance Criteria**:
    - `app list` mostra `openwebui` (P0) e `openclaw` (visível, marcado se P1 incompleto).
    - Método: Docker. Imagem pinada por digest ou tag imutável no registry YAML.
    - `run` abre/imprime URL localhost. `stop`, `status`, `uninstall` implementados.
    - Não sobe o `serve` automaticamente neste PRD? **Decisão: `app run` verifica o server; se down, tenta `serve` em background ou falha com remediation.** Preferir **falha explícita** (“rode `ceia-aisdk serve`”) no P0 para não esconder dois processos. Supervisão conjunta = P1.

  **US-07-2 — Instalar OpenClaw (P1)**
  - As a desenvolvedor, I want to `app install openclaw` so that o agente use o provider local.
  - **Acceptance Criteria**:
    - Método: npm `openclaw@` versão pinada.
    - Escreve provider `ceia` com `baseUrl http://127.0.0.1:11434/v1`, `api: openai-completions`, `apiKey` placeholder ou token do serve.
    - Sem Node/npm → erro com remediation.
    - Não reivindicamos compat com todos os canais (WhatsApp etc.) — só Control UI / chat local.

- **Non-Goals**:
  - App store genérica para qualquer OSS.
  - Empacotar Open WebUI sem Docker neste PRD (pip path do WebUI é frágil).
  - Distribuir o SDK ou as UIs como binário/instalador. O usuário instala `ceia-aisdk[apps]` no PyPI; o runner baixa a UI (Docker/npm) na máquina.
  - Continue, Aider, Open Interpreter.
  - Atualizador automático das apps.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: Docker Engine (P0), Node/npm (P1), server do PRD 06. Nenhuma inferência nova.
- **Evaluation Strategy**:
  - CI: testes do runner com Docker mock/fake (não puxar a imagem no unit).
  - Job manual/nightly: install real do WebUI (TBD runner).
  - Snapshot do JSON/env gerado (assert `11434` e `/v1`).

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/apps/{registry,runner}.py` + YAML de apps.
  - Métodos de install: `docker` | `npm` (| `pip` / `git` no schema, não obrigatórios no P0).
- **Integration Points**:
  - Extra `[apps]`.
  - Contrato com PRD 06: host/port/token.
- **Security & Privacy**:
  - Não publicar portas das apps em `0.0.0.0` sem flag explícita.
  - Não commitar tokens no YAML de exemplo.
  - OpenClaw tem histórico de superfície de rede ampla — default do nosso runner: só localhost / sem canais externos até o usuário configurar.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **P0**: Open WebUI + CLI app * + extra.
  - **P1**: OpenClaw + auto-serve.
  - **v2**: mais apps se o registry provar valor.
- **Technical Risks**:
  - Docker + npm como dependência de produto é custo de suporte maior que o SDK inteiro. Por isso P0 é só Docker/WebUI.
  - OpenClaw muda rápido (releases 2026.x). Pin rígido + `app uninstall`.
  - Este PRD **não** deve começar antes do 06 estar verde — senão o time debuga frontend alheio.

**Contestação ao plano:** launcher no “v1 obrigatório” junto com OpenClaw é vanity até o `serve` ser drop-in. Mantido na série porque o discovery não cortou; ordenado e fatiado.

**Speckit:** feature `app-launcher`. A spec deve marcar OpenClaw como P1.

# PRD 05 — RAG zero-config

| Campo | Valor |
|---|---|
| ID | `PRD-05` |
| Status | Draft |
| Slug Speckit | `rag-module` |
| Depende de | PRD-01, PRD-02 |
| Desbloqueia | cookbook “chat com documentos”; embeddings no PRD 06 |
| PyPI | Minor seguinte após o merge (pacote já público). |
| Plano de origem | Etapa 6 |

---

### 1. Executive Summary

- **Problem Statement**: O wedge contra “só um server de LLM” é perguntar sobre *meus* arquivos com três linhas. Sem RAG, o SDK é um cliente local; com RAG, vira produto para o hobbyista e para o app interno.
- **Proposed Solution**: `ceia_aisdk.rag.RAG(nome)` com LanceDB local, embeddings ONNX (`embed/default`), loaders PDF/DOCX/MD/TXT/HTML, `add` / `retrieve` / `ask` / `list` / `delete`.
- **Success Criteria**:
  - `RAG("t").add(dir)` indexa um corpus de teste de 20 arquivos / ≤ 2 MB em ≤ 60 s CPU (incluindo pull de `embed/default` só na primeira vez; medir também o recorte *já em cache*).
  - `retrieve` de uma pergunta cujo termo está em 1 arquivo devolve esse arquivo em `sources` no top_k=5 em 100% dos casos do corpus fixture (hit@5 = 1.0 no conjunto de 10 queries fixas).
  - `ask` devolve `str` + sources; cada source tem path (ou URL) e score/trecho.
  - KB persiste em `~/.ceia-aisdk/rag/<nome>`; novo `RAG("t")` no mesmo processo seguinte vê os docs sem re-`add`.
  - `retrieve` funciona **sem** instanciar LLM (não importa `ceia_aisdk.llm` no caminho de retrieve).

---

### 2. User Experience & Functionality

- **User Personas**: hobbyista com pasta `./docs` e o SDK do PyPI; serviço que indexa um help center; operador que apaga uma KB.

- **User Stories**:

  **US-05-1 — Indexar pasta e URL**
  - As a desenvolvedor, I want to `kb.add("./docs/")` e `kb.add(url)` so that eu não escolha chunker.
  - **Acceptance Criteria**:
    - Formatos: PDF, DOCX, MD, TXT, HTML. Extensão desconhecida = skip + WARNING, não falha o lote inteiro; lote só com desconhecidos → erro.
    - URL HTML: fetch com timeout 10 s; falha de rede → `DownloadError` naquela URL, outras entradas do mesmo `add` seguem se forem paths (documentar semântica all-or-nothing vs best-effort: **best-effort com relatório**).
    - Chunking recursivo com overlap; parâmetros default documentados; escape hatch kwargs (`chunk_size`, `overlap`) permitido.

  **US-05-2 — Perguntar e só buscar**
  - As a desenvolvedor, I want to `ask` e `retrieve` so that eu escolha se o LLM fala.
  - **Acceptance Criteria**:
    - `retrieve(q, top_k=5)` → lista de chunks.
    - `ask(q)` usa LLM default do PRD 02 + chunks; resposta cita sources.
    - KB vazia: `ask`/`retrieve` → erro ou lista vazia documentada (escolher **erro** `AISDKError` com remediation “kb.add(...)”).

  **US-05-3 — Gerir KBs**
  - As a desenvolvedor, I want to listar e apagar so that eu não acumule índices.
  - **Acceptance Criteria**:
    - `list` / `delete` por nome. `delete` é irreversível e remove o diretório da KB.
    - Nomes de KB sanitizados (`../` rejeitado).

- **Non-Goals**:
  - Agentes, rerankers treináveis, híbrido BM25+vector como requisito (BM25 extra é futuro).
  - Wrapper LangChain/LlamaIndex.
  - Sync com pastas (watchdog).
  - Multilingual embed além do alias `embed/multilingual` como **opcional** no catálogo; default é `embed/default`. Se `multilingual` não estiver curado a tempo, não bloqueia o PRD.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: `sentence-transformers` e/ou `onnxruntime` conforme o plan; `lancedb`; loaders (pypdf, python-docx, etc., pinned). LLM só em `ask`.
- **Evaluation Strategy**:
  - Corpus fixture + 10 queries com doc-alvo conhecido; hit@5 = 100%.
  - Teste de persistência (reabrir KB).
  - Teste de isolamento: duas KBs não compartilham vetores.
  - Não medimos factualidade do `ask` além de “sources não vazias e resposta str” no CI.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/rag/` : store LanceDB, embedder, loaders, `RAG` façade.
  - Embeddings via alias `embed/default@N` no registry.
- **Integration Points**:
  - Config: paths sob `cache_dir/rag/`.
  - PRD 06: `/v1/embeddings` reusa o embedder.
- **Security & Privacy**:
  - Fetch de URL: sem seguir redirects para IPs link-local/metadata (bloqueio SSRF básico: só http/https, deny 127.0.0.0/8, 10/8, 169.254/16, 192.168/16, ::1) — **obrigatório** porque `add(url)` é superfície de rede.
  - Dados da KB ficam locais. Sem telemetria do conteúdo.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **P0**: add path (4 formatos) + retrieve + ask + persist + delete + publish minor. Embeddings no cache, não no wheel.
  - **P1**: add URL com guarda SSRF + `embed/multilingual` + kwargs de chunk. `--essentials` passa a incluir `embed/default`.
- **Technical Risks**:
  - PDF malformado derruba o lote. Mitigação: catch por arquivo + relatório.
  - `sentence-transformers` pode puxar `torch` e destruir o “import leve”. Mitigação: preferir caminho ONNX; se torch entrar, que seja só ao importar `ceia_aisdk.rag`, nunca no top-level.

**Speckit:** feature `rag-module`.

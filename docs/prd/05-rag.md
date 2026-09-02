# PRD 05 — Zero-config RAG

| Field | Value |
|---|---|
| ID | `PRD-05` |
| Status | Draft |
| Speckit Slug | `rag-module` |
| Depends on | PRD-01, PRD-02 |
| Unlocks | “chat with documents” cookbook; embeddings in PRD 06 |
| PyPI | Next minor after merge (package already public). |
| Source Plan | Stage 6 |

---

### 1. Executive Summary

- **Problem Statement**: The key differentiator from “just an LLM server” is the ability to ask about *my* files in three lines. Without RAG, the SDK is a local client; with RAG, it becomes a product for hobbyists and internal applications.
- **Proposed Solution**: `ceia_aisdk.rag.RAG(name)` with local LanceDB, ONNX embeddings (`embed/default`), PDF/DOCX/MD/TXT/HTML loaders, and `add` / `retrieve` / `ask` / `list` / `delete`.
- **Success Criteria**:
  - `RAG("t").add(dir)` indexes a test corpus of 20 files / ≤ 2 MB in ≤ 60 s on CPU (including the `embed/default` pull only the first time; also measure the *already cached* case).
  - For a question whose term is present in 1 file, `retrieve` returns that file in `sources` with top_k=5 for 100% of the fixture corpus cases (hit@5 = 1.0 over the set of 10 fixed queries).
  - `ask` returns a `str` + sources; each source has a path (or URL) and score/snippet.
  - The KB persists in `~/.ceia-aisdk/rag/<name>`; a new `RAG("t")` in a subsequent process can access the docs without another `add`.
  - `retrieve` works **without** instantiating an LLM (it does not import `ceia_aisdk.llm` in the retrieve path).

---

### 2. User Experience & Functionality

- **User Personas**: hobbyist with a `./docs` folder and the SDK from PyPI; service indexing a help center; operator deleting a KB.

- **User Stories**:

  **US-05-1 — Index a folder and URL**
  - As a developer, I want to use `kb.add("./docs/")` and `kb.add(url)` so that I do not have to choose a chunker.
  - **Acceptance Criteria**:
    - Formats: PDF, DOCX, MD, TXT, HTML. Unknown extension = skip + WARNING, without failing the entire batch; a batch containing only unknown extensions → error.
    - HTML URL: fetch with a 10 s timeout; network failure → `DownloadError` for that URL, while other entries in the same `add` continue if they are paths (document all-or-nothing vs best-effort semantics: **best-effort with a report**).
    - Recursive chunking with overlap; documented default parameters; escape-hatch kwargs (`chunk_size`, `overlap`) are allowed.

  **US-05-2 — Ask and retrieve only**
  - As a developer, I want to use `ask` and `retrieve` so that I can choose whether the LLM generates an answer.
  - **Acceptance Criteria**:
    - `retrieve(q, top_k=5)` → list of chunks.
    - `ask(q)` uses the default LLM from PRD 02 + chunks; the answer cites sources.
    - Empty KB: `ask`/`retrieve` → documented error or empty list (choose **error** `AISDKError` with “kb.add(...)” remediation guidance).

  **US-05-3 — Manage KBs**
  - As a developer, I want to list and delete KBs so that I do not accumulate indexes.
  - **Acceptance Criteria**:
    - `list` / `delete` by name. `delete` is irreversible and removes the KB directory.
    - KB names are sanitized (`../` is rejected).

- **Non-Goals**:
  - Agents, trainable rerankers, or hybrid BM25+vector as a requirement (additional BM25 support is future work).
  - Wrapper LangChain/LlamaIndex.
  - Folder synchronization (watchdog).
  - Multilingual embeddings beyond the `embed/multilingual` alias as an **optional** catalog entry; the default is `embed/default`. If `multilingual` is not curated in time, it does not block the PRD.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: `sentence-transformers` and/or `onnxruntime` according to the plan; `lancedb`; loaders (pypdf, python-docx, etc., pinned). LLM only in `ask`.
- **Evaluation Strategy**:
  - Fixture corpus + 10 queries with a known target document; hit@5 = 100%.
  - Persistence test (reopen the KB).
  - Isolation test: two KBs do not share vectors.
  - We do not measure the factual accuracy of `ask` beyond “non-empty sources and a str response” in CI.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/rag/`: LanceDB store, embedder, loaders, `RAG` facade.
  - Embeddings via the `embed/default@N` alias in the registry.
- **Integration Points**:
  - Config: paths under `cache_dir/rag/`.
  - PRD 06: `/v1/embeddings` reuses the embedder.
- **Security & Privacy**:
  - URL fetch: do not follow redirects to link-local/metadata IPs (basic SSRF protection: only http/https, deny 127.0.0.0/8, 10/8, 169.254/16, 192.168/16, ::1) — **required** because `add(url)` is a network-facing surface.
  - KB data remains local. No content telemetry.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **P0**: add path (4 formats) + retrieve + ask + persist + delete + minor release. Embeddings in the cache, not in the wheel.
  - **P1**: add URL with SSRF protection + `embed/multilingual` + chunk kwargs. `--essentials` begins to include `embed/default`.
- **Technical Risks**:
  - A malformed PDF can bring down the batch. Mitigation: catch errors per file + report.
  - `sentence-transformers` may pull in `torch` and undermine “lightweight imports.” Mitigation: prefer the ONNX path; if torch is included, load it only when importing `ceia_aisdk.rag`, never at the top level.

**Speckit:** `rag-module` feature.

# PRD 01 — Model registry e cache

| Campo | Valor |
|---|---|
| ID | `PRD-01` |
| Status | Draft |
| Slug Speckit | `model-registry` |
| Depende de | PRD-00 |
| Desbloqueia | PRD 02–05 |
| PyPI | **Não publica.** Continua install do repo. |
| Plano de origem | Etapa 2 (MVP: sem Ed25519, sem mirrors oficiais) |

---

### 1. Executive Summary

- **Problem Statement**: Sem um catálogo versionado, download íntegro e cache determinístico, o first-chat depende de o usuário caçar GGUF na internet — o oposto de um produto PyPI que compete com Ollama.
- **Proposed Solution**: Registry opaco com aliases `domínio/tamanho@N`, catálogo bundled no wheel, downloader HTTP com resume + `sha256` obrigatório, cache em `~/.ceia-aisdk/models/`, e CLI `ceia-aisdk model *`.
- **Success Criteria**:
  - `ceia-aisdk model pull llm/small` baixa o artefato, verifica `sha256` e grava no cache em path opaco; rerun em cache quente termina em ≤ 2 s e não gera GET HTTP.
  - Download interrompido (kill -9 após ≥ 8 MB) retoma via Range e o arquivo final casa com o `sha256` do catálogo.
  - Checksum divergente descarta o arquivo e levanta `DownloadError` com `.remediation`; nada é promovido ao path final.
  - `model info` nunca imprime repo HF, nome de arquivo upstream nem URL — só o bloco `public`.
  - `CEIA_AISDK_OFFLINE=1` + cache miss falha em ≤ 100 ms com `DownloadError`, sem tentativa de socket.

---

### 2. User Experience & Functionality

- **User Personas**: hobbyista no primeiro pull (ainda via clone); script que pina `small@2`; empresa que aponta `CEIA_AISDK_CATALOG` para um YAML interno.

- **User Stories**:

  **US-01-1 — Resolver alias**
  - As a desenvolvedor, I want to pedir `llm/small` ou `small` so that eu não memorize o artefato real.
  - **Acceptance Criteria**:
    - Formas aceitas: `llm/small`, `small` (domínio implícito só quando o caller declara o domínio — a API pública do registry exige domínio ou um contexto), `llm/small@3`, `llm/small@latest`.
    - `@latest` é pinado pela versão do SDK instalada; não há refresh remoto silencioso.
    - Alias inexistente → `ModelNotFoundError` + lista dos aliases do mesmo domínio.
    - `hf://...` e path local são bypass documentados; o SDK não reescreve o nome do arquivo no cache opaco (grava como custom, metadata `source=bypass`).

  **US-01-2 — Baixar com integridade**
  - As a desenvolvedor, I want to puxar um alias com barra de progresso so that eu confie no binário.
  - **Acceptance Criteria**:
    - CLI: `pull`, `list`, `rm`, `info`, `verify`, `where`.
    - HTTP com resume, progress Rich, `sha256` obrigatório no catálogo.
    - Uma URL por artefato neste PRD (HF org `ceia-aisdk` ou URL de stub de teste). **Sem lista de mirrors e sem failover multi-host.**
    - `model verify` re-hasheia o cache vs catálogo; exit ≠ 0 se divergir.
    - `model where` imprime o path absoluto do cache.

  **US-01-3 — Ver metadata pública**
  - As a desenvolvedor comercial, I want to ver família de licença e `commercial_use` so that eu decida sozinho.
  - **Acceptance Criteria**:
    - Campos públicos: `license_family`, `commercial_use`, `context_length`, `size_gb`, `capabilities`, `quantization_class`.
    - `info` e a API `get_public_metadata(alias)` retornam só isso.
    - **Não** existe `LicenseError`. O SDK não bloqueia pull nem load com base em licença.

  **US-01-4 — Cache opaco e concorrente**
  - As a desenvolvedor, I want to dois processos não corromperem o mesmo pull so that CI e app possam competir.
  - **Acceptance Criteria**:
    - Layout `~/.ceia-aisdk/models/<domínio>/<alias-opaco>.bin` (nome sem string do repo upstream).
    - Lockfile por artefato; segundo processo espera ou reusa o resultado.
    - `rm` apaga arquivo + lock; `list` mostra aliases presentes e tamanho.

  **US-01-5 — Catálogo privado / air-gap**
  - As a operador, I want to apontar `CEIA_AISDK_CATALOG` so that o download não dependa da org pública.
  - **Acceptance Criteria**:
    - Aceita path local ou URL HTTP de um YAML no mesmo schema.
    - Sem verificação de assinatura neste PRD (assinatura é Non-Goal).
    - Schema inválido → `AISDKError`/`DownloadError` com remediation apontando o schema.

- **Non-Goals**:
  - `catalog.yaml.sig`, Ed25519, `CatalogSignatureError`, `CEIA_AISDK_ALLOW_UNSIGNED_CATALOG`.
  - Mirrors oficiais e failover entre hosts. Uma URL que falha = `DownloadError`.
  - Inferência, escolha de device por VRAM vs `size_gb` (essa regra entra no PRD 02 usando `size_gb` daqui).
  - Torrent, CDN própria, upload ao PyPI, `bundle create`, empacotamento desktop.
  - Publicação da org HF (o catálogo de dev pode apontar para fixtures HTTP locais).

  **P1 (deste PRD, não é distribuição):** `model pull --essentials` baixa os aliases essentials que o catálogo já tiver (`llm/small` no mínimo); os demais geram warning, não crash. Só esquenta `~/.ceia-aisdk/models/`.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: HTTP client com Range (httpx ou equivalente já justificado no plan Speckit). Nenhuma GPU. Fixtures: arquivo ≥ 16 MB com `sha256` conhecido no suite de integração.
- **Evaluation Strategy**:
  - Testes de resolver (`@N`, `@latest`, miss).
  - Teste de resume com servidor HTTP local que conta requests.
  - Teste de tampering: altera 1 byte no cache → `verify` falha; `pull` re-baixa ou recusa promover.
  - Teste de opacidade: snapshot de `info` e de `str(exception)` sem substrings `huggingface.co` / nomes de repo de produção.
  - Teste offline.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/registry/{catalog,downloader,cache}.py`. Sem `signing.py`.
  - Catálogo bundled: `ceia_aisdk/registry/_internal_catalog.yaml` (underscore = não é API).
  - Resolver: alias → entrada interna `{url, sha256, size, public}`.
  - Downloader: tmp + fsync + rename atômico após hash ok.
- **Integration Points**:
  - Consome `AISDKConfig.cache_dir` e `.offline`.
  - Expõe API interna estável para o PRD 02: `resolve()`, `ensure_local(alias) -> Path`, `public_info(alias)`.
  - CLI Typer subapp `model`.
- **Security & Privacy**:
  - Integridade = `sha256` do artefato. Sem autenticidade do *catálogo* remoto (risco aceito neste incremento; documentar no `model info --help` e no troubleshooting).
  - Não logar a URL interna em nível WARNING/ERROR sem flag de debug. DEBUG pode logar host, não o path completo do repo se for possível evitar — no mínimo `info` permanece opaco.
  - Path traversal: alias e destinos de cache sanitizados; `CEIA_AISDK_CATALOG` local não pode fazer o downloader escrever fora de `cache_dir` / tmp do cache.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **Este PRD**: catálogo bundled + 1 URL + sha256 + CLI + cache + bypass `hf://` e path.
  - **P1 deste PRD**: `model pull --essentials` (aliases presentes só).
  - **Publish**: ainda não. O wheel público nasce no PRD 02 e já inclui este registry.
  - **Fora desta série**: Ed25519, mirrors, [packaging desktop](08-packaging.md).
- **Technical Risks**:
  - Org HF `ceia-aisdk` pode não existir no momento da implementação. Mitigação: fixture HTTP no CI; URL real injetada quando a org estiver pronta. O PRD 02 não pode depender de um peso de produção indisponível — precisa de um artefato de teste.
  - Opacidade vs. debug: o plano assume esse trade-off; o bypass `hf://` é a válvula.
  - Catálogo remoto unsigned é vetor de MITM. Mitigação: default = bundled; docs deixam o risco explícito até existir signing.

**Contestação ao plano:** signing e mirrors no mesmo incremento do registry atrasam o first-chat e não melhoram o KPI de 15 min. Checksum + bundled é o contrato mínimo honesto.

**Speckit:** feature `model-registry`. A spec deve listar os comandos CLI e o contrato `ensure_local()`.

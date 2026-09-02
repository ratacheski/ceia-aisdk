# PRD 00 — Foundations

| Campo | Valor |
|---|---|
| ID | `PRD-00` |
| Status | Draft |
| Slug Speckit | `sdk-foundations` |
| Depende de | — |
| Desbloqueia | PRD 01+ |
| PyPI | **Não publica.** Só install do repo (`pip install -e .`). |
| Plano de origem | Etapa 1 (com cortes) |

---

### 1. Executive Summary

- **Problem Statement**: Sem um pacote instalável, configuração previsível, detecção de hardware e um comando de diagnóstico, qualquer módulo de inferência nasce sem contrato operacional — e o time não consegue abrir issue nem medir o KPI de 15 min.
- **Proposed Solution**: Entregar o esqueleto do `ceia-aisdk` no repositório: pacote Python, CLI `ceia-aisdk`, `AISDKConfig` em camadas, `hardware.py` com detecção CPU/CUDA, hierarquia de erros com `.remediation`, logging namespaced e `ceia-aisdk doctor`. Ainda **não** sobe ao PyPI.
- **Success Criteria**:
  - `pip install -e .` (ou wheel **local**) instala o pacote em ≤ 60 s numa máquina com Python 3.11+ já presente; o wheel/sdist da lib **sem** extras pesa ≤ 5 MB além das dependências declaradas da fundação. Não há `twine upload` neste PRD.
  - `import ceia_aisdk` retorna em ≤ 200 ms em SSD e **não** importa `llama_cpp`, `faster_whisper`, `piper` nem `torch`.
  - `ceia-aisdk doctor` termina em ≤ 5 s e exit 0 em Linux CPU sem GPU; com NVIDIA presente, reporta nome da GPU, VRAM total e VRAM livre com erro ≤ 256 MB vs `nvidia-smi`.
  - 100% dos testes unitários de precedência de config (kwargs > env > TOML > default) passam no CI Linux x86_64.
  - Zero chamadas de rede no import e no `doctor` (exceto leitura local de sysfs/`nvidia-smi`).

---

### 2. User Experience & Functionality

- **User Personas**:
  - Dev hobbyista que acabou de clonar o repo e quer saber se a máquina serve.
  - Dev que vai embutir o SDK num script ou serviço Python e precisa fixar `cache_dir` e `device`.
  - Maintainer que recebe issue: o `doctor` é o anexo obrigatório.

- **User Stories**:

  **US-00-1 — Instalar o SDK a partir do repo**
  - As a desenvolvedor, I want to `pip install -e .` so that o identificador do produto exista no ambiente local.
  - **Acceptance Criteria**:
    - `pyproject.toml` declara nome `ceia-aisdk`, pacote importável `ceia_aisdk`, console script `ceia-aisdk`, `requires-python = ">=3.11,<3.14"`, classifier `Operating System :: POSIX :: Linux`.
    - Extra `[cuda]` existe como stub documentado (pode estar vazio ou só com marker); extras `[server]` e `[apps]` **não** são obrigatórios neste PRD.
    - `ceia-aisdk --help` lista ao menos `doctor`.
    - Versão acessível em `ceia_aisdk.__version__` e no `doctor` (pode ser `0.0.0` / `0.1.0.dev0` até o publish do PRD 02).
    - README deixa explícito: Linux x86_64, install pelo repo até o 0.1.0.

  **US-00-2 — Configurar em camadas**
  - As a desenvolvedor, I want to sobrescrever device e cache por kwargs, env ou TOML so that o mesmo código roda em laptop e CI.
  - **Acceptance Criteria**:
    - Precedência verificada por teste: kwargs > `CEIA_AISDK_*` > `~/.ceia-aisdk/config.toml` > default.
    - Env mínimas neste PRD: `CEIA_AISDK_DEVICE`, `CEIA_AISDK_CACHE_DIR`, `CEIA_AISDK_LOG_LEVEL`, `CEIA_AISDK_OFFLINE`.
    - Default `cache_dir` = `~/.ceia-aisdk` (expandido); `device` = `auto`; `log_level` = `WARNING` no logger (arquivo TOML pode defaultar `INFO` se criado, mas o processo nasce em WARNING).
    - TOML inexistente não é erro; o SDK opera com defaults.
    - `CEIA_AISDK_OFFLINE=1` é lido e persistido em `AISDKConfig.offline`; o efeito de recusar download é do PRD 01.

  **US-00-3 — Saber o hardware**
  - As a desenvolvedor, I want to que o SDK detecte CUDA e caia para CPU so that eu não configure GPU à mão.
  - **Acceptance Criteria**:
    - `get_device()` retorna `cpu` | `cuda` | `cuda:N`.
    - Sem driver NVIDIA ou sem GPU: `cpu`, sem exception, log em DEBUG/INFO no máximo — **não** em WARNING (não é falha).
    - Com NVIDIA: identifica índice, nome, VRAM total e livre.
    - Se `device="cuda"` foi forçado e não há CUDA: `DeviceError` com `.remediation` citando `device="cpu"` ou instalar driver.
    - Fallback por VRAM insuficiente **espera o PRD 01/02** (precisa do tamanho do modelo). Neste PRD, `get_device()` não escolhe alias.

  **US-00-4 — Diagnosticar com doctor**
  - As a desenvolvedor, I want to um comando único de diagnóstico so that eu abra issue com dados reproduzíveis.
  - **Acceptance Criteria**:
    - Imprime: OS, arch, Python, versão do pacote, device escolhido, GPUs, `cache_dir`, `offline`, extras instalados, e um bloco “copy this”.
    - Exit 0 se a fundação está usável (Python suportado + pacote importável).
    - Exit ≠ 0 se Python < 3.11 ou se `device=cuda` foi forçado e falhou.
    - Não baixa modelos. Não exige internet.

  **US-00-5 — Falhar com remediação**
  - As a desenvolvedor, I want to erros com próxima ação so that eu não leia stack trace nativo primeiro.
  - **Acceptance Criteria**:
    - `AISDKError` é a raiz; neste PRD existem `DeviceError` e, se útil internamente, uma `ConfigError`.
    - Toda instância pública expõe `.remediation: str` não vazia.
    - `LicenseError` e `CatalogSignatureError` **não** entram neste PRD (ver Non-Goals).

- **Non-Goals**:
  - Download, catálogo, cache de pesos, CLI `model *`.
  - Qualquer inferência (LLM/STT/TTS/visão/RAG).
  - FastAPI, app launcher, qualquer empacotamento desktop (PyInstaller, Briefcase, binário).
  - Assinatura Ed25519, mirrors, telemetria enviada a servidor (o flag `CEIA_AISDK_TELEMETRY` pode existir como no-op documentado).
  - `set_metrics_hook` pode ficar para o PRD 02 — não é necessário para `doctor`.
  - Apple Silicon, ROCm, Vulkan.
  - **Windows** (qualquer edição): sem CI, sem paths `AppData`, sem garantia de `nvidia-smi`/console. Import pode até funcionar por acidente — não é suporte.
  - Upload ao PyPI público (e anúncio). Metadata no `pyproject.toml` sim; `twine`/`uv publish` não. TestPyPI é opcional e não conta como lançamento.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: nenhuma inferência. Ferramentas de detecção: `nvidia-smi` (subprocess, timeout 2 s), e/ou bindings CUDA se já presentes. Não adicionar `torch` como dependência da instalação base só para detectar GPU.
- **Evaluation Strategy**:
  - Testes unitários com `nvidia-smi` mockado (presente, ausente, timeout, VRAM).
  - Teste de import: AST/hook garante que `ceia_aisdk/__init__.py` não importa backends de inferência.
  - Job CI Linux x86_64: `pip install -e . && ceia-aisdk doctor`.
  - Job opcional self-hosted GPU (TBD): `doctor` reporta a GPU do runner; se não houver runner, marcar critério CUDA do *doctor* como “testado em máquina de referência” no checklist da spec — a inferência CUDA é gate do PRD 02.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - Pacote `ceia_aisdk/` com `__init__.py` (versão + `AISDKConfig` / `get_device` se quiserem atalho), `config.py`, `hardware.py`, `errors.py`, `cli.py`.
  - Nenhum submódulo `llm/`, `registry/`, `server/` é obrigatório neste incremento. Pastas vazias não devem ser importadas no `__init__`.
  - Fluxo: CLI/API → `AISDKConfig.load()` → `get_device(config)` → stdout/`doctor`.
- **Integration Points**:
  - Identificadores travados: PyPI/CLI `ceia-aisdk`, import `ceia_aisdk`, cache `~/.ceia-aisdk`, env `CEIA_AISDK_*`, log `ceia_aisdk.*`.
  - CLI: Typer + Rich (Rich só para output do doctor; não puxar stack de download).
  - Python: 3.11–3.13, Linux x86_64.
- **Security & Privacy**:
  - `doctor` não envia dados a nenhum endpoint.
  - Não logar conteúdo de arquivos do usuário.
  - Telemetria default off. Se o flag existir, permanece no-op até um PRD futuro.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **Este PRD**: pacote + config + hardware + errors + `doctor` + CI Linux. Sem índice público.
  - **Publish**: PRD 02 (`0.1.0`). Este PRD só deixa o `pyproject.toml` pronto.
  - **Fora da série**: signing, docs site completo, Windows.
- **Technical Risks**:
  - Detectar CUDA sem `torch` depende de `nvidia-smi` no PATH. Mitigação: duas sondas + timeout 2 s + teste mockado. Sem ramo Windows neste PRD.
  - Extra `[cuda]` vazio neste PRD pode frustrar quem lê o README cedo demais. Mitigação: README da fundação diz “inferência no PRD 02”.
  - Constitution Speckit ainda é template — risco de specify sem princípios. Mitigação: ratificar constitution **antes** deste specify.

**Speckit:** descrição da feature = este PRD. Critérios de aceite acima viram Scenario/AC da `spec.md`.

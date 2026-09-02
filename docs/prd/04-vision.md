# PRD 04 — Visão (describe)

| Campo | Valor |
|---|---|
| ID | `PRD-04` |
| Status | Draft |
| Slug Speckit | `vision-describe` |
| Depende de | PRD-02 |
| Desbloqueia | cookbooks de screenshot; rotas visuais futuras |
| PyPI | Minor seguinte após o merge (pacote já público). |
| Plano de origem | Etapa 5 (sem OCR/detect ONNX) |

---

### 1. Executive Summary

- **Problem Statement**: O plano promete visão, mas OCR/YOLO são outro produto (pipeline ONNX, aliases próprios, matriz de testes distinta). Empacotar isso no primeiro incremento de visão atrasa o que o usuário pede: “olha esta imagem e responde”.
- **Proposed Solution**: `ceia_aisdk.vision.Vision.describe(image, prompt)` reusando o runtime LLM multimodal (LLaVA/MiniCPM-V via GGUF já suportado pelo backend do PRD 02), alias `vision/small`.
- **Success Criteria**:
  - `Vision().describe(fixture_png, prompt="Que número aparece?")` devolve `str` contendo o dígito esperado do fixture (1 imagem sintética no repo) em ≥ 90% de 10 runs no alias curado, ou 100% num fixture trivial de alto contraste se o modelo tiny de CI for fraco — nesse caso o gate de CI é “não crash + str não vazia” e o gate de qualidade é checklist manual no alias real.
  - Tempo warm CPU `vision/small` no fixture ≤ 30 s para a resposta completa (não first-token).
  - `from ceia_aisdk.vision import Vision` não importa `ocr`/`detect` — esses nomes **não existem** neste PRD.
  - Imagem inexistente ou formato não suportado → `AISDKError`/`BackendError` com remediation (PNG/JPEG).

---

### 2. User Experience & Functionality

- **User Personas**: hobbyista analisando screenshot via lib PyPI; serviço que manda frame de webcam como arquivo.

- **User Stories**:

  **US-04-1 — Descrever imagem**
  - As a desenvolvedor, I want to `Vision().describe(path, prompt=...)` so that eu faça VQA local.
  - **Acceptance Criteria**:
    - Default alias `vision/small@latest` (catálogo, capabilities inclui `vision`).
    - `prompt` default não vazio (“Descreva a imagem de forma objetiva.”) se omitido.
    - Aceita path e bytes/IO (pelo menos path + `bytes`).
    - Reusa o stack do PRD 02 (mesmo device/config/fallback VRAM).

  **US-04-2 — Escape para o LLM cru**
  - As a desenvolvedor, I want to saber se `LLM` multimodal e `Vision` são a mesma coisa so that eu não instancie dois modelos.
  - **Acceptance Criteria**:
    - Docs: `Vision` é fachada; não carrega um segundo backend se o caller já tiver um `LLM` vision-capable injetável (`Vision(llm=...)` ou equivalente).
    - Sem injeção, `Vision()` resolve o alias de visão, não o default de texto.

- **Non-Goals**:
  - `vision.ocr()`, `vision.detect()`, aliases `vision/ocr`, `vision/detect`, ONNX Runtime para detecção.
  - Video, bounding boxes, UI grounding.
  - Fine-tune multimodal.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: mesmo `llama-cpp-python` do PRD 02 + GGUF mmproj/alias de visão no registry. Sem ONNX novo.
- **Evaluation Strategy**:
  - Fixture sintético (dígito/shape) + assert de substring no alias real.
  - CI com stub/tiny: no-crash + tipo de retorno.
  - Não usamos benchmark COCO neste PRD.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/vision/` com `Vision.describe`.
  - Sem submódulos ocr/detect. Não deixar `from ceia_aisdk.vision import ocr` funcionar por acidente.
- **Integration Points**:
  - Registry: `vision/small`.
  - Hardware/config iguais ao LLM.
- **Security & Privacy**:
  - Imagens ficam locais. Não reenviar para API cloud.
  - Limite de tamanho de arquivo (ex.: 20 MB) para evitar DoS de memória — valor concreto a cravar na spec (≥ 20 MB rejeita).

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **Este PRD**: só `describe` + publish minor. Pesos de visão continuam on-demand (registry), fora do wheel.
  - **Futuro (PRD novo, não esta série)**: OCR/detect ONNX se um cliente real pedir.
- **Technical Risks**:
  - GGUF multimodal + mmproj aumenta complexidade do catalog. Mitigação: um alias, um artefato (ou par explícito interno, nunca público).
  - Qualidade do small em VQA é fraca. Mitigação: KPI de CI honesto (no-crash) + checklist no modelo real.

**Contestação ao plano:** OCR/detect no mesmo módulo da fachada LLM mistura dois roadmaps e dois tipos de falha. Fora.

**Speckit:** feature `vision-describe`.

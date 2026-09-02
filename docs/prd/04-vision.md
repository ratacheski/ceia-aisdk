# PRD 04 — Vision (describe)

| Field | Value |
|---|---|
| ID | `PRD-04` |
| Status | Draft |
| Speckit Slug | `vision-describe` |
| Depends on | PRD-02 |
| Unlocks | screenshot cookbooks; future vision routes |
| PyPI | Next minor after merge (package already public). |
| Source Plan | Stage 5 (without OCR/detect ONNX) |

---

### 1. Executive Summary

- **Problem Statement**: The plan promises vision, but OCR/YOLO are a different product (ONNX pipeline, dedicated aliases, distinct test matrix). Bundling them into the first vision increment delays what the user is asking for: “look at this image and answer.”
- **Proposed Solution**: `ceia_aisdk.vision.Vision.describe(image, prompt)`, reusing the multimodal LLM runtime (LLaVA/MiniCPM-V via GGUF, already supported by the PRD 02 backend), with the `vision/small` alias.
- **Success Criteria**:
  - `Vision().describe(fixture_png, prompt="What number appears?")` returns a `str` containing the expected digit from the fixture (1 synthetic image in the repo) in ≥ 90% of 10 runs with the curated alias, or 100% on a trivial high-contrast fixture if the tiny CI model is weak — in that case, the CI gate is “no crash + non-empty str,” and the quality gate is a manual checklist using the real alias.
  - Warm CPU time for `vision/small` on the fixture is ≤ 30 s for the complete response (not first-token).
  - `from ceia_aisdk.vision import Vision` does not import `ocr`/`detect` — these names **do not exist** in this PRD.
  - Nonexistent image file or unsupported format → `AISDKError`/`BackendError` with remediation guidance (PNG/JPEG).

---

### 2. User Experience & Functionality

- **User Personas**: hobbyist analyzing a screenshot through the PyPI library; service sending a webcam frame as a file.

- **User Stories**:

  **US-04-1 — Describe an image**
  - As a developer, I want to use `Vision().describe(path, prompt=...)` so that I can perform VQA locally.
  - **Acceptance Criteria**:
    - Default alias `vision/small@latest` (catalog, capabilities include `vision`).
    - Non-empty default `prompt` (“Describe the image objectively.”) when omitted.
    - Accepts a path and bytes/IO (at least path + `bytes`).
    - Reuses the PRD 02 stack (same device/config/VRAM fallback).

  **US-04-2 — Escape hatch to the raw LLM**
  - As a developer, I want to know whether the multimodal `LLM` and `Vision` are the same thing so that I do not instantiate two models.
  - **Acceptance Criteria**:
    - Docs: `Vision` is a facade; it does not load a second backend if the caller already has an injectable vision-capable `LLM` (`Vision(llm=...)` or equivalent).
    - Without injection, `Vision()` resolves the vision alias, not the text default.

- **Non-Goals**:
  - `vision.ocr()`, `vision.detect()`, aliases `vision/ocr`, `vision/detect`, ONNX Runtime for detection.
  - Video, bounding boxes, UI grounding.
  - Multimodal fine-tuning.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: the same `llama-cpp-python` from PRD 02 + GGUF mmproj/vision alias in the registry. No new ONNX dependency.
- **Evaluation Strategy**:
  - Synthetic fixture (digit/shape) + substring assertion using the real alias.
  - CI with stub/tiny: no-crash + return type.
  - We do not use a COCO benchmark in this PRD.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/vision/` with `Vision.describe`.
  - No ocr/detect submodules. Do not allow `from ceia_aisdk.vision import ocr` to work accidentally.
- **Integration Points**:
  - Registry: `vision/small`.
  - Same hardware/config as the LLM.
- **Security & Privacy**:
  - Images remain local. Do not forward them to a cloud API.
  - File size limit (e.g., 20 MB) to prevent memory DoS — a concrete value must be specified in the spec (≥ 20 MB is rejected).

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **This PRD**: only `describe` + minor release. Vision weights remain on-demand (registry), outside the wheel.
  - **Future (new PRD, not this series)**: ONNX OCR/detect if requested by a real customer.
- **Technical Risks**:
  - Multimodal GGUF + mmproj increases catalog complexity. Mitigation: one alias, one artifact (or an explicit internal pair, never public).
  - Small-model VQA quality is weak. Mitigation: an honest CI KPI (no-crash) + a checklist using the real model.

**Challenge to the plan:** Putting OCR/detect in the same module as the LLM facade mixes two roadmaps and two types of failure. Out of scope.

**Speckit:** `vision-describe` feature.

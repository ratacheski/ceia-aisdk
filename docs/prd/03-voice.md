# PRD 03 — Voice (STT + TTS)

| Field | Value |
|---|---|
| ID | `PRD-03` |
| Status | Draft |
| Speckit Slug | `voice-stt-tts` |
| Depends on | PRD-00, PRD-01 |
| Unlocks | PRD 06 (`/v1/audio/*` routes) |
| PyPI | Next minor after the merge (same `ceia-aisdk` package, public since 0.1.0). |
| Source Plan | Stage 4 |

---

### 1. Executive Summary

- **Problem Statement**: Anyone comparing the SDK with a complete local runtime expects to speak and listen without assembling Whisper + Piper manually. Without voice support, the public product is just “another GGUF wrapper”.
- **Proposed Solution**: `ceia_aisdk.stt` (`faster-whisper`) and `ceia_aisdk.tts` (`piper-tts`) modules, synchronous + asynchronous, aliases `stt/fast|accurate` and `tts/pt-br|en-us`, lazily loaded through the registry.
- **Success Criteria**:
  - `STT().transcribe(wav_16khz_mono_3s)` returns a `str` with WER ≤ 20% on a 3-second PT-BR or EN fixture (fixed dataset in the test repository).
  - `timestamps=True` returns segments with monotonic `start`/`end` values in seconds, covering the audio ± 0.5 s.
  - `TTS(voice="pt-br").speak("Hello").save(path)` generates a WAV ≥ 0.3 s; `play()` does not crash the process if no audio device is available (documented skip or no-op).
  - Importing `ceia_aisdk` does not load whisper/piper; each module pulls only its own default alias on first use.
  - `stt/fast` + `tts/pt-br` total ≤ 250 MB in the cache (catalog `size_gb` assertion).

---

### 2. User Experience & Functionality

- **User Personas**: a hobbyist with the package already installed via PyPI; a script that records microphone input; a service that only needs PT-BR TTS.

- **User Stories**:

  **US-03-1 — Transcribe a file**
  - As a developer, I want to call `STT().transcribe(path)` so that I can convert audio to text without selecting a model.
  - **Acceptance Criteria**:
    - Default `stt/fast@latest`.
    - Accepts a path and, at minimum, WAV/PCM; if the backend supports other formats, document them; invalid format → `AISDKError`/`BackendError` with remediation guidance.
    - `timestamps=True` returns a documented structure (dataclass or stable dict).
    - CUDA: if the automatic device is cuda and the faster-whisper binding has GPU support, use it; otherwise, use the CPU without crashing.

  **US-03-2 — Microphone streaming**
  - As a developer, I want partial results from the microphone so that I can implement dictation.
  - **Acceptance Criteria**:
    - `stream_microphone()` iterates over strings (partial results). No device → error with remediation guidance (“no audio input”).
    - The CI test uses a mock/fake capture, not real hardware.
    - Stopping the iterator (break/close) releases the device.

  **US-03-3 — Speak PT-BR**
  - As a developer, I want to call `TTS(voice="pt-br").speak(text)` so that the product defaults to Brazilian Portuguese.
  - **Acceptance Criteria**:
    - Default voice = `pt-br` (`tts/pt-br`). `CEIA_AISDK_TTS_LOCALE=en-us` changes the default.
    - `.speak` returns an object with `.save(path)` and `.play()`.
    - `.play()` in headless CI must not fail the test (detect audio backend; skip or use a dummy).
    - Empty text → clear error, with no silent 0-byte WAV.

  **US-03-4 — Async**
  - As a developer, I want `AsyncSTT` / `AsyncTTS` so that the pattern established in PRD 02 is maintained.
  - **Acceptance Criteria**: mirrored methods; 1 asyncio test per class.

- **Non-Goals**:
  - Diarization, speaker ID, voice cloning, or low-latency TTS streaming in the style of a cloud API.
  - Training/fine-tuning.
  - First publication (already completed in PRD 02). This PRD only bumps the minor version.
  - Packaging voices in the wheel; aliases are added to the catalog and to PRD 01's `--essentials`.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: `faster-whisper` (CTranslate2), `piper-tts` (ONNX). Registry aliases listed above. Optional: sounddevice/pyaudio only if `play()` / microphone support is real—prefer an extra or optional import.
- **Evaluation Strategy**:
  - Versioned audio fixture + expected text; WER calculated in the test (20% threshold for fast).
  - TTS: duration + RMS energy > silence; no human MOS evaluation in this PRD.
  - Microphone: fake stream of PCM frames.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - Self-contained `ceia_aisdk/stt/` and `ceia_aisdk/tts/`.
  - Same device/configuration/error contract as PRDs 00–02 (`BackendError`, `DownloadError`).
- **Integration Points**:
  - Catalog: four voice aliases. No dependency on the LLM module.
  - Future PRD 06: `transcribe` → `/v1/audio/transcriptions`; `speak.save` → `/v1/audio/speech`.
- **Security & Privacy**:
  - Audio is processed locally. Do not record microphone input to disk by default.
  - No uploads.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **P0**: file transcription + PT-BR/EN TTS saving + aliases + basic async support + minor release.
  - **P1**: timestamps, microphone, `play()`, CUDA in STT.
- **Technical Risks**:
  - Native audio dependencies break headless CI. Mitigation: optional, mocked `play`/microphone support; Linux only.
  - The 20% WER threshold is intentionally lenient—do not turn this PRD into an ASR paper.

**Speckit:** feature `voice-stt-tts`. Keep STT and TTS in the same spec (a single “voice” increment); if the spec exceeds ~25 tasks, the implementer may split it into two specs, but the PRD remains a single document.

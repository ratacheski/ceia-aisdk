# PRD 03 — Voz (STT + TTS)

| Campo | Valor |
|---|---|
| ID | `PRD-03` |
| Status | Draft |
| Slug Speckit | `voice-stt-tts` |
| Depende de | PRD-00, PRD-01 |
| Desbloqueia | PRD 06 (rotas `/v1/audio/*`) |
| PyPI | Minor seguinte após o merge (mesmo pacote `ceia-aisdk`, já público desde o 0.1.0). |
| Plano de origem | Etapa 4 |

---

### 1. Executive Summary

- **Problem Statement**: Quem compara o SDK a um runtime local completo espera falar e ouvir sem montar Whisper + Piper na mão. Sem voz, o produto público fica só “mais um wrapper de GGUF”.
- **Proposed Solution**: Módulos `ceia_aisdk.stt` (`faster-whisper`) e `ceia_aisdk.tts` (`piper-tts`), sync + async, aliases `stt/fast|accurate` e `tts/pt-br|en-us`, lazy via registry.
- **Success Criteria**:
  - `STT().transcribe(wav_16khz_mono_3s)` devolve `str` com WER ≤ 20% num fixture PT-BR ou EN de 3 s (dataset fixo no repo de testes).
  - `timestamps=True` devolve segmentos com `start`/`end` em segundos, monotônicos, cobrindo o áudio ± 0.5 s.
  - `TTS(voice="pt-br").speak("Olá").save(path)` gera WAV ≥ 0.3 s; play() não quebra o processo se não houver device de áudio (skip ou no-op documentado).
  - Import `ceia_aisdk` não carrega whisper/piper; cada módulo puxa só o próprio alias default no primeiro uso.
  - `stt/fast` + `tts/pt-br` somam ≤ 250 MB no cache (assert do catálogo `size_gb`).

---

### 2. User Experience & Functionality

- **User Personas**: hobbyista com o pacote já instalado via PyPI; script que grava microfone; serviço que só precisa TTS PT-BR.

- **User Stories**:

  **US-03-1 — Transcrever arquivo**
  - As a desenvolvedor, I want to `STT().transcribe(path)` so that eu converta áudio em texto sem escolher modelo.
  - **Acceptance Criteria**:
    - Default `stt/fast@latest`.
    - Aceita path e, no mínimo, WAV/PCM; se o backend aceitar outros formatos, documentar; formato inválido → `AISDKError`/`BackendError` com remediation.
    - `timestamps=True` retorna estrutura documentada (dataclass ou dict estável).
    - CUDA: se device auto for cuda e o binding faster-whisper tiver GPU, usa; senão CPU sem crash.

  **US-03-2 — Stream de microfone**
  - As a desenvolvedor, I want to parciais do microfone so that eu faça ditado.
  - **Acceptance Criteria**:
    - `stream_microphone()` itera strings (parciais). Sem device → erro com remediation (“sem input audio”).
    - Teste de CI usa um mock/fake capture, não hardware real.
    - Parar o iterator (break/close) libera o device.

  **US-03-3 — Falar PT-BR**
  - As a desenvolvedor, I want to `TTS(voice="pt-br").speak(text)` so that o default do produto seja português.
  - **Acceptance Criteria**:
    - Default de voz = `pt-br` (`tts/pt-br`). `CEIA_AISDK_TTS_LOCALE=en-us` troca o default.
    - `.speak` retorna objeto com `.save(path)` e `.play()`.
    - `.play()` em CI headless não deve falhar o teste (detecta backend de áudio; skip ou dummy).
    - Texto vazio → erro claro, sem WAV de 0 bytes silencioso.

  **US-03-4 — Async**
  - As a desenvolvedor, I want to `AsyncSTT` / `AsyncTTS` so that o padrão do PRD 02 se mantenha.
  - **Acceptance Criteria**: métodos espelhados; 1 teste asyncio por classe.

- **Non-Goals**:
  - Diarização, speaker ID, clonagem de voz, streaming TTS de baixa latência estilo API cloud.
  - Treino/fine-tune.
  - Primeiro publish (já ocorreu no PRD 02). Este PRD só bumpa o minor.
  - Empacotar vozes no wheel; aliases entram no catálogo e no `--essentials` do PRD 01.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: `faster-whisper` (CTranslate2), `piper-tts` (ONNX). Registry aliases acima. Opcional: sounddevice/pyaudio só se `play()` / microfone forem reais — preferir extra ou import opcional.
- **Evaluation Strategy**:
  - Fixture de áudio versionado + texto esperado; WER calculado no teste (limiar 20% no fast).
  - TTS: duração + energia RMS > silêncio; não fazemos MOS humano neste PRD.
  - Microfone: fake stream de frames PCM.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/stt/`, `ceia_aisdk/tts/` autocontidos.
  - Mesmo contrato de device/config/erros dos PRDs 00–02 (`BackendError`, `DownloadError`).
- **Integration Points**:
  - Catálogo: quatro aliases de voz. Sem dependência do módulo LLM.
  - Futuro PRD 06: `transcribe` → `/v1/audio/transcriptions`; `speak.save` → `/v1/audio/speech`.
- **Security & Privacy**:
  - Áudio processado localmente. Não gravar microfone em disco por default.
  - Sem upload.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **P0**: transcribe arquivo + TTS save PT-BR/EN + aliases + async básico + publish minor.
  - **P1**: timestamps, microfone, play(), CUDA no STT.
- **Technical Risks**:
  - Dependências nativas de áudio quebram CI headless. Mitigação: `play`/mic opcionais e mockados; Linux only.
  - WER 20% é folgado de propósito — não transformar este PRD em paper de ASR.

**Speckit:** feature `voice-stt-tts`. Manter STT e TTS no mesmo spec (um incremento de “voz”); se o spec passar de ~25 tasks, o implementador pode splitar em dois specs, mas o PRD permanece único.

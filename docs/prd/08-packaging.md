# PRD 08 — Desktop Packaging (Withdrawn)

| Field | Value |
|---|---|
| ID | `PRD-08` |
| Status | **Withdrawn** |
| Reason | The series distributes the SDK only through PyPI. There is no installer, binary, or desktop template. |

---

### Decision

Distribution for this series: **PyPI only**. The first publication to the public index is defined in [PRD 02](02-llm.md) (`ceia-aisdk==0.1.0`). The `[cuda]`, `[server]`, and `[apps]` extras are included in the versions that deliver them. Models remain on-demand in the `~/.ceia-aisdk/` cache through the registry (PRD 01)—never in the wheel.

The original plan (stage 9: PyInstaller, Briefcase, `bundle create`) assumed an “end-user desktop app” persona. That is not the product we are launching. Maintaining a packaging PRD solely to generate a manifest/binary creates work that no one will use.

### What Is Not Included

- PyInstaller, Briefcase, AppImage, `.exe`, installers.
- `ceia-aisdk bundle create`.
- A “how to embed the SDK in a binary” guide.

### What Remains and Where It Lives

- **`ceia-aisdk model pull --essentials`**: offline cache shortcut (CI, demo, air-gapped environments). It is not a distribution channel. It belongs in [PRD 01](01-model-registry.md) as P1, filtering aliases that already exist.
- **App launcher (PRD 07)**: installs OSS frontends (Docker/npm) pointing to `serve`. It does not publish the SDK; the user still installs the SDK via pip.

### When to Reopen

Only through a new PRD, if an actual customer needs a Linux binary. Do not reopen this file.

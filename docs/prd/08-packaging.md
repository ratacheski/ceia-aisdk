# PRD 08 — Empacotamento desktop (retirado)

| Campo | Valor |
|---|---|
| ID | `PRD-08` |
| Status | **Retirado** |
| Motivo | A série entrega o SDK só pelo PyPI. Não há instalador, binário nem template desktop. |

---

### Decisão

Distribuição desta série: **só PyPI**. Primeiro índice público no [PRD 02](02-llm.md) (`ceia-aisdk==0.1.0`). Extras `[cuda]`, `[server]`, `[apps]` entram nas versões que os entregam. Modelos continuam on-demand no cache `~/.ceia-aisdk/`, via registry (PRD 01) — nunca no wheel.

O plano original (etapa 9: PyInstaller, Briefcase, `bundle create`) assumia a persona “app desktop end-user”. Isso não é o produto que estamos lançando. Manter um PRD de packaging só para gerar manifesto/binário cria trabalho que ninguém vai usar.

### O que não entra

- PyInstaller, Briefcase, AppImage, `.exe`, instaladores.
- `ceia-aisdk bundle create`.
- Guia de “como embutir o SDK num binário”.

### O que sobra, e onde mora

- **`ceia-aisdk model pull --essentials`**: atalho de cache offline (CI, demo, air-gap). Não é canal de distribuição. Vai para o [PRD 01](01-model-registry.md) como P1, filtrando aliases que já existirem.
- **App launcher (PRD 07)**: instala frontends OSS (Docker/npm) apontando ao `serve`. Não publica o SDK; o usuário ainda instala o SDK via pip.

### Quando reabrir

Só com um PRD novo, se um cliente real precisar de binário Linux. Não reabrir este arquivo.

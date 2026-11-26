# CCR v12-2026 — Lean Rules-Driven PDP POC

Internal POC: AI interprets and writes; **code** owns execution, validation, and release.

- **Client:** SGS Engineering only (seeded)
- **Pipeline:** scrape → research → scrape sources → facts → write → QC/repair
- **Stack:** FastAPI + SQLModel (SQLite/Neon) · React + Vite
- **Retrieval:** Firecrawl v2 · Serper → DataForSEO
- **LLMs:** OpenAI / Anthropic / Google with per-run model + cost

## Quick start

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env.local   # project-root .env.local (or backend/.env.local)
# edit ../.env.local with API keys
python -m app.seed
python -m app.run               # http://0.0.0.0:8000 — restart after editing env

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

## Offline fixture run

In the UI, check **Use offline fixtures**, or:

```bash
curl -X POST http://127.0.0.1:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.sgs-engineering.com/sgs-3-ton-low-profile-trolley-jack","use_fixtures":true}'
```

Fixture mode skips Firecrawl/search for stages 1–3 and loads a canned fact ledger for stage 4. Stages 5–6 still need LLM API keys unless you only test validators.

## Tests

```bash
cd backend && pytest -q
```

## Machine-readable rules

[`backend/app/clients/sgs/rules.json`](backend/app/clients/sgs/rules.json) — each rule has `rule_id`, `priority`, `scope`, `validation_method` (`CODE` | `LLM` | `HYBRID`), and `on_failure`.

Deterministic checks live in [`backend/app/engine/validators.py`](backend/app/engine/validators.py).

### Rule ID prefixes

| Prefix | Meaning | Covers |
|--------|---------|--------|
| **ACC** | Accuracy | Product identity, supported claims, evidence excerpts, trusted sources |
| **STY** | Style | UK spelling, banned marketing language, no links / competitor names |
| **SEO** | SEO | Title length, word count, title structure |
| **FMT** | Format | Required output structure (title, overview, features, specs) |
| **GEO** | Gap / GEO coverage | Competitive content gaps addressed |
| **CLT** | Client | Client-specific policy (e.g. allowed SGS site benefits) |

Example: `ACC-003` = accuracy rule #3. Prefixes are DynEcom conventions for the compliance report, not an industry standard.

## FAQ

**Where is the run output?**  
On the Runs list, click the run **ID** or **URL**. The detail page shows stages, compliance, draft, fact ledger, and cost.

**What do PASS / FAIL / FLAG / SKIP mean?**  
- **PASS** — rule satisfied (sometimes after auto-correct)  
- **FAIL** — mandatory (or checked) rule not met  
- **FLAG** — preferred rule not fully met; hold for review  
- **SKIP** — rule not applicable to this run  

**When is copy “released”?**  
Only when disposition is **RELEASE** (no mandatory failures). **HOLD** means preferred issues remain (e.g. GEO-001). **REJECT** means mandatory rules failed.

**Fixture vs live?**  
Fixtures skip Firecrawl/search and use canned facts/draft for offline testing. Live runs need API keys and call real scrape, search, and LLMs.

## Acceptance smoke (live)

1. Set `FIRECRAWL_API_KEY`, `SERPER_API_KEY` (or DataForSEO), and at least two LLM keys (writer ≠ QA preferred).
2. Start backend + frontend.
3. New run → SGS trolley jack URL → Start.
4. Confirm compliance report lists every mandatory `rule_id`; copy is `released` only when disposition is `RELEASE`.

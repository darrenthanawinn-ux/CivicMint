# CivicMint — AI Permit & Compliance Navigator

An AI-driven local compliance and permit navigator for small businesses.
Given a business profile, CivicMint retrieves the exact municipal code
sections that apply and returns a permit checklist where **every single
requirement carries a hard citation** back to the source chunk it came from
— cross-checked server-side, not just trusted from the LLM.

```
civicmint/
├── backend/     FastAPI + RAG (Chroma) + LLM orchestration + PDF form filling
├── frontend/    Next.js (App Router) + TypeScript + Tailwind dashboard
└── README.md    You are here
```

## Why it won't hallucinate

1. **Retrieval-gated generation.** The LLM only ever sees municipal code
   excerpts that were actually retrieved from the vector store for this
   business (`backend/app/rag/retriever.py`). It is instructed to cite the
   exact `chunk_id` of the excerpt supporting each permit.
2. **Server-side citation verification.** Before any permit reaches the
   client, `backend/app/agent/orchestrator.py::_validate_and_build_permits`
   looks up the LLM's claimed `chunk_id` against the chunks that were
   *actually retrieved*. If the model cites a chunk_id that doesn't exist in
   that set, the item is dropped and logged as a caught hallucination — the
   citation metadata sent to the client is always rebuilt from our own
   verified chunk data, never copied from the model's output.
3. **Deterministic fallback.** If the LLM is unavailable, times out, or
   returns unparseable/unverifiable output, the API falls back to a
   rule-based mode that returns the retrieved chunks directly as
   lower-confidence permit entries — still 100% citation-backed, just without
   AI summarization.

## Security & resilience features implemented

| # | Requirement | Where |
|---|---|---|
| 1 | Citation integrity / anti-hallucination | `agent/orchestrator.py` (`_validate_and_build_permits`) |
| 2 | Prompt injection defense | `security.py` (pattern stripping) + `agent/prompts.py` (system/user separation, data fencing) + `models.py` (charset/length validation) |
| 3 | PDF injection / overflow protection | `pdf/form_filler.py` (`_sanitize_value`, `_validate_coordinates`) |
| 4 | Rate limiting & cost protection | `rate_limit.py` (sliding window) + `cache.py` (TTL cache for RAG + LLM calls) |
| 5 | Error resilience / graceful degradation | `main.py` global exception handlers, `retriever.py` timeout handling, `llm_client.py` retries + `LLMUnavailableError` fallback path |

## Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional) an Anthropic or OpenAI API key. **The app runs fully without
  either** — it uses a deterministic fallback embedding model and a
  rule-based, citation-backed fallback for permit analysis so you can demo
  the entire pipeline offline / without credentials. Add a key to unlock full
  LLM reasoning and richer summaries.

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then edit .env to add an API key (optional)

# Ingest the sample municipal code corpus into the vector store (one-time)
python -m app.rag.ingest

# Run the API
uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000` (interactive docs at
`http://localhost:8000/docs`).

Run the test suite:
```bash
pytest
```

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.local.example .env.local   # optional, only needed if bypassing the proxy
npm run dev
```

Open `http://localhost:3000`. The Next.js dev server proxies `/backend-api/*`
to the FastAPI backend at `http://localhost:8000` (configured in
`next.config.js`), so no CORS setup is required for local development.

### 3. Try it

Fill in a sample business, e.g.:
- **Name:** Sunrise Coffee Co.
- **Type:** Restaurant / Cafe
- **Address:** 123 Main Street, Springfield, IL
- **Employees:** 4
- **Outdoor seating:** checked
- **Description:** "A 900 sq ft neighborhood coffee shop with a small
  kitchen and a few outdoor tables on the sidewalk."

You'll get back a permit checklist (general business license, food
establishment permit, sidewalk cafe permit, fire operational permit, etc.),
each with an expandable citation showing the exact municipal code excerpt and
a relevance score. Permits with a mapped form template also offer a
**"Pre-fill application PDF"** button that generates a downloadable,
validated PDF with your business data already filled in.

## Extending to a real jurisdiction

The sample corpus (`backend/app/data/sample_municipal_code/*.txt`) uses a
fictional "City of Springfield" code for demo purposes. To point CivicMint at
a real jurisdiction:

1. Drop `.txt` files into that directory using the same
   `[SOURCE: ... | SECTION: ...]` header format per chunk (or extend
   `rag/ingest.py` to parse real PDF/HTML ordinances).
2. Re-run `python -m app.rag.ingest`.
3. Add corresponding entries to `pdf/templates.py` for any official forms you
   want to offer as pre-fillable PDFs.

## Notes on this build

- This was generated as a hackathon MVP: the PDF form filler renders a clean
  overlay page with `reportlab` rather than writing into a real government
  AcroForm PDF (which we don't have redistribution rights to bundle) — the
  validation logic (coordinate bounds + character limits) is identical to
  what you'd run before writing into a real form field.
- The vector store falls back to a deterministic hash-based embedding when no
  OpenAI key is configured, so retrieval — and therefore the whole
  citation pipeline — works end-to-end with zero external dependencies for
  local development and grading.
- Dependency versions in `requirements.txt` / `package.json` were current as
  of this build; run `pip install`/`npm install` in an environment with
  network access to resolve them (this sandbox had network disabled while
  writing the code, so packages could not be installed here to execute a live
  smoke test — all Python files were verified with `py_compile` and all
  TypeScript/TSX files were verified for bracket/paren balance, but you
  should run `pytest` and `npm run build` once dependencies are installed).

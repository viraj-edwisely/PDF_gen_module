# Edwisely PDF Builder

A Streamlit app that turns a textbook PDF plus a topic list into branded study PDFs:

- **GATE**: one Edwisely GATE topic guide per topic (concept notes, worked examples, figures, traps, revision card, previous-year questions, practice, sample paper, answer key).
- **Non-GATE**: one learning-module PDF (topics, case study, practice, model answers, revision sheet), shaped by an optional user prompt.

Pages: **Generate** (start a run), **Runs** (progress, warnings, previews, downloads), **Library** (upload books, review units).
Plan and design decisions: `../PLAN.md`.

## One-time setup (you do these)

### 1. Supabase (database and file storage)
1. Create a free project at https://supabase.com (any region; note the database password).
2. **Connect** button (top bar) → copy the **Session pooler** connection string and put your password in it. This is `DATABASE_URL`. (Use the pooler string, not "Direct connection": Streamlit Cloud cannot reach the direct one.)
3. **Project Settings → API Keys** → copy the project URL (`SUPABASE_URL`) and the **service_role** key (`SUPABASE_KEY`).
4. Nothing else: the app creates its tables, the vector extension and the two storage buckets on first start.

### 2. AI provider keys
- `OPENAI_API_KEY` is **always required** (book search uses OpenAI embeddings).
- Add `ANTHROPIC_API_KEY` for Claude. OpenAI (same key as above) can also be a writer.
- **Gemini runs on Vertex AI with a service account, not an API key.** In Google Cloud: enable the Vertex AI API on your project, create a service account with the **Vertex AI User** role, create a JSON key for it, and paste the whole file into the secret `GOOGLE_SERVICE_ACCOUNT_JSON` (between triple quotes, see `.streamlit/secrets.toml.example`). Optionally set `GOOGLE_CLOUD_LOCATION` (default `global`).
- A writer only appears in the app when its credential is set.

### 3. Deploy on Streamlit Community Cloud
1. Put the **contents of this `app` folder at the root of a private GitHub repository** (so `streamlit_app.py`, `requirements.txt`, `packages.txt` are at the top level).
2. https://share.streamlit.io → **Create app** → pick the repo, main file `streamlit_app.py`.
3. **Advanced settings → Secrets**: paste the values, using `.streamlit/secrets.toml.example` as the template.
4. After deploying, **Settings → Sharing**: make the app **private** and add the email addresses of your team. The app records the viewer's email as "created by".

### 4. Keep the free Supabase project awake
Free projects pause after a week without use. Open the app weekly, or add a scheduled ping.

## Run it on your own computer (optional)
```
pip install -r requirements.txt
# graphviz must be installed for graph/automaton/tree figures (https://graphviz.org/download/)
# put the secrets in .streamlit/secrets.toml
streamlit run streamlit_app.py
```

## How it works (short)
- `ingest.py`: book PDF → page text, units, chunks, embeddings (Postgres + pgvector). `retrieve.py`: scope + topic → book text for the model.
- `pipeline.py`: the steps for one PDF; every finished step is saved, so Resume never pays twice. `llm.py`: Claude / OpenAI / Gemini. `pyq.py`: PYQ sources, verified against the page text.
- `jobs.py`: background workers, cancel, resume. `render/`: the PDF renderers (GATE frame, Non-GATE module), figures and the GATE checker.
- Models and prices live in `config.py` (one model per provider, one line each).

## Limits
Books up to 100 MB / 1,500 pages, 20 topics per run, $5 per run (stops cleanly), 2 runs at once, 10 PYQ links. Scanned books are not supported (digital text only). Numeric answers are not independently verified yet: every GATE PDF carries that warning in the Runs page.

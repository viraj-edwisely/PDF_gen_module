# Edwisely PDF Builder

A Streamlit app that turns a textbook PDF plus a topic list into branded study PDFs:

- **GATE**: one Edwisely GATE topic guide per topic (concept notes, worked examples, figures, traps, revision card, previous-year questions, practice, sample paper, answer key).
- **Non-GATE**: one learning-module PDF (topics, case study, practice, model answers, revision sheet), shaped by an optional user prompt.

Pages: **Generate** (start a run), **Runs** (progress, warnings, previews, downloads, the quality report of each PDF, reviewer feedback), **Library** (upload books, review units), **Illustrations** (approve or reject pictures of machines and apparatus before any PDF uses them), **Usage** (cost, PDFs and activity per person; admins see everyone, others their own), **Admin** (admins only: people, passwords, roles).
Quality plan and the reasons behind the design: `../GATE_QUALITY_PLAN.md` (evidence from SME reviews: `../SME_FEEDBACK_PLAN.md`).
Plan and design decisions: `../PLAN.md`.

## One-time setup (you do these)

### 1. Supabase (database and file storage)
1. Create a free project at https://supabase.com (any region; note the database password).
2. **Connect** button (top bar) → copy the **Session pooler** connection string and put your password in it. This is `DATABASE_URL`. (Use the pooler string, not "Direct connection": Streamlit Cloud cannot reach the direct one.)
3. **Project Settings → API Keys** → copy the project URL (`SUPABASE_URL`) and the **service_role** key (`SUPABASE_KEY`).
4. Nothing else: the app creates its tables, the vector extension and the two storage buckets on first start.

### 2. OpenAI key
- `OPENAI_API_KEY` is the only AI key: it runs the writer model (`gpt-6-luna`, set in `config.py`) and the book search (embeddings). On the Generate page each run gets a **thinking level** (low, medium, high).

### 3. Deploy on Streamlit Community Cloud
1. Put the **contents of this `app` folder at the root of a private GitHub repository** (so `streamlit_app.py`, `requirements.txt`, `packages.txt` are at the top level).
2. https://share.streamlit.io → **Create app** → pick the repo, main file `streamlit_app.py`.
3. **Advanced settings → Secrets**: paste the values, using `.streamlit/secrets.toml.example` as the template.
4. **Open the app straight after deploying and create the first admin account** (yours): with no accounts yet, the
   sign-in page offers this once.
5. On the **Admin** page, add each person: the app makes a password and shows it once, ready to copy and send to them
   (Streamlit's own invite email cannot carry it). People sign in with email and password and can change it in the
   sidebar. Admins reset passwords, make admins, and deactivate or delete accounts; they may delete anyone's runs and
   books, everyone else only their own. Passwords are stored only as salted scrypt hashes.
6. Optional extra layer: **Settings → Sharing → private** on Community Cloud, inviting the same people.

### 4. Keep the free Supabase project awake
Free projects pause after a week without use. Open the app weekly, or add a scheduled ping.

## Run it on your own computer (optional)
```
pip install -r requirements.txt
# graphviz must be installed for graph/automaton/tree figures (https://graphviz.org/download/)
# put the secrets in .streamlit/secrets.toml
streamlit run streamlit_app.py
python -m pytest tests        # offline checks: content rules, renderers, figures against textbook values, the whole GATE pipeline with a scripted model (pip install pytest)
python tests/stress_pdf.py stress.pdf    # after a renderer change: every formula style and figure kind in one PDF, to look at
```

## Measuring quality
- Every GATE PDF gets a **quality report** (Runs page): pages, subtopics covered, prose per section, worked examples with
  steps, figures (and how many are computed from physics), raw maths left on a page, mostly empty pages, notes to review.
- Reviewers add **feedback** on each PDF (kind of problem, page, comment); "All reviewer feedback" on the Runs page lists and
  exports it. Each new kind of problem becomes a test in `tests/` and, where possible, a new automatic check.
- **Golden set**: `python tools/eval.py start` makes one run per topic of `tools/eval_topics.json` (12 topics across papers),
  `python tools/eval.py score NAME` scores them (quality report, the app's checks, and a judge rubric with the SME criteria),
  `python tools/eval.py compare A B` shows what changed. A prompt change ships only if no criterion gets worse.
- Options on the Generate page: **Visual review of figures and pages** (the model looks at every drawn figure and page; wrong
  figures go back to the writer once) and **Draw new illustrations** (GPT Image, once per concept, approved on the
  Illustrations page before use; the model ID and price are in `config.py`: confirm the price before switching it on).

## How it works (short)
- `ingest.py`: book PDF → page text, units, chunks, embeddings (Postgres + pgvector). `retrieve.py`: scope + topic → book text for the model (a scope up to 16k tokens is sent whole; a larger one is searched, and each GATE notes call searches its own planned sections).
- `pipeline.py`: the steps for one PDF; every finished step is saved, so Resume never pays twice. Each model reply is tidied and checked by `content.py`; only broken items go back to the model (one repair), and what stays broken is left out with a note. GATE answer keys get arithmetic checks and a second-model check.
- `llm.py`: the OpenAI writer call (system prompt cached; thinking level per run). `pyq.py`: PYQ sources, verified against the page text.
- `jobs.py`: background workers (topics of a run in parallel, book processing), cancel, resume. `render/`: the PDF renderers (GATE frame, Non-GATE module), figures, the drawing check (`check_content.py`) and the GATE checker.
- Figures (`render/`): `figures.py` (plot with stacked panels, bars, graph, cells, gantt, circuit, and the registry of kinds), `fig_geometry.py` (drawings with true proportions), `fig_diagrams.py` (block diagrams, logic circuits, K-maps, timing diagrams, Mermaid, illustrations), `fig_physics.py` (computed from physics: beam with SFD/BMD, Mohr's circle, pressure on plates, modulation waveforms and spectra, thermodynamic cycles with CoolProp, control responses, McCabe-Thiele stage diagrams with the stage count, Txy and xy diagrams from Antoine constants; the maths is in `stages.py`, which the content checks also use), `fig_process.py` (flowsheets: equipment on a grid joined by labelled streams, routed round the equipment), `labels.py` (labels placed clear of each other and of the drawing). Each kind's spec is its docstring, given to the model as is.
- `review.py`: the visual review and the illustration library. `quality.py`: the quality report.
- Models and prices live in `config.py` (the one writer model and its price).

## Limits
Books up to 100 MB / 1,500 pages, 20 topics per run, $5 per run (stops cleanly), 4 PDFs at once (3 per run), 10 PYQ links. Scanned books are not supported (digital text only). Answer checks catch arithmetic slips and the optional second check (the same model, asked again to re-solve everything) catches many wrong keys, but review the notes on each PDF before publishing.

# Beatrove

Beatrove is a DJ-focused music library manager with an optional vinyl-ingest backend. The browser UI handles all day-to-day crate digging (filters, playlists, waveforms), while an opt-in FastAPI service lets you upload sleeve scans, run OCR, and normalize the metadata with a local LLM.

## System Architecture

- **Browser UI (`index.html`, `assets/js/`)** – Single-page app that loads tracklists, applies search/filter logic, and renders the DJ tooling. Uses `npm run serve` (Python HTTP server) so no Node backend is required.
- **FastAPI Vinyl API (`server/app.py`)** – Handles `/api/v1/records` for vinyl intake. Stores records in `server/vinyl.db` (SQLite) with inline base64 cover images.
- **OCR Pipeline (`server/ocr/`)** – `service.py` iterates provider strategies (`providers.py`). The default providers support HTTP-based OCR endpoints and local CLI commands; responses are flattened into plain text via shared utilities (`utils.py`) so downstream components receive uniform transcripts.
- **Metadata Enrichment (`server/metadata/`)** – Uses strategy objects to interpret OCR transcripts. `LLMEnrichmentStrategy` prompts your configured LLM endpoint to produce structured record data, while `HeuristicEnrichmentStrategy` extracts keys/genres/catalog codes deterministically. Additional strategies can be added by implementing `EnrichmentStrategy.apply`.
- **SQLite Storage (`server/vinyl.db`)** – Persisted records with merged manual fields, LLM-enriched metadata, cover images, and raw OCR payloads for auditing.

## Local Development

### Prerequisites
- Node.js 20+
- Python 3.11+ (with `pip`)
- Git

### Setup Steps

1. **Clone the repo**
   ```sh
   git clone https://github.com/jcrouthamel/Beatrove.git
   cd Beatrove
   ```
2. **Install front-end dependencies**
   ```sh
   npm install
   ```
3. **Create a Python virtual environment (recommended)**
   ```sh
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
4. **Install backend requirements**
   ```sh
   pip install -r server/requirements.txt
   ```
5. **Run the static UI**
   ```sh
   npm run serve
   ```
   This starts `python -m http.server 8000`. Visit `http://localhost:8000` to work with the client-only features (CSV import, filtering, playlists).
6. **Run the FastAPI service (optional vinyl intake)**
   ```sh
   uvicorn server.app:app --reload --port 9000
   ```
   The UI expects the API at `http://localhost:9000/api/v1`. Set `VITE_API_BASE` or update your local config if needed.
7. **Configure OCR/LLM (optional)**
   ```sh
   # HTTP OCR endpoint (path defaults to /v1/chat/completions if omitted)
   export VINYL_OCR_HTTP_URL="http://127.0.0.1:8089"
   export VINYL_OCR_MODEL="nanonets/Nanonets-OCR2-3B"
   # or provide a local CLI command that prints plain text to STDOUT
   # export VINYL_OCR_COMMAND="python /path/to/ocr.py --image {image}"

   export LLM_ENDPOINT="http://127.0.0.1:8088/v1/completions"
   export LLM_MODEL="gemma3"
   # optional tuning variables: LLM_TEMPERATURE, LLM_TOP_P, LLM_MAX_TOKENS, LLM_TIMEOUT_SECONDS
   ```
   Set either `VINYL_OCR_HTTP_URL` **or** `VINYL_OCR_COMMAND` (HTTP is tried first if both exist). The LLM strategy runs only when `LLM_ENDPOINT` is defined.

### Useful Commands

- `make test` – Run the Vitest suite (`npm test`)
- `make python-test` – Run Python unit tests (`python -m unittest discover`)
- `npm run test:watch` – Watch mode for the UI tests
- `uvicorn server.app:app --reload` – Start the FastAPI vinyl API

### Troubleshooting
- **OCR still returns JSON** – Ensure your OCR provider obeys the prompt or add a custom adapter in `server/ocr/providers.py`.
- **LLM not invoked** – Confirm `LLM_ENDPOINT` and `LLM_MODEL` are set. Without them, only heuristics run.
- **SQLite locked errors** – Stop other FastAPI instances or delete `server/vinyl.db` (after backing up) before restarting.

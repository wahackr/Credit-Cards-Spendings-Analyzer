# Credit Card Spending Analyzer

An automated tool that converts credit card PDF statements into structured CSV data by extracting their text and analyzing it with an OpenAI-compatible LLM. The application extracts transaction details including dates, merchant names, amounts, categories, and more from credit card statements.

## Features

- 📄 **PDF Text Extraction**: Converts statement PDFs to Markdown text with table columns rebuilt from word coordinates
- 🤖 **OpenAI-compatible LLM**: Works with any self-hosted or hosted model endpoint that speaks the OpenAI Chat Completions API
- 🚫 **Scanned-PDF Guard**: A PDF with no usable text layer is rejected before any LLM call; OCR is not supported
- 📊 **Structured Output**: Generates clean CSV files with categorized transactions
- 🏷️ **Auto-Categorization**: Automatically categorizes transactions (Dining, Shopping, Travel, etc.)
- 💼 **Account Separation**: Distinguishes between Personal and Business accounts
- 💱 **Multi-Currency Support**: Handles statements with multiple currencies, prioritizing HKD
- 🔍 **Smart Processing**: Handles multi-line transactions and DCC fees
- ⚡ **Background Jobs**: Uploads run as long-running jobs with live progress (SSE), cancellation, and CSV download; multiple statements are processed with bounded concurrency
- 🗂 **Multi-folder Uploads**: Combine PDFs from several folders (drag-drop folders, **Add Folder**, or repeated picks) into one analysis report

## Transaction Categories

The analyzer automatically categorizes transactions into:
- Cloud Services
- Dining
- Entertainment
- Fuel
- Health
- Insurance
- Shopping
- Telecom
- Travel
- Utilities
- Others

## Prerequisites

- Python >= 3.12
- An OpenAI-compatible text-model endpoint (self-hosted or hosted)
- PDF credit card statements

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Credit-Cards-Spendings-Analysiser
```

2. Install Python dependencies using `uv`:
```bash
uv sync
```

Or using pip:
```bash
pip install .
```

## LLM configuration

`openai-compatible` is the only supported provider: the Gemini provider was removed once
statements reach the model as extracted text instead of page images. Provider availability
is determined from the environment variables below.

| Variable | Required | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | No | Only `openai-compatible` is accepted, and it is used when the variable is omitted. The removed `gemini` value fails with an explicit error. |
| `OPENAI_BASE_URL` | Yes | API base URL, normally ending in `/v1`. |
| `OPENAI_API_KEY` | No | API key. Defaults to `not-required`; use a placeholder for unauthenticated local servers. |
| `OPENAI_MODEL` | Yes | Model name exposed by the server. Its presence, together with `OPENAI_BASE_URL`, enables the provider in the web app. |
| `OPENAI_THINKING` | No | Sends the nonstandard `think` option. Set to `false` for thinking-capable Qwen models on Ollama. Omit it for servers that do not support this option. |
| `OPENAI_MAX_OUTPUT_TOKENS` | No | Positive integer limiting completion length. Omit it to use the server default. |
| `LLM_DEBUG` | No | Set truthy to dump every statement's full text and the parsed LLM response to stderr. Off by default because both contain raw card data. |

### Example

```bash
export LLM_PROVIDER=openai-compatible
export OPENAI_BASE_URL=http://10.7.7.79:8080/v1
export OPENAI_API_KEY=not-required
export OPENAI_MODEL=qwen3.5:9b
export OPENAI_THINKING=false
```

`OPENAI_API_KEY` may be omitted because it defaults to `not-required`. If it is
set, it must not be empty. The selected model and server must support structured
output/tool calling through an OpenAI-compatible Chat Completions API; the analyzer
sends statement text, not page images.

For local development you can keep these variables in an untracked `.env` file at
the repository root instead of exporting them in your shell. It is loaded by both
the CLI and the web app. Variables already exported in the environment take
precedence over `.env` values. Restart the application after changing either
source. To use a `.env` value instead of a shell export, unset that variable in
your shell first (for example, `unset OPENAI_API_KEY`). Docker does not copy `.env` into the image; pass the
variables through the shell or a Compose `.env` file instead.

Ollama enables thinking by default for supported models such as Qwen. Thinking
can consume the model's entire context window before it finishes the required
JSON response. Set `OPENAI_THINKING=false` for statement extraction. This option
is Ollama-specific and is only sent when the environment variable is set.

### One provider, several servers

`LLM_PROVIDER` takes no value other than `openai-compatible`, so it can simply be omitted;
the CLI uses that provider directly. The web app lists a provider only when its required
variables are valid, so a missing `OPENAI_BASE_URL` or `OPENAI_MODEL` leaves the
configuration panel empty. To analyze a job against a different server, edit the endpoint
field in that panel for the job instead of configuring another provider.

### Text extraction

Statement PDFs are converted to Markdown with `markitdown`, which rebuilds table
columns from word coordinates, so dates and amounts reach the model as exact
characters instead of pixels. The conversion runs in memory (`io.BytesIO`), so no
intermediate image or text files are produced, and no system PDF tools are needed:
the readers (`pdfplumber`, `pdfminer-six`, `pypdfium2`) ship as wheels.

A PDF that yields fewer than 120 characters is treated as having no usable text
layer and fails before any LLM call — scanned or image-only statements need a text
PDF export, since OCR is not supported.

## Docker Deployment

### Build and Run with Docker

1. **Build the Docker image:**
```bash
docker build -f deploy/docker/analyzer.Dockerfile -t credit-card-analyzer .
```

2. **Run the container:**

`LLM_PROVIDER` may be omitted because `openai-compatible` is the default:

```bash
docker run -p 8000:8000 \
  -e OPENAI_BASE_URL="http://10.7.7.79:8080/v1" \
  -e OPENAI_API_KEY="not-required" \
  -e OPENAI_MODEL="qwen3.5:9b" \
  -e OPENAI_THINKING="false" \
  -e MAX_CONCURRENT_STATEMENTS=2 \
  credit-card-analyzer
```

The endpoint must be reachable from inside the container. An LLM server bound
only to the host's `localhost` is not reachable as `localhost` from the container;
use a reachable host address or an appropriate Docker host-network configuration.

3. **Access the app:**
Open your browser to `http://localhost:8000`

### Docker Compose (Recommended)

The repository tracks `deploy/compose.yaml`; use it instead of writing your own:

```bash
cp deploy/.env.example deploy/.env   # then put your endpoint and model in it
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d
```

Set the desired variables in that file or in your shell before starting the service.
Variables for an unused provider may remain unset. The stack publishes
`${APP_BIND_ADDRESS:-127.0.0.1}:${APP_HOST_PORT:-8010}`, so the app is reachable at
`http://localhost:8010` by default — loopback only, because the API is unauthenticated.

Continuous integration and self-hosted deployment pipelines live in `.github/workflows`:
`development` deploys to the `dev` Docker context, `master` to the `prod` context. See
[deploy/README.md](deploy/README.md) for the runner registration, the `dev`/`prod` environment
variables and secrets, and the bind-address guard.

## Local Development

Set `MAX_CONCURRENT_STATEMENTS` to a positive integer to control how many uploaded
statements are processed at once. It defaults to `2`; keep it low because PDF
rendering consumes memory and AI providers may enforce rate limits.

1. Place your PDF credit card statements in the `statements/` directory:
```
statements/
  ├── bank-name-YYYYMM/
  │   └── statement.pdf
  └── another-bank-YYYYMM/
      └── statement.pdf
```

2. Run the analyzer:
```bash
uv run python src/main.py
```

Or start the web application, then select the provider and model in the
configuration panel:

```bash
uv run uvicorn webapp.app:app --app-dir src --reload --port 8000
```

Open `http://localhost:8000`. Uploads run as background jobs: the browser follows
progress over Server-Sent Events, the server keeps processing statements even if
you close the tab, and finished jobs stay available for results and CSV download
until the server restarts.

For OpenAI-compatible providers, the configuration panel includes an editable
endpoint field prefilled from `OPENAI_BASE_URL`. Change it before starting an
analysis to use a different server for that job. This does not change the server's
environment or the endpoint used by other jobs.

Statement staging accepts several sources in one job: drop files or whole folders,
click to browse files, or use **Add Folder** to include a directory tree. Files
accumulate across selections (only an exact re-add of the same file is skipped,
up to 20 per job), so statements spread over multiple folders — including
different files that share the same name — are combined into a single report.
The relative path is kept as the statement label, and absolute or `..` paths are
rejected.

### Running the tests

The `tests/` directory holds a pytest suite (configured in `pyproject.toml`, which
puts `src` and `tests` on the import path). Run it with:

```bash
uv run pytest -q -ra
uv run flake8 src tests   # lint, matching CI
```

Web app provider behavior:

- `OPENAI_BASE_URL` and `OPENAI_MODEL` set: OpenAI-compatible is listed and preselected.
- Either one missing: the app displays the missing provider settings and blocks uploads.

### API overview

| Endpoint | Purpose |
| --- | --- |
| `GET /api/config` | Providers valid in the environment, their defaults (model, endpoint, thinking), and the worker bound. |
| `POST /api/jobs` | `multipart/form-data` upload of PDFs (`files` field, up to 20; filenames may keep relative sub-paths from folder uploads); optional `provider`/`model`/`base_url` query params. `base_url` overrides the OpenAI-compatible endpoint for this job. Returns the job. |
| `GET /api/jobs` / `GET /api/jobs/{id}` | List jobs or fetch one with per-file stages. |
| `GET /api/jobs/{id}/events` | Server-Sent Events stream of progress until the job finishes. |
| `POST /api/jobs/{id}/cancel` | Stop queued files and let running ones drain. |
| `DELETE /api/jobs/{id}` | Drop the job and its stored results. |
| `GET /api/jobs/{id}/transactions` | Transactions, per-statement summaries, and invalid-amount count. |
| `GET /api/jobs/{id}/csv` | Download the consolidated CSV. |
| `GET /healthz` | Health probe used by Docker. |

Interactive API docs are served at `/docs`.

### OpenAI-compatible troubleshooting

If the response reports that the length limit was reached, the model exhausted
its context window before completing the `Statement` JSON. For Qwen on Ollama,
disable thinking and restart the application so it reloads the environment:

```bash
export OPENAI_THINKING=false
uv run uvicorn webapp.app:app --app-dir src --port 8000
```

If a large statement still reaches the limit, increase the model context size on
the inference server. Ollama context size is configured in the model/Modelfile,
not through its OpenAI-compatible API. `OPENAI_MAX_OUTPUT_TOKENS` only caps the
completion and does not increase the available context.

3. The script will:
   - Extract Markdown text from each PDF (a scanned PDF fails with a clear message)
   - Send that text to the configured LLM
   - Extract and categorize all transactions
   - Output consolidated CSV data

## Project Structure

```
.
├── src/
│   ├── main.py                    # CLI batch entry point
│   ├── webapp/                    # FastAPI web app
│   │   ├── app.py                 # API routes and static page
│   │   ├── jobs.py                # In-memory job manager
│   │   └── static/index.html      # Single-page frontend
│   └── libs/
│       ├── llm/                   # Provider configuration and clients
│       │   └── main.py
│       ├── prompts/               # AI prompts
│       │   └── main.py
│       ├── states/                # Data models
│       │   └── statement.py
│       └── tools/                 # Utility tools
│           ├── pdf_2_text.py      # PDF to Markdown text extraction
│           ├── state_2_csv.py     # CSV generation
│           ├── statement_processor.py # Concurrent statement pipeline
│           ├── statement_reader.py # LLM call and structured output
│           ├── statement_results.py # Per-statement results and validation
│           └── retry.py           # Transient error retry
├── tests/                         # pytest suite (pdf_fixture.py builds a sample PDF)
├── deploy/                        # Docker Compose, image, and CI deploy tooling
│   ├── compose.yaml               # Compose stack (loopback bind, mem ceiling)
│   ├── docker/analyzer.Dockerfile # Runtime image
│   └── tools/                     # deploy.sh + Node scripts tested by CI
├── .github/workflows/             # test.yml, deploy-development.yml, deploy-production.yml
├── statements/                    # Input PDF statements (CLI mode)
├── pyproject.toml                 # Project dependencies
└── README.md
```

Note: the root-level `main.py` is the `uv` scaffold stub, not the analyzer — the CLI
entry point is `src/main.py`.

## Output Format

The analyzer generates CSV output with the following columns:
- `date`: Transaction date (YYYY-MM-DD)
- `transaction_name`: Merchant or transaction description
- `amount`: Transaction amount in HKD
- `category`: Auto-assigned category
- `account`: Personal or Business
- `card_name`: Credit card name

## Dependencies

- `fastapi` and `uvicorn[standard]`: web app and server
- `python-multipart`: parses the `multipart/form-data` statement uploads
- `langchain`: LLM framework
- `langchain-openai`: OpenAI-compatible integration for LangChain
- `markitdown[pdf]`: PDF to Markdown text extraction
- `pandas`: CSV assembly
- `python-dotenv`: loads the repo-root `.env` defaults for the CLI and web app

## Data Models

The application uses Pydantic models for structured data:

- **Transaction**: Individual transaction details
- **Statement**: Complete statement with transactions, totals, and metadata

## How It Works

1. **PDF Discovery**: Scans the `statements/` folder for PDF files
2. **Text Extraction**: Converts each PDF to Markdown with table columns rebuilt from word coordinates
3. **AI Analysis**: Sends the statement text to the configured LLM with structured prompts
4. **Data Extraction**: AI extracts transactions with intelligent parsing
5. **CSV Generation**: Converts structured data to CSV format
6. **Validation**: Cross-checks totals to ensure accuracy

## Advanced Features

- **Multi-line Transaction Handling**: Correctly processes transactions spanning multiple lines
- **DCC Fee Detection**: Automatically identifies and adds Dynamic Currency Conversion fees
- **Smart Categorization**: Uses merchant names to intelligently categorize spending
- **Error Handling**: Robust processing with comprehensive error handling

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- LangChain for LLM orchestration
- markitdown and pdfplumber for PDF text extraction

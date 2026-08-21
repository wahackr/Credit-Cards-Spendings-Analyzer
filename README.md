# Credit Card Spending Analyzer

An automated tool that converts credit card PDF statements into structured CSV data using Google Gemini or an OpenAI-compatible multimodal LLM. The application extracts transaction details including dates, merchant names, amounts, categories, and more from credit card statements.

## Features

- 📄 **PDF to Image Conversion**: Automatically converts PDF statements to images for processing
- 🤖 **Choice of LLM**: Uses Google Gemini or a self-hosted OpenAI-compatible multimodal model
- 📊 **Structured Output**: Generates clean CSV files with categorized transactions
- 🏷️ **Auto-Categorization**: Automatically categorizes transactions (Dining, Shopping, Travel, etc.)
- 💼 **Account Separation**: Distinguishes between Personal and Business accounts
- 💱 **Multi-Currency Support**: Handles statements with multiple currencies, prioritizing HKD
- 🔍 **Smart Processing**: Handles multi-line transactions and DCC fees
- ⚡ **Concurrent Batches**: Processes multiple uploaded statements with bounded concurrency

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
- A Google Gemini API key, or an OpenAI-compatible multimodal endpoint
- PDF credit card statements

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Credit-Cards-Spendings-Analysiser
```

2. Install system dependencies:
```bash
sudo apt-get install poppler-utils
```

3. Install Python dependencies using `uv`:
```bash
uv sync
```

Or using pip:
```bash
pip install .
```

## LLM configuration

The analyzer supports `gemini` and `openai-compatible`. Provider availability is
determined from the provider-specific environment variables below.

| Variable | Required | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | CLI: yes when using OpenAI-compatible; Streamlit: no | CLI provider selection and preferred Streamlit default. Defaults to `gemini`. |
| `GEMINI_API_KEY` | For Gemini | Google Gemini API key. Its presence enables Gemini in Streamlit. |
| `GEMINI_MODEL` | No | Gemini model name. Defaults to `gemini-3-flash-preview`. |
| `OPENAI_BASE_URL` | For OpenAI-compatible | API base URL, normally ending in `/v1`. |
| `OPENAI_API_KEY` | For OpenAI-compatible | API key. Defaults to `not-required`; use a placeholder for unauthenticated local servers. |
| `OPENAI_MODEL` | For OpenAI-compatible | Model name exposed by the server. Its presence, together with `OPENAI_BASE_URL`, enables this provider in Streamlit. |
| `OPENAI_THINKING` | No | Sends the nonstandard `think` option. Set to `false` for thinking-capable Qwen models on Ollama. Omit it for servers that do not support this option. |
| `OPENAI_MAX_OUTPUT_TOKENS` | No | Positive integer limiting completion length. Omit it to use the server default. |

### Gemini only

```bash
export LLM_PROVIDER=gemini
export GEMINI_API_KEY=your-api-key
export GEMINI_MODEL=gemini-3-flash-preview  # optional; this is the default
```

### OpenAI-compatible only

```bash
export LLM_PROVIDER=openai-compatible
export OPENAI_BASE_URL=http://10.7.7.79/v1
export OPENAI_API_KEY=not-required
export OPENAI_MODEL=qwen3.5:9b
export OPENAI_THINKING=false
```

`OPENAI_API_KEY` may be omitted because it defaults to `not-required`. If it is
set, it must not be empty. The selected model and server must support image inputs
and structured output/tool calling through an OpenAI-compatible Chat Completions
API.

Ollama enables thinking by default for supported models such as Qwen. Thinking
can consume the model's entire context window before it finishes the required
JSON response. Set `OPENAI_THINKING=false` for statement extraction. This option
is Ollama-specific and is only sent when the environment variable is set.

### Configure both providers

Set both groups of provider variables when you want to switch providers in the
Streamlit sidebar:

```bash
export GEMINI_API_KEY=your-gemini-api-key
export GEMINI_MODEL=gemini-3-flash-preview

export OPENAI_BASE_URL=http://10.7.7.79/v1
export OPENAI_API_KEY=not-required
export OPENAI_MODEL=qwen3.5:9b
export OPENAI_THINKING=false

# CLI selection and initial Streamlit selection:
export LLM_PROVIDER=openai-compatible
```

`LLM_PROVIDER` does not hide the other configured provider in Streamlit. It only
chooses the initial selection. The sidebar lists every provider whose required
configuration is valid. The CLI has no provider selector, so it uses
`LLM_PROVIDER` directly and defaults to Gemini when the variable is omitted.

### Image handling

PDF pages are rendered as lossless PNG images at 300 DPI by default. This is a
balance between making small transaction digits legible and limiting image size,
vision-token usage, and processing time.

Gemini statement pages are uploaded with the Gemini Files API to avoid the
inline-media request-size limit. OpenAI-compatible endpoints receive Base64 image
content because file-upload APIs are not part of the common Chat Completions API.

## Docker Deployment

### Build and Run with Docker

1. **Build the Docker image:**
```bash
docker build -t credit-card-analyzer .
```

2. **Run the container:**

Gemini:

```bash
docker run -p 8501:8501 \
  -e LLM_PROVIDER="gemini" \
  -e GEMINI_API_KEY="your-api-key-here" \
  -e MAX_CONCURRENT_STATEMENTS=2 \
  credit-card-analyzer
```

OpenAI-compatible:

```bash
docker run -p 8501:8501 \
  -e LLM_PROVIDER="openai-compatible" \
  -e OPENAI_BASE_URL="http://10.7.7.79/v1" \
  -e OPENAI_API_KEY="not-required" \
  -e OPENAI_MODEL="qwen3.5:9b" \
  -e OPENAI_THINKING="false" \
  credit-card-analyzer
```

The endpoint must be reachable from inside the container. An LLM server bound
only to the host's `localhost` is not reachable as `localhost` from the container;
use a reachable host address or an appropriate Docker host-network configuration.

3. **Access the app:**
Open your browser to `http://localhost:8501`

### Docker Compose (Recommended)

Create a `docker-compose.yml` file:

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8501:8501"
    environment:
      - LLM_PROVIDER=${LLM_PROVIDER:-gemini}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_MODEL=${GEMINI_MODEL:-gemini-3-flash-preview}
      - OPENAI_BASE_URL=${OPENAI_BASE_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-not-required}
      - OPENAI_MODEL=${OPENAI_MODEL}
      - OPENAI_THINKING=${OPENAI_THINKING}
      - OPENAI_MAX_OUTPUT_TOKENS=${OPENAI_MAX_OUTPUT_TOKENS}
      - MAX_CONCURRENT_STATEMENTS=${MAX_CONCURRENT_STATEMENTS:-2}
    restart: unless-stopped
```

Then run:
```bash
docker-compose up -d
```

Set the desired variables in your shell or a Compose `.env` file before starting
the service. Variables for an unused provider may remain unset.

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

Or start the Streamlit application, then select the provider and model in the sidebar:

```bash
uv run streamlit run src/app.py
```

Streamlit provider behavior:

- Only `GEMINI_API_KEY` set: only Gemini is listed.
- Only `OPENAI_BASE_URL` and `OPENAI_MODEL` set: only OpenAI-compatible is listed.
- Both configurations set: both are listed, and `LLM_PROVIDER` chooses the initial selection.
- Neither configured: the app displays the missing provider settings and stops.

### OpenAI-compatible troubleshooting

If the response reports that the length limit was reached, the model exhausted
its context window before completing the `Statement` JSON. For Qwen on Ollama,
disable thinking and restart the application so it reloads the environment:

```bash
export OPENAI_THINKING=false
uv run streamlit run src/app.py
```

If a large statement still reaches the limit, increase the model context size on
the inference server. Ollama context size is configured in the model/Modelfile,
not through its OpenAI-compatible API. `OPENAI_MAX_OUTPUT_TOKENS` only caps the
completion and does not increase the available context.

3. The script will:
   - Convert PDFs to images (saved in `statements/bank-name-YYYYMM/images/`)
   - Process images through the configured LLM
   - Extract and categorize all transactions
   - Output consolidated CSV data

## Project Structure

```
.
├── src/
│   ├── main.py                    # Main entry point
│   └── libs/
│       ├── llm/                   # Provider configuration and clients
│       │   └── main.py
│       ├── prompts/               # AI prompts
│       │   └── main.py
│       ├── states/                # Data models
│       │   └── main.py
│       └── tools/                 # Utility tools
│           ├── pdf_2_image.py     # PDF conversion
│           ├── state_2_csv.py     # CSV generation
│           └── statement_reader.py # Statement processing
├── statements/                    # Input PDF statements
├── pyproject.toml                # Project dependencies
└── README.md
```

## Output Format

The analyzer generates CSV output with the following columns:
- `date`: Transaction date (YYYY-MM-DD)
- `transaction_name`: Merchant or transaction description
- `amount`: Transaction amount in HKD
- `category`: Auto-assigned category
- `account`: Personal or Business
- `card_name`: Credit card name

## Dependencies

- `google-genai`: Google Gemini API client
- `langchain`: LLM framework
- `langchain-google-genai`: Gemini integration for LangChain
- `langchain-openai`: OpenAI-compatible integration for LangChain
- `pdf2image`: PDF to image conversion
- `pillow`: Image processing

## Data Models

The application uses Pydantic models for structured data:

- **Transaction**: Individual transaction details
- **Statement**: Complete statement with transactions, totals, and metadata

## How It Works

1. **PDF Discovery**: Scans the `statements/` folder for PDF files
2. **Image Conversion**: Converts each PDF page to PNG images
3. **AI Analysis**: Sends images to the configured LLM with structured prompts
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

- Google Gemini AI for powerful document understanding
- LangChain for LLM orchestration
- pdf2image for reliable PDF conversion

# Credit Card Spending Analyzer

An automated tool that converts credit card PDF statements into structured CSV data using Google's Gemini AI. The application extracts transaction details including dates, merchant names, amounts, categories, and more from credit card statements.

## Features

- 📄 **PDF to Image Conversion**: Automatically converts PDF statements to images for processing
- 🤖 **AI-Powered OCR**: Uses Google Gemini AI to intelligently read and extract transaction data
- 📊 **Structured Output**: Generates clean CSV files with categorized transactions
- 🏷️ **Auto-Categorization**: Automatically categorizes transactions (Dining, Shopping, Travel, etc.)
- 💼 **Account Separation**: Distinguishes between Personal and Business accounts
- 💱 **Multi-Currency Support**: Handles statements with multiple currencies, prioritizing HKD
- 🔍 **Smart Processing**: Handles multi-line transactions and DCC fees

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
- Google Gemini API Key
- PDF credit card statements
- Surfshark (or compatible) OpenVPN account and configuration files (see below)

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

3. Install Python dependencies using `uv` (recommended):
```bash
uv sync
```

Or using pip (not recommended for this project):
```bash
pip install -r pyproject.toml
```

## Docker Deployment
### VPN Configuration

1. Place your OpenVPN configuration and authentication files in the `openvpn-configs/` directory:
```
openvpn-configs/
  ├── auth.txt
  └── your-vpn-config.ovpn
```
Edit `auth.txt` with your VPN username and password (one per line).


### Build and Run with Docker

1. **Build the Docker image:**
```bash
docker build -t credit-card-analyzer .
```

2. **Run the container:**
```bash
docker run -p 8501:8501 \
  -e GEMINI_API_KEY="your-api-key-here" \
  -e OPENVPN_CONFIG="your-vpn-config.ovpn" \
  -v $(pwd)/openvpn-configs:/etc/openvpn \
  credit-card-analyzer
```

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
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    volumes:
      - ./openvpn-configs:/etc/openvpn
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - OPENVPN_CONFIG=your-vpn-config.ovpn
    restart: unless-stopped
```

Then run:
```bash
docker-compose up -d
```

The container will automatically connect to the VPN using the provided configuration before starting the app.

## Local Development

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

3. The script will:
   - Convert PDFs to images (saved in `statements/bank-name-YYYYMM/images/`)
   - Process images through Gemini AI
   - Extract and categorize all transactions
   - Output consolidated CSV data

## Project Structure

```
.
├── src/
│   ├── main.py                    # Main entry point
│   └── libs/
│       ├── gemini/                # Gemini API client
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
├── pyproject.toml                 # Project dependencies
├── entrypoint.sh                  # Entrypoint script (handles VPN and app startup)
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
- `pdf2image`: PDF to image conversion
- `pillow`: Image processing

## Data Models

The application uses Pydantic models for structured data:

- **Transaction**: Individual transaction details
- **Statement**: Complete statement with transactions, totals, and metadata

## How It Works

1. **PDF Discovery**: Scans the `statements/` folder for PDF files
2. **Image Conversion**: Converts each PDF page to PNG images
3. **AI Analysis**: Sends images to Gemini AI with structured prompts
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

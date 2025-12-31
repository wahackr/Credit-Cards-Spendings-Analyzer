FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    gnupg \
    wget \
    openvpn \
    curl \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*


# Create entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set work directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN pip install uv && uv sync --frozen --no-install-project

# Copy project files
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/healthz || exit 1

# Run entrypoint script with uv run start
ENTRYPOINT ["/entrypoint.sh", "uv", "run", "streamlit", "run", "src/app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]

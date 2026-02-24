# Stock Analysis Pipeline - Google Cloud Run
FROM python:3.11-slim

WORKDIR /app

# Install system deps for building some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements - use cloud-specific to avoid dev deps
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Copy application code
COPY config.py .
COPY api_server.py .
COPY run_pipeline.py .
COPY portfolio_compare.py .
COPY static/ ./static/
COPY stock_agent/ ./stock_agent/
COPY financial_engine/ ./financial_engine/
COPY portfolio_optimizer/ ./portfolio_optimizer/
COPY backtester/ ./backtester/
COPY report_generator/ ./report_generator/

# Create data directory for runtime
RUN mkdir -p /app/data /app/reports_archive

# Cloud Run: PORT is set by platform; use /tmp for ephemeral data
ENV PORT=8080
ENV DATA_DIR=/tmp/app_data
EXPOSE 8080

# Run the API server
CMD uvicorn api_server:app --host 0.0.0.0 --port ${PORT}

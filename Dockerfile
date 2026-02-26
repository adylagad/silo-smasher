# ── Stage 1: build the React frontend ──────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --frozen-lockfile

COPY frontend/ ./
RUN npm run build


# ── Stage 2: Python API ──────────────────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# System deps for boto3/cryptography and Neo4j driver
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer-cached separately from source).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "fastapi>=0.115.0" "uvicorn[standard]>=0.32.0"

# Install the package.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Copy the API and supporting files.
COPY api/ ./api/
COPY examples/ ./examples/

# Copy the built frontend from Stage 1.
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

# Pre-create the system-of-record directory tree so local fallbacks work.
RUN mkdir -p data/system_of_record/raw_snapshots \
               data/system_of_record/agent_context \
               data/system_of_record/receipts

EXPOSE 8000

# Render (and most container hosts) injects $PORT at runtime.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

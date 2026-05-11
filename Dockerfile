# Opțional: imagine pentru același calculator / mediu controlat de tine.
# Build from this directory:
#   docker build -t audi-vcds-master .
# Run (exemplu cu volume pentru date persistente):
#   docker run --rm -p 8088:8088 -e LLM_MODE=disabled \
#     -v "$(pwd)/data/vectorstore:/app/data/vectorstore" \
#     -v "$(pwd)/data/uploaded-logs:/app/data/uploaded-logs" \
#     audi-vcds-master

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static
COPY scripts ./scripts
COPY mcp_server ./mcp_server
COPY knowledge ./knowledge

RUN mkdir -p data/vectorstore data/uploaded-logs data/manuals data/ingested-uploads \
    && useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

USER app

ENV PYTHONUNBUFFERED=1
EXPOSE 8088

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]

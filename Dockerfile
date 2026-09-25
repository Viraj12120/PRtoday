FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install poetry poetry-plugin-export
COPY pyproject.toml poetry.lock* ./
RUN poetry lock && poetry export --without-hashes -f requirements.txt > req.txt

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="/app"
LABEL org.opencontainers.image.source="https://github.com/Viraj12120/PRtoday"

RUN apt-get update && apt-get install -y --no-install-recommends curl git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/req.txt .
RUN pip install --no-cache-dir -r req.txt

COPY alembic.ini ./
COPY pr_today/ ./pr_today/

RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "pr_today.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

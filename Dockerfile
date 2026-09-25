FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY switchboard ./switchboard

RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 appuser

USER appuser

EXPOSE 8000

CMD ["uvicorn", "switchboard.main:app", "--host", "0.0.0.0", "--port", "8000"]

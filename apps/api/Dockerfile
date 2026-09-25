FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY packages/schemas /opt/packages/schemas
COPY packages/telephony /opt/packages/telephony
COPY packages/observability /opt/packages/observability
COPY apps/api /srv

RUN pip install --no-cache-dir \
    /opt/packages/schemas \
    /opt/packages/telephony \
    /opt/packages/observability \
    /srv

EXPOSE 8000
CMD ["uvicorn", "switchboard_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

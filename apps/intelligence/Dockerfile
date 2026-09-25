FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY packages/schemas /opt/packages/schemas
COPY packages/classification /opt/packages/classification
COPY packages/observability /opt/packages/observability
COPY packages/events /opt/packages/events
COPY packages/repositories /opt/packages/repositories
COPY apps/intelligence /srv

RUN pip install --no-cache-dir \
    /opt/packages/schemas \
    /opt/packages/classification \
    /opt/packages/observability \
    /opt/packages/events \
    /opt/packages/repositories \
    /srv

EXPOSE 8002
CMD ["uvicorn", "switchboard_intelligence.main:app", "--host", "0.0.0.0", "--port", "8002"]

FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY packages/schemas /opt/packages/schemas
COPY packages/conversation /opt/packages/conversation
COPY packages/observability /opt/packages/observability
COPY packages/events /opt/packages/events
COPY apps/media_gateway /srv

RUN pip install --no-cache-dir \
    /opt/packages/schemas \
    /opt/packages/conversation \
    /opt/packages/observability \
    /opt/packages/events \
    /srv

EXPOSE 8001
CMD ["uvicorn", "switchboard_media.main:app", "--host", "0.0.0.0", "--port", "8001"]

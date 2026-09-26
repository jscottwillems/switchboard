PYTHON ?= python3
PYTHONPATH := .:packages/schemas:packages/telephony:packages/conversation:packages/classification:packages/observability:packages/events:packages/repositories:apps/api:apps/media_gateway:apps/intelligence
export PYTHONPATH

.PHONY: test install-dev test-mvp-smoke

install-dev:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e packages/schemas -e packages/telephony -e packages/conversation -e packages/classification -e packages/observability -e packages/events -e packages/repositories
	$(PYTHON) -m pip install -e apps/api -e apps/media_gateway -e apps/intelligence
	$(PYTHON) -m pip install pytest httpx

# Requires Postgres at DATABASE_URL and Redis at REDIS_URL. The suite applies apps/api/migrations.
test:
	$(PYTHON) -m pytest -q

# One mock vertical slice: webhook, fixture STT, speak-back, finding, call reads.
test-mvp-smoke:
	$(PYTHON) -m pytest -q -m mvp_smoke

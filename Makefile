PYTHON ?= python3
PYTHONPATH := packages/schemas:packages/telephony:packages/conversation:packages/classification:packages/observability:apps/api:apps/media_gateway:apps/intelligence
export PYTHONPATH

.PHONY: test install-dev

install-dev:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e packages/schemas -e packages/telephony -e packages/conversation -e packages/classification -e packages/observability
	$(PYTHON) -m pip install -e apps/api -e apps/media_gateway -e apps/intelligence
	$(PYTHON) -m pip install pytest httpx

test:
	$(PYTHON) -m pytest -q

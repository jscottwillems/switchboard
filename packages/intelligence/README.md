# Sherlock (`packages/intelligence`)

Intelligence slice for Project Switchboard. Pydantic models are the canonical schema. TypeScript in `typescript/intelligence.ts` is generated from them.

The repository was empty aside from a README, so this package introduces the layout: Python under `src/switchboard_intelligence`, fixtures and the TypeScript mirror beside it, narrative docs in `/docs`.

## Run tests

```bash
pip install -e ".[dev]"
pytest
```

Run those commands from this directory.

## Regenerate mirrors

```bash
python -m switchboard_intelligence.codegen.typescript
python scripts/build_fixtures.py
```

## Extract

```bash
uvicorn switchboard_intelligence.api:app
```

`POST /v1/intelligence/extract` takes the local transcript adapter. Model extraction is not called. Attributions are empty until an attributor with a campaign corpus is passed to `extract_intelligence`.

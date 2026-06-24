# Pulse — Planned

Pulse generates marketing and business content across 50+ languages — localized, not merely translated. It adapts tone, idiom, and cultural context for each market rather than producing literal translations.

## Differentiator

Draws on Vault so content is grounded in the business's own knowledge, products, and voice. Model-agnostic and deployable on your own infrastructure.

## Target

Businesses expanding across markets that need consistent, on-brand, multi-language content without a large localization team.

## Quick Start

```bash
# Start all services with Docker Compose
make dev

# Or run services individually
cd pulse-api && uvicorn pulse.main:app --reload --port 8000
cd pulse-ui && npm run dev
```

## Project Structure

- `pulse-api/` — FastAPI backend (auth, content, generation, experiments, integrations)
- `pulse-worker/` — Async worker for bulk generation jobs
- `pulse-scheduler/` — Scheduled task runner
- `pulse-ui/` — React + TypeScript + Vite SPA
- `k8s/` — Kubernetes manifests for self-hosted deployment
- `prd.md`, `tsd.md`, `sad.md`, `tbk.md` — Product/technical/architecture docs

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for the current implementation status and checkpoint plan.

## Honest Note

Content generation is increasingly a thin wrapper over frontier models, so Pulse should not be a lead product — defensibility comes from genuine localization quality plus suite integration rather than from raw generation, which is commoditized.

## Positioning

Value-adding module of the suite, not a lead product.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

This is a **documentation-only repository** containing planning artifacts for Pulse, a planned multilingual content generation module within the ODW.ai suite. No implementation has started yet.

## Document Structure

- **prd.md** — Product Requirements Document: user problems, target market, competitive positioning, success metrics
- **tsd.md** — Technical Specification Document: service breakdown, API contracts, data models, deployment architecture
- **sad.md** — System Architecture Document: architectural decisions, component interactions, trade-offs, deployment topology
- **tbk.md** — Task Breakdown Knowledge: implementation phases, sequential vs parallel workstreams, critical path, estimated effort (34 working days)
- **research.md** — Competitive landscape analysis (2025-2026), market gaps, sovereign AI positioning

## Planned Tech Stack

Based on TSD/TBK documents:
- **Backend:** Django/FastAPI monolith (modular monolith pattern)
- **Database:** PostgreSQL with pgvector extension, Redis for caching and job queue (Redis Streams)
- **Frontend:** React SPA
- **LLM Integration:** Model-agnostic adapters (OpenAI, Anthropic, Mistral, Ollama, vLLM, Azure OpenAI, AWS Bedrock)
- **Deployment:** Docker Compose / Kubernetes, supports self-hosted and air-gapped environments
- **Storage:** S3/MinIO for object storage

## Architecture Summary

Pulse uses a **modular monolith with async job processing**:
- Synchronous path: REST API → service modules → response (single content generation, UI interactions)
- Async path: API → Redis Streams job queue → worker pool → results (bulk generation)
- Event-driven: webhooks, audit logging, analytics

Key modules: Generation Orchestrator, Cultural Adaptation Engine, Quality Scoring Engine, LLM Abstraction Layer, Vault Connector, Bulk Job Manager, Tenant Isolation (PostgreSQL RLS).

## Product Context

Pulse generates culturally-adapted marketing content across 50+ languages. Differentiators:
1. Cultural adaptation (not literal translation) — adjusts tone, idiom, formality per market
2. Vault integration — content grounded in business's own knowledge and brand voice
3. Infrastructure sovereignty — self-hosted, model-agnostic, no data leaves customer deployment

Positioned as a **value-adding suite module**, not a standalone lead product.

## When Implementation Begins

Refer to tbk.md for the phased implementation strategy. Critical path components:
1. LLM Abstraction Layer (all generation depends on this)
2. Cultural Adaptation Engine (core IP differentiator)
3. Database schema → ORM → Auth → API endpoints (sequential dependency chain)

Parallelizable work: LLM adapters are independent of each other, frontend can proceed after API contracts are defined, unit tests alongside module implementation.

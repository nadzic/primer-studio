# Primer Studio

[![CI](https://github.com/nadzic/primer-studio/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nadzic/primer-studio/actions/workflows/ci.yml)
[![Live App](https://img.shields.io/badge/Live%20App-veritake.ai-2563EB?logo=googlechrome&logoColor=white)](https://veritake.ai)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Next.js 16](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-agent%20orchestration-1C3C3C?logo=langchain&logoColor=white)

An AI-native, multi-agent equity research assistant.

Hosted app: [https://veritake.ai](https://veritake.ai)

The project turns one user prompt into a structured research brief by combining:
- company + search planning nodes,
- public-source retrieval and ranking,
- evidence extraction/classification/selection,
- and a production-style API + frontend chat UI.

## Portfolio Overview

### Problem

Retail-style stock analysis is often fragmented: one tool for charts, another for news, another for valuation, and no consistent risk layer.

### Solution

This project provides a single pipeline that:
1. resolves the target company/symbol from natural language,
2. gathers and ranks public reporting sources,
3. extracts and classifies structured evidence,
4. selects the highest-utility evidence for a retail brief,
5. synthesizes a final response in a consistent output format.

### Why it is interesting

- Multi-agent orchestration with clear node boundaries (`LangGraph`).
- Retrieval + evidence modeling + synthesis in one flow.
- End-to-end system design (backend, frontend, voice input, CI).
- Practical API contract and reproducible local environment.

## What I Built

### Backend research pipeline

- `company_resolver` normalizes company/ticker intent from user input.
- `search_planner` builds purpose-driven search queries.
- `public_source_searcher` retrieves public sources and applies policy filters.
- `source_ranker` scores and ranks sources by reliability/relevance/recency.
- `evidence_extractor` converts source text into atomic evidence items.
- `evidence_classifier` tags evidence strength + fact/interpretation + confidence.
- `evidence_selector` keeps only useful evidence for the final brief.
- `research_synthesizer` generates final brief sections and citations.

### Product-facing features

- FastAPI endpoints for research and service health/metadata.
- Metadata endpoint `GET /api/v1/meta/model` for runtime model transparency.
- Next.js chat-style frontend for research workflow.
- Voice dictation + transcription via `POST /api/transcribe` (ElevenLabs proxy route).

## System Flow

`request -> company_resolver -> search_planner -> public_source_searcher -> source_ranker -> evidence_extractor -> evidence_classifier -> evidence_selector -> research_synthesizer -> response`

```mermaid
flowchart TD
    A([Start]) --> B[Resolve Company]
    B --> C[Plan Search]
    C --> D[Search Public Sources]
    D --> E[Rank Sources]
    E --> F[Extract Evidence]
    F --> G[Classify Evidence]
    G --> H[Select Evidence]
    H --> I[Synthesize Research Brief]
    I --> J([Response])
```

## Technical task write-up (Primer take-home)

### Workflow

The workflow is intentionally multi-step (agentic), not a one-shot prompt:
- **Resolve company**: normalize user intent to a specific company/ticker.
- **Plan search**: generate purpose-driven queries for “latest reporting”.
- **Search public sources**: retrieve public URLs/snippets with policy filters.
- **Rank sources**: score reliability/relevance/recency and dedupe before downstream use.
- **Extract evidence**: convert source text into atomic evidence items with URLs.
- **Classify evidence**: label strength (strong/medium/weak) and fact vs interpretation.
- **Select evidence**: keep only high-utility, grounded items for the retail brief.
- **Synthesize brief**: produce a concise structured output with citations (no stock calls).

### How sources are prioritised

Sources are ranked by a combined score with explicit heuristics + model judgment:
- **Reliability**: SEC filings and company IR materials are prioritised over commentary.
- **Relevance**: preference for content tied to the latest reporting period and KPIs.
- **Recency**: preference for the latest quarter/earnings cycle vs stale coverage.
- **Dedupe + adjustments**: repeated newswire/duplicates are downweighted.

This is designed to prevent “more text” from winning over “better evidence”.

### Weak vs strong evidence handling

The system separates **facts** from **interpretation** in the output and treats evidence as:
- **Strong**: primary sources (SEC/IR) and high-confidence factual claims with clear grounding.
- **Medium**: reputable secondary sources or weaker grounding (still useful context).
- **Weak**: speculative commentary/sentiment; included only when clearly labeled and relevant to the debate.

Only selected evidence is allowed to drive the final brief, and each bullet is mapped back to a source URL when available.

### What I would improve with more time

- **Deeper primary-source fetching**: ingest full 10-Q/8-K/earnings transcript text for better grounding.
- **Streaming + trace UI**: stream per-node progress/events to the frontend instead of time-based progress.
- **Evals**: expand evals to include ranking/selection metrics (e.g. “top sources contain SEC/IR/transcript”).
- **Caching**: cache source discovery + fetch results to reduce latency and token spend.
- **More robust extraction**: stronger HTML→text extraction and citation spans (paragraph-level citations).

## API Surface

- `GET /api/v1/health`
- `GET /api/v1/meta/model`
- `POST /api/v1/research`

Example research request:

```json
{
  "query": "Please research NVDA"
}
```

Example research response shape:

```json
{
  "company": "NVIDIA Corporation",
  "ticker": "NVDA",
  "brief": {
    "executive_summary": "...",
    "what_changed": [
      {
        "text": "...",
        "type": "fact",
        "evidence_strength": "strong",
        "source_url": "https://..."
      }
    ],
    "what_matters_most_now": [],
    "bull_points": [],
    "bear_points": [],
    "what_to_watch_next": []
  },
  "evidence_quality_summary": {
    "strong": 4,
    "medium": 3,
    "weak": 1
  },
  "sources": [],
  "selected_evidence": [],
  "discarded_evidence_count": 8,
  "disclaimer": "This is not investment advice.",
  "warning": null,
  "error": null
}
```

Example frontend-style plain-text output:

```text
NVIDIA Corporation (NVDA)
Latest reporting research brief
----------------------------------------

Executive summary
...

What changed
- Revenue grew ...

What matters most now
- ...

Bull points
- ...

Bear points
- ...

What to watch next
- ...

Evidence quality
Strong: 4 | Medium: 3 | Weak: 1

Sources used
1. ...
2. ...
3. ...

Disclaimer
This is not investment advice.
```

## Tech Stack

### Backend

- Python 3.11
- FastAPI + Uvicorn
- LangGraph / LangChain
- Tavily web search (via backend service integration)

### Frontend

- Next.js 16
- React 19
- TypeScript
- Typed API client for backend workflow integration

### Tooling

- `uv` for Python dependency management
- Docker + Docker Compose
- Ruff + BasedPyright + Pytest
- GitHub Actions CI

## Run Locally

### 1) Backend

```bash
uv sync
uv run uvicorn app.main:app --reload --app-dir .
```

Create `.env` (copy `.env.example` or `sample.env`) and configure at least:
- `OPENAI_API_KEY` (or another configured provider key),
- `LLM_PROVIDER`,
- `LLM_MODEL_NAME`,
- `ALLOWED_ORIGINS`.

Optional:
- `ANTHROPIC_API_KEY`
- `FINNHUB_API_KEY`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `TAVILY_API_KEY` (for public web search)
- `RATE_LIMIT_ANON_DAILY` (default `2`, transcription route)
- `RATE_LIMIT_COOKIE_SECRET` (for signed anonymous guest cookie)

### 2) Frontend

```bash
cd app/frontend
npm install
npm run dev
```

Set `app/frontend/.env.local`:
- `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api/v1`)
- `ELEVENLABS_API_KEY` (optional, only if using voice transcription)

### 3) Full stack with Docker

```bash
docker compose up --build
```

Useful URLs:
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/api/v1/health`
- Frontend: `http://localhost:3000`

## Project Structure

```text
app/
  agents/
    graph/
      nodes/
    services/
      fundamentals/
      technicals/
      valuation/
      sentiment/
      insider/
  api/
    routes/
    schemas/
  frontend/
    src/
      app/
      components/
      lib/
```

## Quality

CI checks on push to `main`:
- Ruff lint
- BasedPyright type checks
- Pytest (when tests exist)
- Python compile smoke checks
- Docker build

## TODOs

- Implement jobs, workers, and queues for data ingestion and indexing
- Add fallback models
- Experiment with using smaller models for classification and routing, and reserve larger models for final generation
- Provide a default safe response when API calls fail
- Improve LLM provider orchestration to easily swap models

## Disclaimer

Educational/research project. Not financial advice.

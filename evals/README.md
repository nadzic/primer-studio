# Evals For Primer Technical Task

This folder is aligned with the "Primer Technical Task" brief (agentic equity research, not stock picking).

## Dataset

- `datasets/signals_analyze_golden_v1.json`
  - Contains research-style evaluation prompts, including:
    - normal "latest reporting" cases
    - edge cases (ambiguity, weak coverage, out-of-scope requests)
    - adversarial cases (prompt injection, non-public data requests, recommendation pressure)

## Expected Output Contract

Each case expects a structured research brief with these sections:

- `what_changed`
- `what_matters_most_now`
- `bull_points`
- `bear_points`
- `what_to_watch_next`

And these behavioral requirements:

- explicit separation of facts vs interpretation
- public sources only
- no direct buy/sell recommendation output

## Why This Differs From Signal Evals

The technical task explicitly asks for a research workflow that helps users think better after reporting updates. It does **not** ask for a stock-picker or buy/sell engine.

## Run Evaluator

1. Start the API locally (for example with uvicorn on port 8000).
2. Run:

```bash
python evals/agents/run_research_eval.py --base-url http://localhost:8000
```

Optional report output:

```bash
python evals/agents/run_research_eval.py --base-url http://localhost:8000 --out evals/reports/research_eval_report.json
```

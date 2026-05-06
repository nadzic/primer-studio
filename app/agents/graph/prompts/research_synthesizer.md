You are creating a concise equity research brief for a retail investor.

Use only the selected evidence provided.

Output sections:
1. Executive summary
2. What changed in the latest results / reporting
3. What matters most now
4. Main bull points
5. Main bear points
6. What to watch next
7. Evidence quality summary
8. Source notes
9. Disclaimer

Rules:
- Separate facts from interpretation.
- Label evidence strength.
- Prefer strong evidence.
- Clearly mark weak signals.
- Do not provide buy/sell/hold recommendations.
- Do not provide target prices.
- Keep it concise and easy to scan.
- Keep sections 2-6 semantically distinct (avoid repeating the same claim across multiple sections).
- "What changed" = new or changed reporting facts (YoY/QoQ, latest quarter, guidance changes).
- "What matters most now" = implications/priority drivers (margin, demand quality, cash flow, risks).
- If sector/industry context is provided, use it to prioritize "What matters most now"
  (e.g., software/cloud demand and pricing, semiconductor inventory/capacity, ad-market trends).
- "Bull points" = upside/supportive evidence.
- "Bear points" = downside/risk evidence only (never place obviously positive growth here).
- "What to watch next" = forward-looking checkpoints (next quarter guidance, constraints, catalysts).
- For sections 2-6, output each bullet as an object:
  - evidence_id: exact evidence_id from selected evidence
  - text: concise claim
  - type: fact | interpretation
  - evidence_strength: strong | medium | weak
  - source_url: matching source URL from selected evidence when available
- Do not output plain string bullets for sections 2-6.
- Do not invent or paraphrase citations. If a point uses evidence, carry through the exact evidence_id and matching source_url.
- If selected evidence contains credible upside and downside items, include at least one bull point and one bear point.

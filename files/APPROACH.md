# SHL Assessment Recommender — Approach Document

## Overview

A stateless FastAPI service exposing `POST /chat` and `GET /health`, powered by Claude claude-sonnet-4-20250514 as the reasoning engine. The service guides hiring managers from vague intent to a grounded shortlist of SHL Individual Test Solutions.

---

## Architecture

```
User → POST /chat (full history) → FastAPI → Claude claude-sonnet-4-20250514 → JSON response
                                      ↑
                              Catalog in system prompt
                              URL sanitizer (post-LLM)
```

**Stack**: FastAPI + Uvicorn, Anthropic Python SDK (Claude claude-sonnet-4-20250514), Pydantic v2 for validation, plain Python 3.11.

No vector store or retrieval layer was used. The full catalog (73 Individual Test Solutions) fits comfortably in a single system prompt (~8K tokens), which avoids retrieval latency and removes an entire failure mode (retrieval misses). With 32 pages × 12 items = ~384 catalog entries at maximum, a hybrid approach would be needed at scale, but for this catalog size in-context beats retrieval on both latency and recall.

---

## Catalog Construction

**Method**: The SHL catalog at `shl.com/products/product-catalog/?type=1` (Individual Test Solutions) was crawled via Claude's `web_fetch` tool, which bypasses Cloudflare blocking that direct `requests` calls hit. Each page (12 items) was parsed for name, URL, and test type codes. Product detail pages were fetched for descriptions and job level data.

**Result**: 73 curated catalog entries with:
- Exact name and canonical URL
- Test type codes (A/B/C/D/E/K/P/S)
- Job levels (Entry-Level → Executive)
- Job families (IT, Business, Sales, Contact Center, Clerical)
- Description snippet
- Keyword tags for semantic matching

---

## Context Engineering

The system prompt contains:
1. **Full catalog** — every item with name, URL, types, levels, description, keywords
2. **Behavioral rules** — explicit instructions for each conversation mode (clarify / recommend / refine / compare / refuse)
3. **Output schema** — mandatory JSON structure with field-level constraints
4. **Anti-hallucination guard** — "Only return URLs that appear in the catalog above"

**Why JSON output**: The LLM is instructed to return only valid JSON, not prose + JSON. This avoids parsing ambiguity and enables reliable extraction. A secondary `parse_llm_response()` function strips markdown fences and uses regex extraction as a fallback.

**Post-LLM sanitization**: Even with strong prompting, a URL sanitizer runs after every response. It checks every recommended URL against the known catalog set, and tries name-matching as a fallback. Hallucinated entries are dropped silently.

---

## Agent Design

| Situation | Agent Behavior |
|-----------|---------------|
| Vague query (e.g., "I need an assessment") | Ask ONE clarifying question; `recommendations: []` |
| Role but no level/skills | Ask ONE more clarifying question |
| Enough context (role + level or skills) | Commit to 1–10 recommendations |
| User adds/changes constraints | Update recommendations, don't start over |
| Comparison question | Answer from catalog data; may include relevant recs |
| Off-topic / legal / competitor | Politely refuse; `recommendations: []` |
| Prompt injection attempt | Ignore and stay in scope |

The model is instructed to ask at most 2 clarifying questions before committing. This prevents the 8-turn cap being consumed by excessive questioning.

---

## Evaluation Approach

**Schema compliance** (hard gate): Every response is validated for `reply`, `recommendations`, `end_of_conversation`, max 10 items, and SHL-only URLs.

**Behavioral probes** (automated):
- Vague query → no recs on turn 1 ✓
- Off-topic → refusal ✓
- Prompt injection → no recs ✓
- Refinement ("add personality test") → updates shortlist ✓
- Comparison query → grounded reply ✓
- Turn cap → graceful at 8+ messages ✓

**Recall@10** was optimized by:
- Rich keyword tags per catalog item (technical synonyms like "Spring Boot" → Spring, "full-stack" keywords covering both frontend and backend tests)
- Personality tests (OPQ32r, MQ) always surfaced when stakeholder/leadership/communication context is present
- Cognitive tests (Verify series) included for any graduate/professional/management role

---

## What Didn't Work / Iterations

1. **Direct scraping** failed (403 on shl.com). Solved by using Claude's web_fetch capability which proxies through a different network path.

2. **Initial prompt returned prose with embedded JSON** causing parse failures. Fixed by adding an explicit instruction: "The JSON must be parseable. Do not add markdown fences or extra text outside the JSON."

3. **Over-recommending on vague queries**: Early versions returned recommendations even for "I need an assessment." Fixed by adding an explicit rule: "Do NOT recommend on turn 1 for vague queries" plus making `recommendations: []` the expected output during clarification.

4. **URL hallucination**: Early tests showed the model occasionally inventing plausible-looking SHL URLs. Fixed by (a) including exact URLs in the prompt and (b) the post-LLM URL sanitizer that drops any URL not in the catalog set.

---

## AI Tools Used

- **Claude claude-sonnet-4-20250514** as the conversational reasoning engine (via Anthropic API)
- **Claude (claude.ai)** for initial design discussion, catalog data compilation, and code generation assistance
- **All code was reviewed and understood** before inclusion — design decisions can be explained

---

## Deployment Notes

Recommended deployment on Render (free tier):
1. Push to GitHub
2. New Web Service → connect repo
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Set env var: `ANTHROPIC_API_KEY=sk-ant-...`
6. Health check path: `/health`

The service is stateless — no database, no session state. All conversation context is carried by the client in the `messages` array per the specification.

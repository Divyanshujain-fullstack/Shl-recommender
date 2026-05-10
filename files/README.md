# SHL Assessment Recommender

Conversational agent that helps hiring managers find the right SHL assessments through dialogue.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run the service
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API

### GET /health
```json
{"status": "ok"}
```

### POST /chat
**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "Hiring a Java developer who works with stakeholders"},
    {"role": "assistant", "content": "Sure. What is seniority level?"},
    {"role": "user", "content": "Mid-level, around 4 years"}
  ]
}
```

**Response:**
```json
{
  "reply": "Got it. Here are 5 assessments that fit a mid-level Java dev with stakeholder needs.",
  "recommendations": [
    {"name": "Java 8 (New)", "url": "https://www.shl.com/...", "test_type": "K"},
    {"name": "OPQ32r", "url": "https://www.shl.com/...", "test_type": "P"}
  ],
  "end_of_conversation": false
}
```

## Running Tests

```bash
# Start the server first, then:
python test_suite.py
```

## Deployment (Render)

1. Push to GitHub
2. Create new Web Service on render.com
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add env var: `ANTHROPIC_API_KEY`

## Design

- **No vector store**: Full catalog (73 items) fits in system prompt. Simpler, faster, higher recall.
- **Stateless**: Full conversation history passed on every request.
- **URL sanitizer**: Post-LLM filter ensures only catalog URLs are returned.
- **JSON-only output**: LLM instructed to return parseable JSON, with fallback parser.

## Test Type Codes

| Code | Type |
|------|------|
| A | Ability & Aptitude |
| B | Biodata & Situational Judgement |
| C | Competencies |
| D | Development & 360 |
| E | Assessment Exercises |
| K | Knowledge & Skills |
| P | Personality & Behavior |
| S | Simulations |

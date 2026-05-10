"""
SHL Assessment Recommender — FastAPI Service (Gemini)
"""
from __future__ import annotations
import json, os, re
from typing import List
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from catalog_data import get_catalog

app = FastAPI(title="SHL Assessment Recommender", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CATALOG = get_catalog()
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

def _build_catalog_text():
    lines = []
    for item in CATALOG:
        types = ", ".join(item["test_types"])
        desc = item.get("description", "")[:150]
        levels = ", ".join(item.get("job_levels", []))
        kws = ", ".join(item.get("keywords", [])[:8])
        lines.append(f'- "{item["name"]}" | types:{types} | levels:{levels} | url:{item["url"]}\n  desc: {desc}\n  keywords: {kws}')
    return "\n".join(lines)

CATALOG_TEXT = _build_catalog_text()

SYSTEM_PROMPT = f"""You are an expert SHL assessment consultant. Help hiring managers find the right SHL assessments.

## CATALOG
{CATALOG_TEXT}

## TEST TYPES
A=Ability, B=Biodata/SJT, C=Competencies, D=Development, E=Exercises, K=Knowledge/Skills, P=Personality, S=Simulations

## RULES
1. CLARIFY if query is vague - ask ONE question, return empty recommendations
2. RECOMMEND 1-10 assessments when you have enough context
3. REFINE when user changes constraints
4. COMPARE using catalog data only
5. REFUSE off-topic questions
6. NEVER invent URLs - only use catalog URLs

## OUTPUT - Return ONLY valid JSON:
{{"reply": "message", "recommendations": [{{"name": "exact name", "url": "exact url", "test_type": "letter"}}], "end_of_conversation": false}}"""

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str

class ChatResponse(BaseModel):
    reply: str
    recommendations: List[Recommendation]
    end_of_conversation: bool

VALID_URLS = {item["url"] for item in CATALOG}
URL_TO_ITEM = {item["url"]: item for item in CATALOG}

def sanitize_recommendations(recs):
    result, seen = [], set()
    for r in recs:
        url, name = r.get("url", ""), r.get("name", "")
        matched_url = url
        if url not in VALID_URLS:
            for item in CATALOG:
                if item["name"].lower() == name.lower():
                    matched_url = item["url"]
                    break
            else:
                continue
        if matched_url not in seen:
            seen.add(matched_url)
            item = URL_TO_ITEM.get(matched_url, {})
            result.append(Recommendation(name=item.get("name", name), url=matched_url, test_type=r.get("test_type", item.get("test_type", "K"))))
    return result[:10]

def parse_llm_response(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {"reply": text[:400] or "Please try again.", "recommendations": [], "end_of_conversation": False}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")
    messages = request.messages[-16:]
    try:
        history = []
        for msg in messages[:-1]:
            role = "user" if msg.role == "user" else "model"
            history.append({"role": role, "parts": [msg.content]})
        last_content = messages[-1].content
        chat_session = gemini_model.start_chat(history=history)
        prompt = f"{SYSTEM_PROMPT}\n\nUser: {last_content}" if len(history) == 0 else last_content
        response = chat_session.send_message(prompt)
        parsed = parse_llm_response(response.text)
        recs = sanitize_recommendations(parsed.get("recommendations", []))
        return ChatResponse(
            reply=parsed.get("reply", "Could you provide more details?"),
            recommendations=recs,
            end_of_conversation=bool(parsed.get("end_of_conversation", False)),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

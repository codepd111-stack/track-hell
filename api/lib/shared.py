"""
Shared utilities — DB (Vercel Postgres) + Groq LLM
"""

import os
import re
import json
import psycopg2
import psycopg2.extras
from groq import Groq

# ── GROQ ──────────────────────────────────────────────────────────────────────

def get_groq_client():
    return Groq(api_key=os.environ["GROQ_API_KEY"])

def call_llm(prompt, system="", model="llama3-70b-8192"):
    client = get_groq_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=1500
    )
    return response.choices[0].message.content

def parse_json_response(text):
    """Strip markdown fences and parse JSON safely."""
    cleaned = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except:
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return {}

# ── POSTGRES ──────────────────────────────────────────────────────────────────

def get_db():
    conn = psycopg2.connect(
        os.environ["POSTGRES_URL"],
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_logs (
            id SERIAL PRIMARY KEY,
            log_date DATE UNIQUE,
            raw_text TEXT,
            parsed_json JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id SERIAL PRIMARY KEY,
            name TEXT,
            playlist TEXT,
            total_items INTEGER,
            completed_items INTEGER DEFAULT 0,
            deadline DATE,
            category TEXT DEFAULT 'learning',
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS goal_progress (
            id SERIAL PRIMARY KEY,
            goal_id INTEGER REFERENCES goals(id),
            log_date DATE,
            items_done INTEGER,
            UNIQUE(goal_id, log_date)
        )
    """)
    conn.commit()
    c.close()
    conn.close()

# ── CORS HEADERS ──────────────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json"
}

def cors_response(data, status=200):
    return json.dumps(data), status, CORS_HEADERS

# ── PROMPTS ───────────────────────────────────────────────────────────────────

PARSE_SYSTEM = """You are a structured data extractor for a personal daily log assistant.
The user is an Indian vegetarian male doing a 90-day self-improvement challenge. He may go to the gym, run outdoors, study technical ML/AI content, and eat Indian food.

Extract from the freeform log and return ONLY valid JSON, no explanation:

{
  "wake_time": "HH:MM or null",
  "sleep_time": "HH:MM or null",
  "sleep_hours": float or null,
  "exercise": [
    {"type": "run|gym|walk|yoga|other", "details": "description", "distance_km": float or null, "duration_min": int or null}
  ],
  "meals": [
    {"meal": "breakfast|lunch|dinner|snack", "items": ["food1","food2"], "protein_est_g": float, "notes": ""}
  ],
  "learning": [
    {"topic": "LangGraph|PyTorch|etc", "platform": "CampusX|etc", "items_done": int, "notes": ""}
  ],
  "tv_hours": float or null,
  "doomscroll_hours": float or null,
  "mood_signal": "good|okay|tired|low|wasted",
  "notable": "one sentence summary"
}

Indian vegetarian protein estimates (use these):
- 1 chapati = 5g, 100g paneer = 18g, 1 cup dal = 9g, 1 cup rajma = 15g, 1 cup chana = 15g
- 100g tofu = 8g, 1 cup curd = 5g, 1 glass milk = 8g, 30g almonds = 6g, 2 eggs = 12g
- 1 cup moong = 7g, 100g sattu = 20g, 1 cup soya chunks = 25g

Return ONLY the JSON object."""

INSIGHT_SYSTEM = """You are a sharp, direct personal coach for an Indian vegetarian male on a 90-day self-improvement challenge. He may be going to the gym and is focused on fitness, nutrition, and learning ML/AI.

Given today's parsed log and recent history, generate insights in this EXACT JSON format:

{
  "fitness": "2-3 sentences. Compare today vs yesterday/week. Specific numbers. If gym session mention muscle groups. If no exercise, call it out plainly.",
  "nutrition": "2-3 sentences. Reference specific Indian foods eaten. Estimate total protein. Suggest specific Indian vegetarian additions if falling short — paneer, dal, curd, rajma, chana, tofu, soya chunks, sattu, milk, almonds, sprouts. If gym day, specifically mention pre/post workout nutrition needs. If dinner skipped, flag it.",
  "learning": "2-3 sentences. Videos/topics done vs recent days. Goal pace check. Specific catch-up advice if behind.",
  "sleep": "1-2 sentences. Hours and wake time consistency.",
  "time_quality": "1-2 sentences. Ratio of productive to passive hours. Data only, no moralising.",
  "mood": "1 sentence. Gentle observation from tone and word choices in the log.",
  "daily_protein_g": total estimated protein as integer
}

Be direct and specific. Warm but not motivational-poster cheesy. Return ONLY JSON."""

GOAL_DETECT_SYSTEM = """Detect if the user is setting a new learning/study goal.
A goal sounds like: 'I want to complete X playlist, Y videos, by [date]' or 'finish X in Y days' or similar.

Return JSON:
{
  "is_goal": true or false,
  "name": "short goal name",
  "playlist": "playlist or topic name",
  "total_items": integer,
  "deadline": "YYYY-MM-DD",
  "category": "learning"
}

If no goal detected, return {"is_goal": false}.
Today's year is 2025. Infer full date from partial mentions like 'June 25' -> '2025-06-25'.
Return ONLY JSON."""

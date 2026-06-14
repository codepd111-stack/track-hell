"""
POST /api/submit_log
Parses freeform daily log, saves to Postgres, returns insights + goal stats.
"""

import json
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from _shared import (
    get_db, init_db, call_llm, parse_json_response,
    cors_response, PARSE_SYSTEM, INSIGHT_SYSTEM, GOAL_DETECT_SYSTEM
)

def handler(request):
    if request.method == "OPTIONS":
        return cors_response({})

    if request.method != "POST":
        return cors_response({"error": "POST only"}, 405)

    try:
        init_db()
        body = request.get_json()
        raw_text = (body.get("text") or "").strip()
        log_date = body.get("date") or date.today().isoformat()

        if not raw_text:
            return cors_response({"error": "Empty log"}, 400)

        # ── 1. Detect goal ────────────────────────────────────────────────────
        goal_raw = call_llm(raw_text, system=GOAL_DETECT_SYSTEM)
        goal_info = parse_json_response(goal_raw)
        new_goal = None

        if goal_info.get("is_goal"):
            conn = get_db()
            c = conn.cursor()
            c.execute("""
                INSERT INTO goals (name, playlist, total_items, deadline, category)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                goal_info["name"], goal_info["playlist"],
                goal_info["total_items"], goal_info["deadline"],
                goal_info.get("category", "learning")
            ))
            conn.commit()
            c.close(); conn.close()
            new_goal = goal_info

        # ── 2. Parse log ──────────────────────────────────────────────────────
        parsed_raw = call_llm(raw_text, system=PARSE_SYSTEM)
        parsed = parse_json_response(parsed_raw)

        # ── 3. Save log ───────────────────────────────────────────────────────
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO daily_logs (log_date, raw_text, parsed_json)
            VALUES (%s, %s, %s)
            ON CONFLICT (log_date) DO UPDATE
              SET raw_text = EXCLUDED.raw_text,
                  parsed_json = EXCLUDED.parsed_json
        """, (log_date, raw_text, json.dumps(parsed)))
        conn.commit()

        # ── 4. Update goals from learning ─────────────────────────────────────
        c.execute("SELECT * FROM goals WHERE active = TRUE")
        goals = c.fetchall()
        for goal in goals:
            for item in parsed.get("learning", []):
                topic = item.get("topic", "").lower()
                playlist = (goal["playlist"] or "").lower()
                if topic in playlist or playlist in topic or any(w in playlist for w in topic.split()):
                    items_done = item.get("items_done", 0) or 0
                    if items_done > 0:
                        c.execute("""
                            INSERT INTO goal_progress (goal_id, log_date, items_done)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (goal_id, log_date) DO NOTHING
                        """, (goal["id"], log_date, items_done))
                        c.execute("""
                            UPDATE goals SET completed_items = completed_items + %s
                            WHERE id = %s
                        """, (items_done, goal["id"]))
        conn.commit()

        # ── 5. Fetch history ──────────────────────────────────────────────────
        cutoff = (date.fromisoformat(log_date) - timedelta(days=7)).isoformat()
        c.execute("""
            SELECT log_date::text, parsed_json FROM daily_logs
            WHERE log_date >= %s AND log_date < %s
            ORDER BY log_date DESC
        """, (cutoff, log_date))
        history_rows = c.fetchall()
        history = []
        for r in history_rows:
            history.append({"date": r["log_date"], "data": r["parsed_json"]})

        # ── 6. Goal stats ─────────────────────────────────────────────────────
        c.execute("SELECT * FROM goals WHERE active = TRUE ORDER BY deadline ASC")
        active_goals = c.fetchall()
        goal_stats = [compute_goal_stats(dict(g)) for g in active_goals]

        c.close(); conn.close()

        # ── 7. Generate insights ──────────────────────────────────────────────
        history_summary = []
        for h in history[:6]:
            d = h["data"]
            history_summary.append({
                "date": h["date"],
                "exercise": d.get("exercise", []),
                "meals_protein": sum(m.get("protein_est_g", 0) for m in d.get("meals", [])),
                "learning_items": sum(l.get("items_done", 0) for l in d.get("learning", [])),
                "mood": d.get("mood_signal")
            })

        insight_prompt = f"""Today's log (parsed):
{json.dumps(parsed, indent=2)}

Recent history (last {len(history_summary)} days):
{json.dumps(history_summary, indent=2)}

Active learning goals:
{json.dumps(goal_stats, indent=2)}

Generate insights JSON now."""

        insight_raw = call_llm(insight_prompt, system=INSIGHT_SYSTEM)
        insights = parse_json_response(insight_raw)

        return cors_response({
            "parsed": parsed,
            "insights": insights,
            "goal_stats": goal_stats,
            "new_goal": new_goal,
            "log_date": log_date
        })

    except Exception as e:
        return cors_response({"error": str(e)}, 500)


def compute_goal_stats(goal):
    from datetime import date as d
    today = d.today()
    deadline = d.fromisoformat(str(goal["deadline"]))
    days_left = max(0, (deadline - today).days)
    remaining = max(0, goal["total_items"] - goal["completed_items"])
    pace_needed = round(remaining / days_left, 1) if days_left > 0 else remaining
    pct = round((goal["completed_items"] / goal["total_items"]) * 100) if goal["total_items"] else 0
    return {
        "id": goal["id"],
        "name": goal["name"],
        "playlist": goal["playlist"],
        "total": goal["total_items"],
        "done": goal["completed_items"],
        "remaining": remaining,
        "deadline": str(goal["deadline"]),
        "days_left": days_left,
        "pace_needed": pace_needed,
        "on_track": pace_needed <= 3,
        "pct": pct
    }

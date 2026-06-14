"""
GET    /api/goals        — list active goals with stats
POST   /api/goals        — add a new goal
DELETE /api/goals?id=N   — archive a goal
"""

import json
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from _shared import get_db, init_db, cors_response


def compute_goal_stats(goal):
    today = date.today()
    deadline = date.fromisoformat(str(goal["deadline"]))
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


def handler(request):
    if request.method == "OPTIONS":
        return cors_response({})

    try:
        init_db()
        conn = get_db()
        c = conn.cursor()

        if request.method == "GET":
            c.execute("SELECT * FROM goals WHERE active = TRUE ORDER BY deadline ASC")
            goals = [compute_goal_stats(dict(g)) for g in c.fetchall()]
            c.close(); conn.close()
            return cors_response(goals)

        if request.method == "POST":
            body = request.get_json()
            c.execute("""
                INSERT INTO goals (name, playlist, total_items, deadline, category)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                body["name"], body["playlist"],
                int(body["total_items"]), body["deadline"],
                body.get("category", "learning")
            ))
            conn.commit()
            c.close(); conn.close()
            return cors_response({"success": True})

        if request.method == "DELETE":
            goal_id = request.args.get("id")
            c.execute("UPDATE goals SET active = FALSE WHERE id = %s", (goal_id,))
            conn.commit()
            c.close(); conn.close()
            return cors_response({"success": True})

    except Exception as e:
        return cors_response({"error": str(e)}, 500)

"""
GET /api/history?days=14   — recent daily logs
GET /api/stats             — weekly aggregated stats
"""

import sys
import os
import json
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from _shared import get_db, init_db, cors_response


def handler(request):
    if request.method == "OPTIONS":
        return cors_response({})

    try:
        init_db()
        path = request.path or ""
        conn = get_db()
        c = conn.cursor()

        if "stats" in path:
            cutoff = (date.today() - timedelta(days=7)).isoformat()
            c.execute("""
                SELECT parsed_json FROM daily_logs
                WHERE log_date >= %s ORDER BY log_date DESC
            """, (cutoff,))
            rows = c.fetchall()
            total_run = 0; total_protein = 0; total_learn = 0; days_ex = 0
            for r in rows:
                d = r["parsed_json"]
                for ex in d.get("exercise", []):
                    if ex.get("type") == "run" and ex.get("distance_km"):
                        total_run += ex["distance_km"]
                total_protein += sum(m.get("protein_est_g", 0) for m in d.get("meals", []))
                total_learn += sum(l.get("items_done", 0) for l in d.get("learning", []))
                if d.get("exercise"):
                    days_ex += 1
            n = len(rows) or 1
            c.close(); conn.close()
            return cors_response({
                "days_logged": len(rows),
                "avg_run_km": round(total_run / n, 2),
                "avg_protein_g": round(total_protein / n),
                "total_learning_items": total_learn,
                "days_exercised": days_ex
            })

        else:
            days = int(request.args.get("days", 14))
            cutoff = (date.today() - timedelta(days=days)).isoformat()
            c.execute("""
                SELECT log_date::text, parsed_json FROM daily_logs
                WHERE log_date >= %s ORDER BY log_date DESC
            """, (cutoff,))
            logs = [{"date": r["log_date"], "data": r["parsed_json"]} for r in c.fetchall()]
            c.close(); conn.close()
            return cors_response(logs)

    except Exception as e:
        return cors_response({"error": str(e)}, 500)

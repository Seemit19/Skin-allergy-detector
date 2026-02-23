import json
import os
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "allergy_logs.db"
HOST = "0.0.0.0"
PORT = 5000


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS allergy_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue TEXT NOT NULL,
            probable_allergy TEXT,
            most_likely_cause TEXT,
            remedies TEXT,
            precautions TEXT,
            factors TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def parse_json_from_response(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and start < end:
            return json.loads(raw_text[start : end + 1])
        raise


def analyze_issue_with_openai(issue: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    system_prompt = (
        "You are a medical triage assistant for allergy guidance. "
        "Given the user's symptom/problem text in any language, respond ONLY in valid JSON with this schema: "
        "{"
        "\"probable_allergy\": string,"
        "\"most_likely_cause\": string,"
        "\"remedies\": string[],"
        "\"precautions\": string[],"
        "\"triggering_factors\": string[]"
        "}. Include emergency warning for severe symptoms in precautions."
    )

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": issue},
        ],
        "temperature": 0.2,
    }

    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=60) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI HTTP error {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error contacting OpenAI: {exc}") from exc

    output_text = response_data.get("output_text", "").strip()
    parsed = parse_json_from_response(output_text)
    return {
        "probable_allergy": parsed.get("probable_allergy", "Unknown allergy"),
        "most_likely_cause": parsed.get("most_likely_cause", "Cause could not be determined"),
        "remedies": parsed.get("remedies", []),
        "precautions": parsed.get("precautions", []),
        "triggering_factors": parsed.get("triggering_factors", []),
    }


def build_history():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT id, issue, probable_allergy, most_likely_cause, remedies, precautions, factors, created_at
        FROM allergy_logs
        ORDER BY datetime(created_at) DESC
        """
    ).fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "issue": row["issue"],
            "probable_allergy": row["probable_allergy"],
            "most_likely_cause": row["most_likely_cause"],
            "remedies": json.loads(row["remedies"] or "[]"),
            "precautions": json.loads(row["precautions"] or "[]"),
            "factors": json.loads(row["factors"] or "[]"),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def build_report():
    conn = get_db_connection()
    rows = conn.execute("SELECT probable_allergy, factors, created_at FROM allergy_logs").fetchall()
    conn.close()

    allergy_counts = {}
    factor_counts = {}
    daily_counts = {}

    for row in rows:
        allergy = row["probable_allergy"] or "Unknown"
        allergy_counts[allergy] = allergy_counts.get(allergy, 0) + 1
        for factor in json.loads(row["factors"] or "[]"):
            factor_counts[factor] = factor_counts.get(factor, 0) + 1
        day = row["created_at"][:10]
        daily_counts[day] = daily_counts.get(day, 0) + 1

    return {
        "total_logs": len(rows),
        "allergy_frequency": allergy_counts,
        "factor_frequency": factor_counts,
        "daily_frequency": dict(sorted(daily_counts.items())),
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, code=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, content_type: str):
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self._send_file(BASE_DIR / "templates" / "index.html", "text/html; charset=utf-8")
            return
        if self.path == "/static/style.css":
            self._send_file(BASE_DIR / "static" / "style.css", "text/css; charset=utf-8")
            return
        if self.path == "/static/app.js":
            self._send_file(BASE_DIR / "static" / "app.js", "application/javascript; charset=utf-8")
            return
        if self.path == "/api/history":
            self._send_json(build_history())
            return
        if self.path == "/api/report":
            self._send_json(build_report())
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self):
        if self.path != "/api/analyze":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        data = json.loads(body)
        issue = (data.get("issue") or "").strip()

        if not issue:
            self._send_json({"error": "Please provide your allergy issue."}, code=400)
            return

        try:
            result = analyze_issue_with_openai(issue)
        except Exception as exc:
            self._send_json({"error": f"Failed to analyze issue: {exc}"}, code=500)
            return

        created_at = datetime.utcnow().isoformat()
        conn = get_db_connection()
        cursor = conn.execute(
            """
            INSERT INTO allergy_logs (issue, probable_allergy, most_likely_cause, remedies, precautions, factors, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                issue,
                result["probable_allergy"],
                result["most_likely_cause"],
                json.dumps(result["remedies"]),
                json.dumps(result["precautions"]),
                json.dumps(result["triggering_factors"]),
                created_at,
            ),
        )
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()

        self._send_json({"id": record_id, "issue": issue, **result, "created_at": created_at})


def run():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Server running on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()

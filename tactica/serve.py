"""HTTP server: serves the web/ directory and drives the tournament.

Endpoints:
  GET  /                       static files from web/
  GET  /api/models             list available LLM models from the gateway
  GET  /api/state              current tournament state
  POST /api/start              kick off a tournament (body: {model, rounds, mode})

Single-tournament-at-a-time. Uses threads, stdlib only.
"""

import http.server
import json
import os
import re
import socketserver
import sys
import threading
import traceback
from urllib.parse import urlparse

from .llm import DEFAULT_BASE_URL, LLMClient, LLMError
from .tournament import (
    load_existing_state, run_one_round, write_manifest,
)


WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")
WEB_DIR = os.path.abspath(WEB_DIR)


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock:
            self.status = "idle"            # idle | running | done | error
            self.mode = ""                  # continue | fresh
            self.model = ""
            self.message = ""
            self.current_round = 0
            self.rounds_done = 0
            self.target_rounds = 0
            self.log_tail = []
            self.error = None

    def snapshot(self):
        with self.lock:
            return {
                "status": self.status,
                "mode": self.mode,
                "model": self.model,
                "message": self.message,
                "current_round": self.current_round,
                "rounds_done": self.rounds_done,
                "target_rounds": self.target_rounds,
                "log_tail": list(self.log_tail[-30:]),
                "error": self.error,
            }


STATE = State()
RUN_LOCK = threading.Lock()


def _log_fn(msg):
    """Logger passed into run_one_round. Mirrors to stdout and structures
    state.message based on known log patterns."""
    if not isinstance(msg, str):
        msg = str(msg)
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
    s = msg.strip()
    if not s:
        return
    with STATE.lock:
        STATE.log_tail.append(s)
        if len(STATE.log_tail) > 200:
            del STATE.log_tail[: len(STATE.log_tail) - 200]
        if s.startswith("=== Round "):
            m = re.search(r"Round (\d+)", s)
            if m:
                STATE.current_round = int(m.group(1))
                STATE.message = f"Round {m.group(1)}: starting"
        elif "[red] LLM call" in s:
            STATE.message = f"Round {STATE.current_round}: asking RED…"
        elif "[blue] LLM call" in s:
            STATE.message = f"Round {STATE.current_round}: asking BLUE…"
        elif "validation failed" in s:
            STATE.message = f"Round {STATE.current_round}: brief invalid, retrying…"
        elif "Running battle" in s:
            STATE.message = f"Round {STATE.current_round}: running battle"
        elif s.startswith("  Battle done"):
            STATE.message = f"Round {STATE.current_round}: saving"
        elif s.startswith("  Recording:"):
            STATE.rounds_done += 1
            STATE.message = (
                f"Round {STATE.current_round} saved "
                f"({STATE.rounds_done}/{STATE.target_rounds})"
            )


def _run_thread(model, rounds, mode, out_dir, base_url, temperature):
    try:
        client = LLMClient(base_url=base_url)

        if mode == "fresh":
            # Reset the manifest so the UI immediately shows an empty list;
            # leftover round_NNN.json files get overwritten as new rounds run.
            os.makedirs(out_dir, exist_ok=True)
            empty = {
                "model": model, "base_url": base_url,
                "rounds_total": 0, "rounds": [],
            }
            write_manifest(empty, out_dir)
            manifest = empty
            prev_reports = {"red": None, "blue": None}
            start_round = 1
        else:
            manifest, prev_reports, start_round = load_existing_state(out_dir)
            if manifest is None:
                manifest = {
                    "model": model, "base_url": base_url,
                    "rounds_total": 0, "rounds": [],
                }
                start_round = 1

        end_round = start_round + rounds
        manifest["rounds_total"] = end_round - 1
        manifest["model"] = model
        manifest["base_url"] = base_url
        write_manifest(manifest, out_dir)

        with STATE.lock:
            STATE.target_rounds = rounds
            STATE.rounds_done = 0
            STATE.message = f"Starting round {start_round}"

        for round_n in range(start_round, end_round):
            seed = 1000 + round_n
            summary, reports = run_one_round(
                client, model, round_n, seed, prev_reports, out_dir,
                log=_log_fn,
            )
            manifest["rounds"].append(summary)
            write_manifest(manifest, out_dir)
            prev_reports = reports

        with STATE.lock:
            STATE.status = "done"
            STATE.message = f"Completed {rounds} round(s)"
    except Exception as e:
        traceback.print_exc()
        with STATE.lock:
            STATE.status = "error"
            STATE.error = f"{type(e).__name__}: {e}"
            STATE.message = f"ERROR: {STATE.error}"
    finally:
        try:
            RUN_LOCK.release()
        except RuntimeError:
            pass


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            return self._json(STATE.snapshot())
        if path == "/api/models":
            try:
                client = LLMClient()
                return self._json({"models": client.list_models()})
            except LLMError as e:
                return self._json({"error": str(e), "models": []}, status=502)
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/start":
            length = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return self._json({"error": "invalid JSON"}, status=400)

            model = (req.get("model") or "").strip()
            try:
                rounds = int(req.get("rounds", 1))
            except (TypeError, ValueError):
                return self._json({"error": "rounds must be int"}, status=400)
            mode = req.get("mode", "continue")

            if not model:
                return self._json({"error": "model required"}, status=400)
            if rounds < 1 or rounds > 50:
                return self._json({"error": "rounds must be 1..50"}, status=400)
            if mode not in {"continue", "fresh"}:
                return self._json({"error": "mode must be continue|fresh"}, status=400)

            if not RUN_LOCK.acquire(blocking=False):
                return self._json(
                    {"error": "a tournament is already running"}, status=409
                )

            STATE.reset()
            with STATE.lock:
                STATE.status = "running"
                STATE.mode = mode
                STATE.model = model
                STATE.target_rounds = rounds
                STATE.message = "Starting…"

            out_dir = os.path.join(WEB_DIR, "rounds")
            t = threading.Thread(
                target=_run_thread,
                args=(model, rounds, mode, out_dir, DEFAULT_BASE_URL, 0.6),
                daemon=True,
            )
            t.start()
            return self._json({"started": True})

        self.send_response(404)
        self.end_headers()

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Less noisy than default; only log non-static.
        if "/api/" in self.path:
            sys.stderr.write(
                f"{self.client_address[0]} {self.command} {self.path} "
                f"-> {args[1] if len(args) > 1 else '?'}\n"
            )


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    port = int(os.environ.get("TACTICA_PORT", "8765"))
    server = ThreadingServer(("0.0.0.0", port), Handler)
    print(f"Tactica server: http://localhost:{port}", flush=True)
    print(f"Serving from: {WEB_DIR}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down…")
        server.shutdown()


if __name__ == "__main__":
    main()

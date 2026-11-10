"""Sticky Notes server. Run:  python app.py   then open http://localhost:8000
Uses only the Python standard library. Notes and folders are saved to notes.json.
Music: .mp3 files are added in the browser and stored there, so the server needs nothing for them."""
import json, os, urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "notes.json")
SCHED = os.path.join(ROOT, "schedule.json")  # schedule picture + reminder settings
PRIVATE = ("/app.py", "/notes.json", "/schedule.json")


def read_data():
    d = []
    if os.path.exists(DATA):
        try:
            with open(DATA, encoding="utf-8") as f:
                d = json.load(f)
        except ValueError:
            d = []
    if isinstance(d, list):  # older file: just a list of notes
        d = {"notes": d, "folders": None}
    return d


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/api/notes":
            d = read_data()
            out = {"notes": d.get("notes") or []}
            if isinstance(d.get("folders"), list):
                out["folders"] = d["folders"]
            return self._json(out)
        if url.path == "/api/schedule":
            try:
                with open(SCHED, encoding="utf-8") as f:
                    return self._json(json.load(f))
            except (OSError, ValueError):
                return self._json({})
        if url.path in PRIVATE:
            return self.send_error(404)
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/schedule":
            try:
                size = int(self.headers.get("Content-Length", 0))
                assert size < 80_000_000
                p = json.loads(self.rfile.read(size))
                imgs, st = p.get("images", []), p.get("settings", {})
                assert isinstance(imgs, list) and len(imgs) <= 40 and isinstance(st, dict)
                clean = []
                for i in imgs:
                    assert isinstance(i, dict) and isinstance(i.get("src"), str) and i["src"].startswith("data:image/")
                    clean.append({
                        "id": str(i.get("id", ""))[:20],
                        "src": i["src"],
                        "name": str(i.get("name", ""))[:80],
                        "board": bool(i.get("board")),
                        "x": float(i.get("x") or 0), "y": float(i.get("y") or 0),
                        "w": float(i.get("w") or 240), "r": float(i.get("r") or 0),
                    })
            except (ValueError, TypeError, AssertionError, AttributeError):
                return self._json({"error": "Bad schedule data."}, 400)
            with open(SCHED, "w", encoding="utf-8") as f:
                json.dump({"images": clean, "settings": st}, f)
            return self._json({"saved": True})
        if self.path != "/api/notes":
            return self.send_error(404)
        try:
            size = int(self.headers.get("Content-Length", 0))
            p = json.loads(self.rfile.read(size))
            old = read_data()
            if isinstance(p, list):
                data = {"notes": p[:200], "folders": old.get("folders")}
            else:
                assert isinstance(p, dict) and isinstance(p.get("notes"), list)
                fl = p.get("folders")
                data = {"notes": p["notes"][:200], "folders": fl[:50] if isinstance(fl, list) else old.get("folders")}
        except (ValueError, AssertionError):
            return self._json({"error": "Send a JSON list of notes."}, 400)
        with open(DATA, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self._json({"saved": len(data["notes"])})

    def log_message(self, *args):
        pass


def lan_ip():
    """This computer's address on the Wi-Fi, so a phone can open the app too."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


if __name__ == "__main__":
    print("Sticky Notes running at http://localhost:8000  (Ctrl+C to stop)")
    ip = lan_ip()
    if ip:
        print(f"On your phone (same Wi-Fi): http://{ip}:8000")
    ThreadingHTTPServer(("", 8000), Handler).serve_forever()

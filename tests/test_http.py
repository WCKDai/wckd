#!/usr/bin/env python3
"""The HTTP transport: any agent that can make a request can drive WCKD."""
import json, socket, subprocess, sys, time, unittest, urllib.error, urllib.request

from tree import Tree


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = Tree()
        cls.port = free_port()
        cls.proc = subprocess.Popen(
            [sys.executable, str(cls.t.root / "bin" / "wckd.py"), "serve", "--port", str(cls.port), "--quiet"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(100):
            try:
                cls.get("/health")
                return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("server did not start: " + (cls.proc.stdout.read() if cls.proc.stdout else ""))

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
        cls.t.close()

    @classmethod
    def url(cls, path):
        return f"http://127.0.0.1:{cls.port}{path}"

    @classmethod
    def get(cls, path):
        with urllib.request.urlopen(cls.url(path), timeout=10) as r:
            return json.loads(r.read())

    @classmethod
    def post(cls, path, body):
        req = urllib.request.Request(cls.url(path), data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())

    def test_health_and_protocol(self):
        self.assertTrue(self.get("/health")["ok"])
        proto = self.get("/protocol")
        self.assertEqual(proto["protocol"], "WCKD")
        self.assertEqual(len(proto["phases"]), 4)

    def test_create_then_drive(self):
        created = self.post("/projects", {"slug": "api", "wish": "A CLI that says hi", "by": "test"})
        self.assertEqual(created["created"], "api")
        self.assertIn("G-W", self.get("/projects/api")["status"])
        self.assertIn("step W1", self.get("/projects/api/next")["next"])
        handoff = self.get("/projects/api/handoff?format=md")
        self.assertIn("WCKD handoff", handoff["markdown"])
        projects = self.get("/projects")
        self.assertEqual([p["slug"] for p in projects], ["api"])

    def test_invalid_artifact_is_refused_over_http(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post("/projects/api/artifacts/brief.json", {"content": {"nope": True}})
        self.assertEqual(e.exception.code, 400)
        self.assertIn("does not validate", e.exception.read().decode())

    def test_write_then_gate(self):
        path = self.t.project("api") / "brief.json"
        brief = json.loads((self.t.root / "examples" / "air-quality-monitor" / "brief.json").read_text())
        written = self.post("/projects/api/artifacts/brief.json", {"content": brief})
        self.assertTrue(written["wrote"].endswith("brief.json"))
        out = self.post("/projects/api/gates/G-W", {"by": "Galahad", "human": True})
        self.assertIn("PASS", out["output"])
        self.assertTrue(path.exists())
        self.assertEqual(json.loads((self.t.project("api") / "gates" / "G-W.json").read_text())["decision"], "PASS")

    def test_unknown_route(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get("/nope")
        self.assertEqual(e.exception.code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)

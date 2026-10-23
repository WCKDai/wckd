"""Shared test helper: a throwaway copy of the protocol tree, so tests never touch the real projects/."""
import shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIECES = ["bin", "schemas", "workflows", "templates", "memory", "machine", "agents", "examples"]
FILES = ["SOUL.md", "GOALS.md", "SKILLS.md", "PROTOCOL.md"]


class Tree:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "wckd"
        self.root.mkdir()
        for d in PIECES:
            if (ROOT / d).exists():
                shutil.copytree(ROOT / d, self.root / d)
        for f in FILES:
            if (ROOT / f).exists():
                shutil.copy(ROOT / f, self.root / f)
        (self.root / "projects").mkdir()

    def cli(self, *args, expect=0, env=None):
        import os
        e = dict(os.environ)
        if env:
            e.update(env)
        r = subprocess.run([sys.executable, str(self.root / "bin" / "wckd.py")] + list(args),
                           capture_output=True, text=True, env=e)
        if expect is not None and r.returncode != expect:
            raise AssertionError(f"{' '.join(args)} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
        return r.stdout + r.stderr

    def project(self, slug="p"):
        return self.root / "projects" / slug

    def close(self):
        self._tmp.cleanup()

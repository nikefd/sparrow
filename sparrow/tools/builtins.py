"""Built-in tool battery — turns sparrow from a pure engine into an agent that
can actually do things (read/write files, search, run commands, fetch URLs).

All opt-in: a host wires them explicitly with ``tools=[*builtins(), ...]``; the
core stays domain-agnostic. The three dangerous tools (write_file / edit_file /
run_bash) are marked ``writes=True`` so they route through the approval gate when
an approver is configured — basic tools and human-in-the-loop are designed to
pair. Everything here is stdlib-only.

``builtins(root=None, *, allow=None)``:
  - ``root`` confines all file operations under one directory (paths that escape
    are rejected). Recommended whenever the agent isn't fully trusted.
  - ``allow`` selects a subset by name, e.g. ``allow={"read_file", "grep"}``.
"""
from __future__ import annotations

import glob as _glob
import re
import subprocess
import urllib.request
from pathlib import Path

from .registry import tool

_ALL = ["read_file", "list_dir", "glob", "grep",
        "write_file", "edit_file", "run_bash", "http_fetch"]


def _safe(root, path: str) -> Path:
    """Resolve ``path``; if a sandbox ``root`` is set, reject escapes."""
    if root is None:
        return Path(path).expanduser()
    base = Path(root).expanduser().resolve()
    p = (base / path).resolve()
    if base != p and base not in p.parents:
        raise ValueError(f"path escapes sandbox root: {path}")
    return p


def builtins(root=None, *, allow=None):
    """Return the built-in tools (optionally sandboxed to ``root`` and filtered to
    ``allow``)."""
    @tool(description="Read a UTF-8 text file.", source="builtin:fs", label="read")
    def read_file(path: str) -> dict:
        p = _safe(root, path)
        return {"path": str(p), "content": p.read_text(encoding="utf-8", errors="replace"),
                "source": f"file:{p}"}

    @tool(description="List entries in a directory.", source="builtin:fs", label="ls")
    def list_dir(path: str = ".") -> dict:
        p = _safe(root, path)
        return {"path": str(p), "entries": sorted(e.name + ("/" if e.is_dir() else "")
                                                  for e in p.iterdir())}

    @tool(description="Glob for files matching a pattern (e.g. '**/*.py').",
          source="builtin:fs", label="glob")
    def glob(pattern: str) -> dict:
        base = Path(root).expanduser().resolve() if root else Path(".")
        matches = [str(Path(m)) for m in _glob.glob(str(base / pattern), recursive=True)]
        return {"pattern": pattern, "matches": sorted(matches)}

    @tool(description="Search file contents for a regex; returns matching lines.",
          source="builtin:fs", label="grep")
    def grep(pattern: str, path: str = ".") -> dict:
        rx = re.compile(pattern)
        base = _safe(root, path)
        files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()]
        hits = []
        for f in files:
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if rx.search(line):
                        hits.append({"file": str(f), "line": i, "text": line[:300]})
                        if len(hits) >= 200:
                            return {"pattern": pattern, "hits": hits, "_summary": "200+ hits (truncated)"}
            except OSError:
                continue
        return {"pattern": pattern, "hits": hits}

    @tool(description="Write (overwrite) a UTF-8 text file. Requires approval.",
          source="builtin:fs", label="write", writes=True)
    def write_file(path: str, content: str = "", conversation_id: str = "") -> dict:
        p = _safe(root, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p), "bytes": len(content.encode()),
                "_summary": f"wrote {p}"}

    @tool(description="Replace an exact substring in a file. Requires approval.",
          source="builtin:fs", label="edit", writes=True)
    def edit_file(path: str, old: str, new: str = "", conversation_id: str = "") -> dict:
        p = _safe(root, path)
        text = p.read_text(encoding="utf-8")
        if old not in text:
            return {"error": "old string not found"}
        if text.count(old) > 1:
            return {"error": f"old string is not unique ({text.count(old)} matches)"}
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        return {"ok": True, "path": str(p), "_summary": f"edited {p}"}

    @tool(description="Run a shell command and capture output. Requires approval.",
          source="builtin:shell", label="bash", writes=True)
    def run_bash(command: str, conversation_id: str = "") -> dict:
        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return {"error": "command timed out (30s)"}
        return {"command": command, "returncode": r.returncode,
                "stdout": r.stdout[:8000], "stderr": r.stderr[:2000],
                "_summary": f"exit {r.returncode}"}

    @tool(description="Fetch a URL and return its text body.", source="builtin:web", label="fetch")
    def http_fetch(url: str) -> dict:
        with urllib.request.urlopen(url, timeout=20) as resp:
            body = resp.read(1_000_000).decode("utf-8", errors="replace")
            return {"url": url, "status": getattr(resp, "status", 200), "body": body,
                    "source": url}

    local = {"read_file": read_file, "list_dir": list_dir, "glob": glob, "grep": grep,
             "write_file": write_file, "edit_file": edit_file, "run_bash": run_bash,
             "http_fetch": http_fetch}
    names = allow or _ALL
    return [local[n] for n in _ALL if n in names]

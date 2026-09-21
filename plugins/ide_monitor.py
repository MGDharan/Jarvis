"""
IDE Monitor Plugin — JARVIS watches your open IDE and works autonomously.

What it does:
  1. Detects which IDE is currently open (VS Code, Kiro, Code Insiders,
     Antigravity, PyCharm, Cursor, Windsurf, etc.)
  2. Reads the active project folder from the window title
  3. Scans the project files to understand what it is (language, framework, purpose)
  4. Auto-accepts AI notifications/popups in the IDE (Copilot, Kiro suggestions, etc.)
  5. Proactively improves the project in the background using Gemini:
       - Finds bugs, missing error handling, performance issues
       - Generates improvement suggestions and writes them as comments / fixes
       - Reports what it did via JARVIS voice when user returns
  6. Runs continuously until user says "stop monitoring IDE"

Trigger phrases:
  "monitor my IDE"         → start watching
  "watch my code"          → start watching
  "monitor my VS Code"     → start watching
  "stop monitoring IDE"    → stop
  "what are you doing in my code" → status report
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import threading
import time
import warnings
from pathlib import Path

_OS = platform.system()

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

try:
    import win32gui
    import win32process
    _WIN32 = True
except ImportError:
    _WIN32 = False

try:
    from google import genai as _genai
    _GENAI = True
except ImportError:
    _GENAI = False

try:
    import uiautomation as _auto
    _UIA = True
except ImportError:
    _UIA = False

# ── PLUGIN manifest ───────────────────────────────────────────────────────────
PLUGIN = {
    "name": "ide_monitor",
    "description": (
        "Monitors the user's open IDE (VS Code, Kiro, Code Insiders, Antigravity, "
        "PyCharm, Cursor, etc.), detects the active project, analyzes the codebase, "
        "auto-accepts AI notifications/suggestions, and autonomously improves the "
        "project in the background. "
        "Trigger phrases to START: 'monitor my IDE', 'watch my code', "
        "'monitor my VS Code', 'keep an eye on my project', 'work on my code while I am away'. "
        "Trigger phrases to STOP: 'stop monitoring IDE', 'stop watching my code', "
        "'what are you doing in my code' (status report)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'start' to begin monitoring, 'stop' to end, 'status' for report.",
            },
            "ide": {
                "type": "STRING",
                "description": (
                    "Optional: name of IDE to focus on — 'vscode', 'kiro', "
                    "'insiders', 'antigravity', 'pycharm', 'cursor'. "
                    "Leave blank to auto-detect."
                ),
            },
            "mode": {
                "type": "STRING",
                "description": (
                    "'observe' — analyze only, never write files. "
                    "'assist' (default) — analyze + write improvement comments/fixes. "
                    "'auto' — full autonomous improvement, writes code directly."
                ),
            },
        },
        "required": ["action"],
    },
}

# ── Known IDEs ────────────────────────────────────────────────────────────────
_IDE_SIGNATURES = [
    # (process_name_fragment, display_name, window_title_pattern)
    ("code.exe",           "VS Code",          r"(.+?) [-–—] Visual Studio Code"),
    ("code - insiders.exe","Code Insiders",     r"(.+?) [-–—] Visual Studio Code"),
    ("kiro.exe",           "Kiro",              r"(.+?) [-–—] Kiro"),
    ("antigravity",        "Antigravity IDE",   r"(.+?) [-–—] Antigravity"),
    ("pycharm",            "PyCharm",           r"(.+?) [-–—] PyCharm"),
    ("cursor.exe",         "Cursor",            r"(.+?) [-–—] Cursor"),
    ("windsurf.exe",       "Windsurf",          r"(.+?) [-–—] Windsurf"),
    ("webstorm",           "WebStorm",          r"(.+?) [-–—] WebStorm"),
    ("clion",              "CLion",             r"(.+?) [-–—] CLion"),
    ("goland",             "GoLand",            r"(.+?) [-–—] GoLand"),
    ("rider",              "Rider",             r"(.+?) [-–—] Rider"),
    ("sublime_text",       "Sublime Text",      r"(.+?) [-–—] Sublime Text"),
    ("notepad++",          "Notepad++",         r"(.+?) [-–—] Notepad\+\+"),
    ("vim",                "Vim",               None),
    ("nvim",               "Neovim",            None),
]

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"

# ── Module state ──────────────────────────────────────────────────────────────
_monitor_thread: threading.Thread | None = None
_monitoring = False
_stop_evt   = threading.Event()
_status: dict = {
    "ide":          "",
    "project_path": "",
    "project_name": "",
    "language":     "",
    "last_action":  "",
    "actions_done": [],
    "start_time":   0.0,
}


# ─────────────────────────────────────────────────────────────────────────────
# IDE Detection
# ─────────────────────────────────────────────────────────────────────────────

def _load_api_key() -> str:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8")).get("gemini_api_key", "")
    except Exception:
        return ""


def _detect_ide_windows() -> tuple[str, str, str]:
    """
    Returns (ide_display_name, window_title, project_path).
    Uses win32gui to enumerate windows and match IDE process names.
    """
    if not _WIN32 or not _PSUTIL:
        return "", "", ""

    best: tuple[str, str, str] = ("", "", "")

    def _enum_cb(hwnd, _):
        nonlocal best
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            proc_name = proc.name().lower()
        except Exception:
            return

        for proc_frag, display_name, title_pattern in _IDE_SIGNATURES:
            if proc_frag.lower() in proc_name:
                project_path = ""
                if title_pattern:
                    m = re.search(title_pattern, title, re.IGNORECASE)
                    if m:
                        raw = m.group(1).strip()
                        # Try to resolve as a path
                        p = Path(raw)
                        if p.exists() and p.is_dir():
                            project_path = str(p)
                        else:
                            # Search common locations
                            for base in [
                                Path.home() / "Desktop",
                                Path.home() / "Documents",
                                Path("F:/jarvis"),
                                Path("C:/Users") / os.environ.get("USERNAME", "") / "source",
                                Path.home(),
                            ]:
                                candidate = base / raw
                                if candidate.exists() and candidate.is_dir():
                                    project_path = str(candidate)
                                    break
                best = (display_name, title, project_path)
                return

    try:
        win32gui.EnumWindows(_enum_cb, None)
    except Exception:
        pass

    return best


def _detect_ide_from_processes() -> tuple[str, str, str]:
    """Fallback: scan running processes for IDE executables."""
    if not _PSUTIL:
        return "", "", ""
    for proc in psutil.process_iter(["name", "exe", "cmdline"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            for proc_frag, display_name, _ in _IDE_SIGNATURES:
                if proc_frag.lower() in pname:
                    # Try to extract project path from cmdline
                    cmdline = proc.info.get("cmdline") or []
                    for arg in reversed(cmdline):
                        p = Path(arg)
                        if p.exists() and p.is_dir() and len(arg) > 3:
                            return display_name, pname, str(p)
                    return display_name, pname, ""
        except Exception:
            continue
    return "", "", ""


def _detect_ide() -> tuple[str, str, str]:
    """Returns (ide_name, window_title_or_proc, project_path)."""
    if _OS == "Windows":
        result = _detect_ide_windows()
        if result[0]:
            return result
    return _detect_ide_from_processes()


# ─────────────────────────────────────────────────────────────────────────────
# Project Analysis
# ─────────────────────────────────────────────────────────────────────────────

_LANG_EXTENSIONS = {
    ".py":   "Python",
    ".js":   "JavaScript",
    ".ts":   "TypeScript",
    ".jsx":  "React/JSX",
    ".tsx":  "React/TSX",
    ".rs":   "Rust",
    ".go":   "Go",
    ".java": "Java",
    ".cs":   "C#",
    ".cpp":  "C++",
    ".c":    "C",
    ".html": "HTML",
    ".css":  "CSS",
    ".rb":   "Ruby",
    ".php":  "PHP",
    ".swift":"Swift",
    ".kt":   "Kotlin",
    ".dart": "Dart",
    ".lua":  "Lua",
    ".sh":   "Shell",
}

_IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    "dist", "build", ".next", ".cache", "target", "bin", "obj",
    ".idea", ".vscode", ".kiro",
}

_MAX_FILE_READ_BYTES = 6000   # per file for context
_MAX_FILES_FOR_CONTEXT = 12   # number of source files to include in analysis


def _scan_project(project_path: str) -> dict:
    """
    Scan a project directory and return:
    {
        "language": str,
        "framework": str,
        "purpose": str (inferred),
        "file_count": int,
        "files": [(path, size, snippet), ...],
        "entry_point": str | None,
        "dependencies": [str],
    }
    """
    root = Path(project_path)
    if not root.exists():
        return {}

    ext_counts: dict[str, int] = {}
    source_files: list[Path]   = []

    for f in root.rglob("*"):
        if any(part in _IGNORE_DIRS for part in f.parts):
            continue
        if f.is_file():
            ext = f.suffix.lower()
            if ext in _LANG_EXTENSIONS:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                source_files.append(f)

    if not ext_counts:
        return {"language": "Unknown", "file_count": 0, "files": []}

    # Dominant language
    dominant_ext = max(ext_counts, key=ext_counts.get)
    language = _LANG_EXTENSIONS.get(dominant_ext, "Unknown")

    # Sort files: entry points first, then by size desc
    def _priority(p: Path) -> int:
        name = p.name.lower()
        if name in ("main.py", "index.py", "app.py", "server.py", "main.ts",
                     "index.ts", "app.ts", "main.js", "index.js", "app.js"):
            return 0
        return 1

    source_files.sort(key=lambda p: (_priority(p), -p.stat().st_size))

    # Read snippets
    files_context = []
    for f in source_files[:_MAX_FILES_FOR_CONTEXT]:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            snippet = content[:_MAX_FILE_READ_BYTES]
            files_context.append((str(f.relative_to(root)), f.stat().st_size, snippet))
        except Exception:
            files_context.append((str(f.relative_to(root)), 0, ""))

    # Dependencies
    deps: list[str] = []
    for dep_file in ["requirements.txt", "package.json", "Cargo.toml",
                      "go.mod", "pom.xml", "build.gradle"]:
        dep_path = root / dep_file
        if dep_path.exists():
            try:
                deps_text = dep_path.read_text(encoding="utf-8", errors="replace")[:500]
                deps.append(f"{dep_file}:\n{deps_text}")
            except Exception:
                pass

    # Entry point
    entry = None
    for candidate in ["main.py", "app.py", "index.py", "server.py",
                       "main.ts", "index.ts", "index.js", "main.js"]:
        if (root / candidate).exists():
            entry = candidate
            break

    return {
        "language":    language,
        "framework":   _detect_framework(root, language),
        "file_count":  len(source_files),
        "files":       files_context,
        "entry_point": entry,
        "dependencies":deps,
        "root":        str(root),
    }


def _detect_framework(root: Path, language: str) -> str:
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "next" in deps:     return "Next.js"
            if "react" in deps:    return "React"
            if "vue" in deps:      return "Vue.js"
            if "svelte" in deps:   return "Svelte"
            if "express" in deps:  return "Express.js"
            if "fastify" in deps:  return "Fastify"
        except Exception:
            pass

    req = root / "requirements.txt"
    if req.exists():
        try:
            text = req.read_text(encoding="utf-8", errors="replace").lower()
            if "fastapi" in text:   return "FastAPI"
            if "flask" in text:     return "Flask"
            if "django" in text:    return "Django"
            if "pytorch" in text:   return "PyTorch"
            if "tensorflow" in text: return "TensorFlow"
            if "streamlit" in text: return "Streamlit"
            if "gradio" in text:    return "Gradio"
        except Exception:
            pass

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Gemini Analysis & Improvement
# ─────────────────────────────────────────────────────────────────────────────

def _build_project_context(scan: dict) -> str:
    """Build a compact text block describing the project for Gemini."""
    lines = []
    lines.append(f"Language: {scan.get('language', 'Unknown')}")
    if scan.get("framework"):
        lines.append(f"Framework: {scan['framework']}")
    lines.append(f"Source files: {scan.get('file_count', 0)}")
    if scan.get("entry_point"):
        lines.append(f"Entry point: {scan['entry_point']}")
    if scan.get("dependencies"):
        lines.append("\nDependencies:\n" + "\n".join(scan["dependencies"])[:600])
    lines.append("\n--- Source files ---")
    for rel_path, size, snippet in scan.get("files", []):
        lines.append(f"\n### {rel_path} ({size} bytes)")
        lines.append(snippet[:3000])
    return "\n".join(lines)


def _gemini_analyze(scan: dict) -> str:
    """Ask Gemini to analyze the project and return findings."""
    api_key = _load_api_key()
    if not api_key or not _GENAI:
        return ""

    context = _build_project_context(scan)
    prompt = (
        "You are JARVIS, an expert software engineer analyzing a project autonomously. "
        "The user is away from their keyboard. Study this codebase carefully.\n\n"
        f"{context}\n\n"
        "Provide a structured analysis with:\n"
        "1. PROJECT PURPOSE — what this project does in 1-2 sentences\n"
        "2. LANGUAGE & STACK — confirmed tech stack\n"
        "3. CODE ISSUES — specific bugs, errors, or problems you can see (file:line if possible)\n"
        "4. IMPROVEMENTS — 3-5 concrete improvements ranked by impact\n"
        "5. QUICK WINS — things that can be fixed in < 10 lines each\n\n"
        "Be specific. Reference actual file names and line numbers where possible. "
        "Do not be generic. If you see an actual bug, name it precisely."
    )

    try:
        client = _genai.Client(api_key=api_key)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
        return (response.text or "").strip()
    except Exception as e:
        print(f"[IDEMonitor] Gemini analyze error: {e}")
        return ""


def _gemini_improve_file(file_path: str, content: str, scan: dict, issue: str) -> str:
    """Ask Gemini to rewrite a specific file with improvements."""
    api_key = _load_api_key()
    if not api_key or not _GENAI:
        return content

    prompt = (
        f"You are JARVIS improving code autonomously. The user is away.\n\n"
        f"Project: {scan.get('language', 'Unknown')} / {scan.get('framework', '')}\n"
        f"File: {file_path}\n"
        f"Issue to fix: {issue}\n\n"
        f"Current code:\n{content[:8000]}\n\n"
        "Rewrite this file with the issue fixed. "
        "Preserve ALL existing functionality. Only fix the specified issue. "
        "Return ONLY the complete corrected code with no explanation, "
        "no markdown fences, no preamble."
    )

    try:
        client = _genai.Client(api_key=api_key)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
        result = (response.text or "").strip()
        # Strip markdown fences if Gemini added them
        result = re.sub(r"^```[a-zA-Z]*\n?", "", result)
        result = re.sub(r"\n?```\s*$", "", result)
        return result.strip() if result.strip() else content
    except Exception as e:
        print(f"[IDEMonitor] Gemini improve error: {e}")
        return content


def _gemini_summarize_work(actions: list[str], scan: dict) -> str:
    """Ask Gemini to produce a natural-language summary of what was done."""
    api_key = _load_api_key()
    if not api_key or not _GENAI:
        return "I worked on your project while you were away."

    prompt = (
        f"You are JARVIS reporting back to the user. "
        f"Project: {scan.get('language', '')} / {scan.get('framework', '')} "
        f"at {scan.get('root', 'unknown location')}.\n\n"
        f"Actions taken:\n" + "\n".join(f"- {a}" for a in actions) + "\n\n"
        "Write a concise 2-3 sentence spoken report to the user starting with 'Sir,'. "
        "Be specific about what was improved. Sound like JARVIS."
    )

    try:
        client = _genai.Client(api_key=api_key)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
        return (response.text or "").strip()
    except Exception:
        return f"Sir, I analyzed your project and made {len(actions)} improvements."


# ─────────────────────────────────────────────────────────────────────────────
# IDE Notification Auto-Accept (UIA-based)
# ─────────────────────────────────────────────────────────────────────────────

_ACCEPT_KEYWORDS = [
    "allow", "accept", "yes", "ok", "confirm", "continue",
    "apply", "enable", "install", "update", "keep",
    "always allow", "trust", "approve",
]

_REJECT_KEYWORDS = [
    "deny", "reject", "cancel", "no", "never", "block",
    "don't allow", "remove", "uninstall",
]


def _try_accept_ide_notifications() -> list[str]:
    """
    Use UIA to find and click 'Allow'/'Accept' buttons in IDE notification popups.
    Returns list of actions taken.
    """
    if not _UIA or _OS != "Windows":
        return []

    accepted = []
    try:
        with _auto.UIAutomationInitializerInThread():
            for _, display_name, _ in _IDE_SIGNATURES:
                try:
                    # Find IDE windows
                    windows = _auto.GetRootControl().GetChildren()
                    for win in windows:
                        win_name = (win.Name or "").lower()
                        if any(ide_frag.replace(".exe", "").lower() in win_name
                               for ide_frag, _, _ in _IDE_SIGNATURES):
                            # Look for notification buttons within this window
                            buttons = win.FindAllControl(
                                _auto.ControlType.ButtonControl,
                                searchDepth=15
                            )
                            for btn in buttons:
                                btn_text = (btn.Name or "").lower()
                                if any(kw in btn_text for kw in _ACCEPT_KEYWORDS):
                                    # Make sure it's not a destructive action
                                    if not any(kw in btn_text for kw in _REJECT_KEYWORDS):
                                        try:
                                            btn.Click()
                                            accepted.append(f"Clicked '{btn.Name}' in {win.Name}")
                                            time.sleep(0.3)
                                        except Exception:
                                            pass
                except Exception:
                    continue
    except Exception as e:
        print(f"[IDEMonitor] UIA notification scan error: {e}")

    return accepted


# ─────────────────────────────────────────────────────────────────────────────
# Main Monitor Loop
# ─────────────────────────────────────────────────────────────────────────────

def _monitor_loop(player, mode: str, preferred_ide: str) -> None:
    global _monitoring

    print(f"[IDEMonitor] ▶ Started (mode={mode})")
    if player:
        try:
            player.write_log("JARVIS: IDE monitor started. Scanning for active IDE...")
        except Exception:
            pass

    _status["start_time"] = time.time()
    _status["actions_done"] = []

    ide_name      = ""
    project_path  = ""
    scan_result: dict = {}
    analysis      = ""
    last_scan_t   = 0.0
    last_notif_t  = 0.0
    last_improve_t = 0.0
    analysis_done = False

    SCAN_INTERVAL    = 30    # re-scan project every 30s
    NOTIF_INTERVAL   = 8     # check for IDE notifications every 8s
    IMPROVE_INTERVAL = 120   # attempt improvement every 2 min

    while not _stop_evt.is_set():
        now = time.time()

        # ── Detect IDE ────────────────────────────────────────────────────────
        detected_ide, _, detected_path = _detect_ide()
        if preferred_ide:
            for frag, dname, _ in _IDE_SIGNATURES:
                if preferred_ide.lower() in dname.lower():
                    if detected_ide and preferred_ide.lower() in detected_ide.lower():
                        break
                    # Keep searching if preferred not found yet
                    break

        if detected_ide and detected_ide != ide_name:
            ide_name = detected_ide
            print(f"[IDEMonitor] 🖥 Detected IDE: {ide_name}")
            _status["ide"] = ide_name
            if player:
                try:
                    player.write_log(f"JARVIS: Detected {ide_name} is open.")
                except Exception:
                    pass

        if detected_path and detected_path != project_path:
            project_path  = detected_path
            analysis_done = False   # re-analyze on project change
            last_scan_t   = 0       # force rescan
            print(f"[IDEMonitor] 📁 Project path: {project_path}")
            _status["project_path"] = project_path
            _status["project_name"] = Path(project_path).name
            if player:
                try:
                    player.write_log(f"JARVIS: Project detected: {Path(project_path).name}")
                except Exception:
                    pass

        # ── Scan project ──────────────────────────────────────────────────────
        if project_path and (now - last_scan_t) > SCAN_INTERVAL:
            last_scan_t = now
            print("[IDEMonitor] 🔍 Scanning project...")
            scan_result = _scan_project(project_path)
            lang = scan_result.get("language", "")
            fw   = scan_result.get("framework", "")
            _status["language"] = f"{lang}{' / ' + fw if fw else ''}"
            print(f"[IDEMonitor] Language: {lang} | Framework: {fw} | Files: {scan_result.get('file_count', 0)}")

            # Initial analysis — once per project
            if not analysis_done and scan_result.get("files"):
                print("[IDEMonitor] 🧠 Analyzing project with Gemini...")
                analysis = _gemini_analyze(scan_result)
                if analysis:
                    analysis_done = True
                    _status["last_action"] = "Analyzed project"
                    _status["actions_done"].append("Analyzed project codebase")
                    if player:
                        try:
                            short = analysis[:200].replace("\n", " ")
                            player.write_log(f"JARVIS: Project analyzed. {short}...")
                        except Exception:
                            pass

        # ── Accept IDE notifications ──────────────────────────────────────────
        if (now - last_notif_t) > NOTIF_INTERVAL:
            last_notif_t = now
            accepted = _try_accept_ide_notifications()
            for action in accepted:
                print(f"[IDEMonitor] ✅ {action}")
                _status["actions_done"].append(action)
                _status["last_action"] = action
                if player:
                    try:
                        player.write_log(f"JARVIS: Auto-accepted: {action}")
                    except Exception:
                        pass

        # ── Autonomous improvement ────────────────────────────────────────────
        if (mode in ("assist", "auto") and
                project_path and
                scan_result.get("files") and
                analysis and
                (now - last_improve_t) > IMPROVE_INTERVAL):

            last_improve_t = now

            if mode == "auto":
                # Find a quick-win file to improve
                _do_improvement(scan_result, analysis, player)
            elif mode == "assist":
                # Write an improvement report as a comment file
                _write_improvement_notes(project_path, analysis, scan_result, player)

        _stop_evt.wait(timeout=5)

    # ── Shutdown: report what was done ────────────────────────────────────────
    print("[IDEMonitor] ■ Stopped.")
    _monitoring = False

    if _status["actions_done"] and player:
        summary = _gemini_summarize_work(_status["actions_done"], scan_result)
        try:
            player.write_log(f"JARVIS: {summary}")
        except Exception:
            pass
        if hasattr(player, "request_say") and callable(player.request_say):
            try:
                player.request_say(summary)
            except Exception:
                pass


def _do_improvement(scan: dict, analysis: str, player) -> None:
    """Auto mode: pick one quick-win and actually fix it."""
    files = scan.get("files", [])
    if not files:
        return

    # Pick the first source file with actual content
    for rel_path, size, snippet in files:
        if size < 100 or not snippet.strip():
            continue

        full_path = Path(scan["root"]) / rel_path
        if not full_path.exists():
            continue

        try:
            original = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        # Ask Gemini for the most impactful single improvement
        issue_prompt = (
            f"Based on this analysis:\n{analysis[:1500]}\n\n"
            f"For file {rel_path}, what is the single most impactful improvement "
            "that can be made safely? Respond in ONE sentence describing only the fix."
        )

        api_key = _load_api_key()
        if not api_key or not _GENAI:
            return

        try:
            client = _genai.Client(api_key=api_key)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=issue_prompt,
                )
            issue = (resp.text or "").strip()
        except Exception:
            return

        if not issue:
            return

        print(f"[IDEMonitor] 🔧 Auto-improving {rel_path}: {issue}")
        improved = _gemini_improve_file(rel_path, original, scan, issue)

        if improved and improved != original:
            # Backup original
            backup = full_path.with_suffix(full_path.suffix + ".jarvis_backup")
            try:
                backup.write_text(original, encoding="utf-8")
                full_path.write_text(improved, encoding="utf-8")
                action = f"Improved {rel_path}: {issue}"
                _status["actions_done"].append(action)
                _status["last_action"] = action
                print(f"[IDEMonitor] ✅ Saved improvement to {rel_path}")
                if player:
                    try:
                        player.write_log(f"JARVIS: ✏️ Auto-improved {rel_path}")
                    except Exception:
                        pass
            except Exception as e:
                print(f"[IDEMonitor] Write error: {e}")
        return  # Only one file per cycle


def _write_improvement_notes(project_path: str, analysis: str, scan: dict, player) -> None:
    """Assist mode: write JARVIS_IMPROVEMENTS.md into the project."""
    report_path = Path(project_path) / "JARVIS_IMPROVEMENTS.md"

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    content = (
        f"# JARVIS Improvement Report\n"
        f"Generated: {timestamp}\n"
        f"Project: {scan.get('language', '')} / {scan.get('framework', '')}\n\n"
        f"{analysis}\n\n"
        f"---\n*Generated autonomously by JARVIS while you were away.*\n"
    )

    try:
        report_path.write_text(content, encoding="utf-8")
        action = f"Wrote improvement report to JARVIS_IMPROVEMENTS.md"
        _status["actions_done"].append(action)
        _status["last_action"] = action
        print(f"[IDEMonitor] 📝 Report written: {report_path}")
        if player:
            try:
                player.write_log("JARVIS: 📝 Wrote JARVIS_IMPROVEMENTS.md to your project.")
            except Exception:
                pass
    except Exception as e:
        print(f"[IDEMonitor] Report write error: {e}")


# ── Plugin entry point ────────────────────────────────────────────────────────

def run(parameters: dict, player=None, session_memory=None) -> str:
    global _monitor_thread, _monitoring

    action    = parameters.get("action", "start").strip().lower()
    preferred = parameters.get("ide", "").strip()
    mode      = parameters.get("mode", "assist").strip().lower()

    if mode not in ("observe", "assist", "auto"):
        mode = "assist"

    # ── Status ────────────────────────────────────────────────────────────────
    if action in ("status", "report", "what"):
        if not _monitoring:
            return "IDE monitor is not currently running, sir."
        elapsed = int(time.time() - _status.get("start_time", time.time()))
        m, s    = divmod(elapsed, 60)
        actions = _status.get("actions_done", [])
        return (
            f"IDE monitor has been running for {m}m {s}s. "
            f"Detected: {_status.get('ide', 'no IDE')} — "
            f"Project: {_status.get('project_name', 'unknown')} "
            f"({_status.get('language', '?')}). "
            f"Actions taken: {len(actions)}. "
            f"Last: {_status.get('last_action', 'scanning')}."
        )

    # ── Stop ─────────────────────────────────────────────────────────────────
    if action in ("stop", "off", "disable"):
        if not _monitoring:
            return "IDE monitor is not running, sir."
        _stop_evt.set()
        _monitoring = False
        if _monitor_thread and _monitor_thread.is_alive():
            _monitor_thread.join(timeout=6)
        if player:
            try:
                player.write_log("JARVIS: IDE monitor stopped.")
            except Exception:
                pass
        done = _status.get("actions_done", [])
        return (
            f"IDE monitor stopped. "
            f"During this session I completed {len(done)} actions on your project."
        )

    # ── Start ─────────────────────────────────────────────────────────────────
    missing = []
    if not _PSUTIL:
        missing.append("psutil")
    if _OS == "Windows" and not _WIN32:
        missing.append("pywin32")
    if not _GENAI:
        missing.append("google-generativeai")

    if missing:
        return (
            f"Cannot start — missing packages: {', '.join(missing)}. "
            f"Run: pip install {' '.join(missing)}"
        )

    if not _load_api_key():
        return "Gemini API key not configured, sir."

    if _monitoring:
        return (
            f"IDE monitor is already running. "
            f"Currently watching {_status.get('ide', 'your IDE')} — "
            f"project: {_status.get('project_name', 'unknown')}."
        )

    _stop_evt.clear()
    _monitoring = True

    _monitor_thread = threading.Thread(
        target=_monitor_loop,
        args=(player, mode, preferred),
        daemon=True,
    )
    _monitor_thread.start()

    ide_str = f" focusing on {preferred}" if preferred else ""
    mode_desc = {
        "observe": "I will analyze silently but not touch any files",
        "assist":  "I will analyze and write improvement notes to JARVIS_IMPROVEMENTS.md",
        "auto":    "I will analyze and automatically fix issues I find",
    }[mode]

    return (
        f"IDE monitor activated{ide_str}, sir. "
        f"{mode_desc}. "
        f"I will detect your open IDE, read the project, "
        f"auto-accept AI suggestions and notifications, "
        f"and improve the code while you are away. "
        f"Say 'stop monitoring IDE' when you return or "
        f"'what are you doing in my code' for a status update."
    )

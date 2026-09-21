"""
ML Workspace Plugin — entry point called by JARVIS plugin loader.

This file is NOT the PLUGIN dict file — the loader needs a top-level
plugins/ml_workspace.py file. This module contains the full logic.
"""
from __future__ import annotations

from . import workspace as _ws
from .planner import parse_nl_to_plan
from .schema import WorkspaceSession


def handle(action: str, parameters: dict, player=None) -> str:
    """
    Main dispatch. Called by the outer plugin.py with the parsed intent.
    """
    def log(msg: str):
        if player:
            try:
                player.write_log(f"JARVIS [ML]: {msg}")
            except Exception:
                pass
        print(f"[MLWorkspace] {msg}")

    # ── Activate ──────────────────────────────────────────────────────────────
    if action == "activate":
        session, msg = _ws.activate()
        log(f"Workspace activated: {session.workspace_id}")
        return msg

    # ── Load dataset ──────────────────────────────────────────────────────────
    if action == "load_dataset":
        file_path = parameters.get("file_path", "").strip()
        if not file_path:
            return ("Please provide the dataset path. "
                    "You can drop a file in JARVIS or type the full path.")
        session, msg = _ws.load_dataset_action(file_path)
        log(f"Dataset loaded: {file_path}")
        return msg

    # ── Status ────────────────────────────────────────────────────────────────
    if action == "status":
        return _ws.status()

    # ── History ───────────────────────────────────────────────────────────────
    if action == "history":
        return _ws.show_history()

    # ── Compare ───────────────────────────────────────────────────────────────
    if action == "compare":
        return _ws.compare_last_two()

    # ── Natural language update (set_* actions) ───────────────────────────────
    if action in ("set_target", "set_task", "set_algorithm",
                  "set_split", "set_metrics", "update"):
        patch = {k: v for k, v in parameters.items()
                 if k not in ("action", "file_path", "instruction") and v}
        session, msg = _ws.update_plan(patch)
        return msg

    # ── Run experiment ────────────────────────────────────────────────────────
    if action in ("run", "train", "execute"):
        # Apply any last-minute patches from parameters
        patch = {k: v for k, v in parameters.items()
                 if k not in ("action", "file_path", "instruction") and v}
        if patch:
            _ws.update_plan(patch)
        log("Running experiment...")
        session, result_str = _ws.run_experiment()
        if session:
            log(f"Experiment {session.experiments_run} complete.")
        return result_str

    # ── NL passthrough (Gemini extracted a free-form instruction) ─────────────
    if action == "nl":
        instruction = parameters.get("instruction", "")
        session = _ws.get_active_session()
        ctx = {}
        if session:
            ctx = {
                "target":    session.target,
                "task":      session.task,
                "algorithm": session.algorithm,
                "split":     session.split,
                "metrics":   session.metrics,
                "has_dataset": bool(session.dataset_path),
            }
        plan_patch = parse_nl_to_plan(instruction, ctx)
        log(f"NL plan patch: {plan_patch}")

        parsed_action = plan_patch.pop("action", None)

        # Apply config updates
        if plan_patch:
            _ws.update_plan(plan_patch)

        # If run was implied, execute
        if parsed_action in ("run", "auto") or (
            session and session.algorithm and session.target
            and "run" in instruction.lower() or "train" in instruction.lower()
        ):
            session, result_str = _ws.run_experiment()
            return result_str

        elif parsed_action == "history":
            return _ws.show_history()
        elif parsed_action == "compare":
            return _ws.compare_last_two()
        elif parsed_action == "status":
            return _ws.status()

        # Otherwise just confirm what was set
        return _ws.status()

    return f"Unknown workspace action: {action}"

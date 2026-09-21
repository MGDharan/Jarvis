"""
Workspace session schema — in-memory state for one ML session.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkspaceSession:
    workspace_id: str          = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str                = "active"          # active | idle | closed

    # Dataset
    dataset_path: str          = ""
    dataset_name: str          = ""
    schema: dict               = field(default_factory=dict)   # from dataset_analyzer

    # Experiment config (conversationally updated)
    target: str                = ""
    features: list[str]        = field(default_factory=list)
    task: str                  = ""                # regression | classification
    algorithm: str             = ""
    split: dict                = field(default_factory=lambda: {
        "train": 0.8, "validation": 0.1, "test": 0.1
    })
    metrics: list[str]         = field(default_factory=list)
    params: dict               = field(default_factory=dict)
    activation: str            = ""
    random_state: int          = 42

    # Last result (for comparison / follow-up questions)
    last_result: dict          = field(default_factory=dict)
    last_experiment_path: str  = ""
    experiments_run: int       = 0

    def to_plan(self) -> dict[str, Any]:
        """Build a structured ML plan from the current session state."""
        return {
            "action":       "train_model",
            "task":         self.task,
            "algorithm":    self.algorithm,
            "target":       self.target,
            "features":     self.features or None,
            "split":        self.split,
            "metrics":      self.metrics,
            "params":       self.params,
            "activation":   self.activation or None,
            "random_state": self.random_state,
            "preprocessing": {"missing_values": "auto",
                               "categorical_encoding": "auto",
                               "scaling": "auto"},
        }

    def apply_patch(self, patch: dict) -> list[str]:
        """
        Apply a partial update from the LLM plan to this session.
        Returns list of what changed (for logging).
        """
        changed = []
        if patch.get("target") and patch["target"] != self.target:
            self.target = patch["target"]; changed.append(f"target → {self.target}")
        if patch.get("task") and patch["task"] != self.task:
            self.task = patch["task"]; changed.append(f"task → {self.task}")
        if patch.get("algorithm") and patch["algorithm"] != self.algorithm:
            self.algorithm = patch["algorithm"]; changed.append(f"algorithm → {self.algorithm}")
        if patch.get("features"):
            self.features = patch["features"]; changed.append(f"features → {self.features}")
        if patch.get("split"):
            self.split = patch["split"]
            sp = self.split
            changed.append(
                f"split → {round(sp.get('train',0)*100)}/"
                f"{round(sp.get('validation',0)*100)}/"
                f"{round(sp.get('test',0)*100)}"
            )
        if patch.get("metrics"):
            self.metrics = patch["metrics"]; changed.append(f"metrics → {self.metrics}")
        if patch.get("activation"):
            self.activation = patch["activation"]; changed.append(f"activation → {self.activation}")
        if patch.get("random_state"):
            self.random_state = int(patch["random_state"])
        if patch.get("params"):
            self.params.update(patch["params"]); changed.append("model parameters updated")
        return changed

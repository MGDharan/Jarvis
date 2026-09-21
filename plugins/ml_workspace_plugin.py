"""
JARVIS ML Workspace Plugin — top-level discovery file.

The plugin loader finds this file and registers the 'ml_workspace' tool.
All logic lives in plugins/ml_workspace/ package.
"""

PLUGIN = {
    "name": "ml_workspace_plugin",
    "description": (
        "Activates and controls the JARVIS Machine Learning Workspace. "
        "Allows the user to perform complete ML experiments through natural language — "
        "no Python coding required. "
        "\n"
        "Trigger phrases:\n"
        "  ACTIVATE: 'activate workspace', 'open ML workspace', 'start machine learning workspace', "
        "'open data science workspace', 'start an ML experiment'\n"
        "  LOAD DATA: 'load dataset', 'upload this CSV', 'analyze this file'\n"
        "  CONFIGURE: 'use XGBoost', 'predict salary', 'train 80 10 10', "
        "'calculate MAE and RMSE', 'use Random Forest'\n"
        "  RUN: 'run the experiment', 'train the model', 'execute'\n"
        "  HISTORY: 'show experiment history', 'compare my last two experiments'\n"
        "  STATUS: 'workspace status', 'what is configured'\n"
        "\n"
        "Do NOT use this tool for general coding questions. "
        "ALWAYS use this tool when the user says 'ML workspace', 'machine learning experiment', "
        "'train a model', 'predict X using Y algorithm'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "What to do: "
                    "'activate' — open workspace, "
                    "'load_dataset' — load a file, "
                    "'update' — set target/algorithm/split/metrics, "
                    "'run' — execute training, "
                    "'history' — show past experiments, "
                    "'compare' — compare last 2 experiments, "
                    "'status' — show current config, "
                    "'nl' — natural language free-form instruction."
                ),
            },
            "instruction": {
                "type": "STRING",
                "description": (
                    "Full natural language instruction from the user "
                    "(for action='nl'). "
                    "Example: 'Use XGBoost, train 80/10/10, calculate MAE and R2'"
                ),
            },
            "file_path": {
                "type": "STRING",
                "description": "Absolute path to dataset file (for action='load_dataset').",
            },
            "target": {
                "type": "STRING",
                "description": "Target column name to predict.",
            },
            "task": {
                "type": "STRING",
                "description": "'regression' or 'classification'.",
            },
            "algorithm": {
                "type": "STRING",
                "description": (
                    "Algorithm name: xgboost, random_forest, linear_regression, "
                    "logistic_regression, extra_trees, gradient_boosting, "
                    "decision_tree, neural_network, svm, knn."
                ),
            },
            "split": {
                "type": "OBJECT",
                "description": (
                    "Train/validation/test split as fractions summing to 1.0. "
                    "Example: {\"train\": 0.8, \"validation\": 0.1, \"test\": 0.1}"
                ),
            },
            "metrics": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": (
                    "List of metrics. Regression: mae, mse, rmse, r2, mape. "
                    "Classification: accuracy, precision, recall, f1, roc_auc."
                ),
            },
            "activation": {
                "type": "STRING",
                "description": "Activation function (neural_network only): relu, tanh, sigmoid.",
            },
            "random_state": {
                "type": "NUMBER",
                "description": "Random seed for reproducibility (default 42).",
            },
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Plugin entry point — delegates to the workspace package."""
    try:
        from plugins.ml_workspace.plugin import handle
    except ImportError as e:
        return f"ML Workspace package import failed: {e}"

    action = (parameters.get("action") or "nl").strip().lower()

    try:
        return handle(action, parameters, player=player)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return f"ML Workspace error: {exc}"

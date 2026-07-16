"""Load quant/ research scripts as importable modules — one canonical loader.

WHY importlib at all: the quant scripts are deliberately named in run order
(`01_stationarity.py`, `02_cointegration.py`, …) and a module name cannot
start with a digit, so a plain `import` is impossible. Both the integrated
orchestrator and the /api/quant/ endpoints need the same trick — this is the
one copy (was duplicated in scripts/run_integrated_demo.py and
portfolio/quant_views.py).

Framework-free, like everything in core/.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

# core/ lives at <root>/week2/core/ — quant/ is a sibling of week2/.
QUANT_DIR = Path(__file__).resolve().parent.parent.parent / "quant"


def load_quant_module(rel_path: str, base: Path | None = None) -> Any:
    """Load `quant/<rel_path>` (e.g. "01_mean_reversion/02_cointegration.py").

    Args:
        rel_path: path relative to the quant/ directory, forward slashes.
        base: override the quant/ directory (tests).

    Returns:
        The executed module object.

    Raises:
        RuntimeError: if the file can't be located or loaded.
    """
    full = (base or QUANT_DIR) / rel_path
    spec = importlib.util.spec_from_file_location(
        rel_path.replace("/", ".").replace(".py", ""), full)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {full}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

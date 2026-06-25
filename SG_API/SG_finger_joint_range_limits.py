"""
Reads the finger_joint_range_limits.csv file to get the per-joint angle limits (rad) for FilterSuspicion finger-range suspicion.

Per-joint angle limits (rad) for FilterSuspicion finger-range suspicion.

Loaded from finger_joint_range_limits.csv (one finger per row, j0–j7 min/max columns).
Finger order: thumb=0, index=1, middle=2, ring=3, pinky=4.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Optional, Tuple

from . import SG_types as SG_T

FingerJointKey = Tuple[int, int]

FINGER_NAMES = ("thumb", "index", "middle", "ring", "pinky")
DEFAULT_LIMITS_CSV = Path(__file__).resolve().parent / "finger_joint_range_limits.csv"

_LIMITS_CACHE: Optional[Dict[FingerJointKey, Tuple[float, float]]] = None
_LIMITS_CACHE_PATH: Optional[Path] = None


def _joint_column_names(joint_idx: int) -> Tuple[str, str]:
    return f"j{joint_idx}_min", f"j{joint_idx}_max"


def load_finger_joint_range_limits(
    csv_path: Optional[Path] = None,
    *,
    reload: bool = False,
) -> Dict[FingerJointKey, Tuple[float, float]]:
    """Load (finger_idx, joint_idx) -> (min_rad, max_rad) from CSV."""
    global _LIMITS_CACHE, _LIMITS_CACHE_PATH

    path = (csv_path if csv_path is not None else DEFAULT_LIMITS_CSV).resolve()
    if not reload and _LIMITS_CACHE is not None and _LIMITS_CACHE_PATH == path:
        return _LIMITS_CACHE

    if not path.is_file():
        raise FileNotFoundError(f"Finger joint range limits CSV not found: {path}")

    limits: Dict[FingerJointKey, Tuple[float, float]] = {}
    name_to_idx = {name: idx for idx, name in enumerate(FINGER_NAMES)}

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "finger" not in reader.fieldnames:
            raise ValueError(f"{path.name}: expected 'finger' column")

        for row in reader:
            finger_name = row["finger"].strip().lower()
            if finger_name not in name_to_idx:
                raise ValueError(f"{path.name}: unknown finger {finger_name!r}")
            finger_idx = name_to_idx[finger_name]

            for joint_idx in range(8):
                min_col, max_col = _joint_column_names(joint_idx)
                if min_col not in row or max_col not in row:
                    continue
                min_raw = row[min_col].strip()
                max_raw = row[max_col].strip()
                if not min_raw or not max_raw:
                    continue
                limits[(finger_idx, joint_idx)] = (float(min_raw), float(max_raw))

    _LIMITS_CACHE = limits
    _LIMITS_CACHE_PATH = path
    return limits


def lookup_joint_range_limits(
    finger_idx: int,
    joint_idx: int,
    hand : SG_T.Hand,
    table: Optional[Dict[FingerJointKey, Tuple[float, float]]] = None,
) -> Tuple[Optional[float], Optional[float]]:
    limits = table if table is not None else load_finger_joint_range_limits()
    entry = limits.get((finger_idx, joint_idx))
    if entry is None:
        return None, None
    min_lim, max_lim = entry
    # Limits are calibrated for a right hand. The left hand mirrors the j0
    # (abduction/splay) axis, so negate and swap min/max for that joint only.
    if hand == SG_T.Hand.LEFT and joint_idx == 0:
        return -max_lim, -min_lim
    return min_lim, max_lim

"""
Pinch configuration dataclass for the Robot_Pinch_Mapper.
"""
from dataclasses import dataclass, field
from typing import Dict, Sequence

@dataclass
class Robot_Pinch_Config:
    """Configuration for pinch detection and mapping"""

    name: str = "DefaultPinchConfig"

    # Format: finger_index: [thumb_abduction, thumb_flexion, finger_flexion]
    robot_pinch_targets: Dict[int, Sequence[float]] = field(default_factory=lambda: {
        1: [5000, 9000, 3000],
        2: [4500, 9000, 3500],
        3: [4000, 9000, 3200],
        4: [3500, 9000, 2800],
    })

    # Minimum thumb abduction to consider pinch
    thumb_abduction_threshold: float = 9000

    distance_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "min_distance":    5,
        "max_distance":   70,
    })

    blend_weights: Dict[str, float] = field(default_factory=lambda: {
        "thumb":    0.4,
        "distance": 0.6,
    })

@dataclass
class Robot_Pinch_State:
    pinch_factor: float = 0.0
    thumb_factor: float = 0.0
    distance_factor: float = 0.0
    active_pinch_finger: int = 1
    pinch_mode_active: bool = False
    min_distance: float = 100.0

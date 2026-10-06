"""
Robot Hand Mapping Module

This module provides mapping between Rembrandt glove data and robot hand,
including pinch detection and smooth transitions between normal and pinch modes.

For use see examples/robot_hand_mapper_pbent.py.

Questions? Written by:
- Akshay Radhamohan M
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/robot_hand_mapper/
Support: https://www.senseglove.com/support/
"""

import os
import numpy as np

from . import SG_types as SG_T
from SG_API.SG_logger import sg_logger
from .SG_robot_pinch_config import Robot_Pinch_Config, Robot_Pinch_State

from typing import Dict, List, Optional, Sequence, Union, Tuple

PRIMARY_PINCH_FINGER = 1
PERCENTAGE_BENT_MAX = 10000
THUMB_ABDUCTION_INFLUENCE_MIN = 0.2

# mm gap between the two closest fingers needed for full closest-finger confidence
FINGER_SWITCH_MARGIN = 5.0

# Per-finger distance bias gain, multiplies the measured min joint distance for that finger before
# ranking fingers by closeness. Compensates for per-finger reach/exo differences (e.g. the pinky,
# which can't physically reach the same abduction as the others)

# TODO: Update will follow when we map the compensation
FINGER_BIAS_GAIN = [1.0, 0.9, 0.9, 0.8]

class Robot_Pinch_Mapper:
    """
    Maps Rembrandt glove data to robot hand control with pinch detection.
    """
    def __init__(self, device_id: Optional[int] = None, config: Optional[Robot_Pinch_Config] = None):
        self.device_id = device_id
        self.config = config or Robot_Pinch_Config()
        self.state = Robot_Pinch_State()
        self._gui = None
        self.primary_pinch_finger = PRIMARY_PINCH_FINGER
        self.finger_switch_margin = FINGER_SWITCH_MARGIN
        self.finger_bias_gain = list(FINGER_BIAS_GAIN)
        self._last_flex: Optional[List[float]] = None
        self._last_abd: Optional[List[float]] = None
        self._last_rpm_result: Optional[Tuple] = None

        # Manual mode: Does not use glove/device input or pinch blending,
        # returns manually-set values instead
        self.manual_mode: bool = False
        self.manual_flex: List[float] = [0.0] * 5
        self.manual_abdn: List[float] = [0.0] * 5

        sg_logger.set_console_level(sg_logger.INFO)

    def register_gui(self, gui):
        """Register a GUI to receive automatic updates."""
        self._gui = gui

    def set_manual_mode(self, enabled: bool):
        """Enable/disable manual mode"""
        self.manual_mode = bool(enabled)

    def set_manual_values(self, flex: SG_T.Sequence[Union[int, float]],
                          abdn: SG_T.Sequence[Union[int, float]]):
        """Set the manual-mode output values."""
        self.manual_flex = [float(v) for v in flex]
        self.manual_abdn = [float(v) for v in abdn]

    def _manual_rpm_result(self) -> Tuple:
        flex = list(self.manual_flex)
        abdn = list(self.manual_abdn)
        result = (flex, abdn)
        self._last_flex = flex
        self._last_abd = abdn
        self._last_rpm_result = result
        return result

    def apply_config(self, config: Robot_Pinch_Config):
        """Apply a new Robot_Pinch_Config instance to this mapper."""
        if not isinstance(config, Robot_Pinch_Config):
            raise TypeError("apply_config() expects a Robot_Pinch_Config instance.")
        try:
            self.config = config
            sg_logger.info(f"Robot_Pinch_Mapper: Applied config '{config.name}'.")
        except Exception as e:
            sg_logger.warn(f"Failed to apply config: {e}")
            raise

    def set_pinch_targets(self, finger_index: int, thumb_abduction: float, thumb_flexion: float, finger_flexion: float):
        """
        Set the pinch target percentages for a specific finger combination.

        Args:
            finger_index: 1=index, 2=middle, 3=ring, 4=pinky
            thumb_abdn: Target robot thumb abduction during pinch
            thumb_flex: Target robot thumb flexion during pinch
            finger_flex: Target flexion for the specified finger during pinch
        """
        try:
            if finger_index not in (1, 2, 3, 4):
                raise ValueError(f"Invalid finger_index {finger_index}. Use 1-4 for index-pinky.")

            self.config.robot_pinch_targets[finger_index] = [
                int(thumb_abduction), int(thumb_flexion), int(finger_flexion),
            ]
            sg_logger.info(f"Pinch target set for finger index {finger_index}")
        except Exception as e:
            sg_logger.warn(f"Failed to set pinch target for finger {finger_index}: {e}")

    def goto_pinch(self, finger_index: int) -> Tuple:
        """
        Load the configured pinch target for finger_index (from the currently loaded
        config's robot_pinch_targets) into the manual-mode output values.
        """
        if finger_index not in (1, 2, 3, 4):
            raise ValueError(f"Invalid finger_index {finger_index}. Use 1-4 for index-pinky.")

        thumb_abdn, thumb_flex, finger_flex = \
            self.config.robot_pinch_targets.get(finger_index, [5000, 9000, 3000])

        self.manual_flex = [0.0] * 5
        self.manual_abdn = [0.0] * 5
        self.manual_abdn[0] = float(thumb_abdn)
        self.manual_flex[0] = float(thumb_flex)
        self.manual_flex[finger_index] = float(finger_flex)

        return self._manual_rpm_result()

    def reset_manual(self) -> Tuple:
        """Reset all manual-mode output values (thumb + all fingers) back to 0."""
        self.manual_flex = [0.0] * 5
        self.manual_abdn = [0.0] * 5
        return self._manual_rpm_result()

    def set_distance_thresholds(self, min_distance: float, max_distance: float):
        """Set distance thresholds for pinch detection (in mm)."""
        try:
            self.config.distance_thresholds["min_distance"]   = float(min_distance)
            self.config.distance_thresholds["max_distance"]   = float(max_distance)
            sg_logger.info(f"Distance thresholds: min={min_distance}, max={max_distance} mm")
        except Exception as e:
            sg_logger.warn(f"Failed to set distance thresholds: {e}")

    def set_blend_weights(self, weight_thumb: float, weight_distance: float):
        """Set the relative weights (each in [0, 1]) used to combine distance/thumb factors."""
        try:
            self.config.blend_weights["thumb"] = float(weight_thumb)
            self.config.blend_weights["distance"] = float(weight_distance)
            sg_logger.info(f"Blend weights: thumb={weight_thumb}, distance={weight_distance}")
        except Exception as e:
            sg_logger.warn(f"Failed to set blend weights: {e}")

    def set_thumb_abduction_threshold(self, threshold: float):
        """Set thumb abduction threshold for pinch detection (percentage bent)."""
        try:
            self.config.thumb_abduction_threshold = int(threshold)
            sg_logger.info(f"Thumb abduction threshold: {self.config.thumb_abduction_threshold}")
        except Exception as e:
            sg_logger.warn(f"Failed to set thumb abduction threshold: {e}")

    def save_config(self, name: str, directory: Optional[str] = None):
        """Save the current pinch configuration to a Python file."""
        if not isinstance(self.config, Robot_Pinch_Config):
            raise TypeError("Mapper configuration is not a valid Robot_Pinch_Config instance.")
        try:
            path = _save_pinch_config(self.config, name, directory)
            sg_logger.info(f"Robot_Pinch_Mapper: Configuration saved as '{name}' in {path}")
        except Exception as e:
            sg_logger.warn(f"Robot_Pinch_Mapper: Failed to save configuration '{name}': {e}")
            raise

    def _smooth_step(self, value: float, min_val: float, max_val: float) -> float:
        """
        Smooth step function that maps input range to 0.0-1.0 with S-curve.

        Args:
            value: Input value
            min_val: Value that maps to 0.0
            max_val: Value that maps to 1.0

        Returns:
            Smoothly interpolated value between 0.0 and 1.0
        """
        if max_val <= min_val:
            return 1.0 if value >= max_val else 0.0

        # Clamp and normalize to 0-1 range
        t = np.clip((value - min_val) / (max_val - min_val), 0.0, 1.0)

        # Apply smooth S-curve (3t^2 - 2t^3)
        return float(t * t * (3.0 - 2.0 * t))

    def _calculate_thumb_abduction_influence(self, normal_abdn: SG_T.Sequence[Union[int, float]]) -> float:
        thumb_abdn = normal_abdn[0]

        # Smooth step function for thumb abduction
        # Maps abduction percentage to 0.0-1.0 influence
        thumb_min = self.config.thumb_abduction_threshold * 0.0  # starting influence
        thumb_max = self.config.thumb_abduction_threshold * 1.0  # Full influence
        thumb_factor = self._smooth_step(thumb_abdn, thumb_min, thumb_max)

        # Thumb Factor Offset (So that the thumb abdn is never "0")
        thumb_factor = THUMB_ABDUCTION_INFLUENCE_MIN + (1.0 - THUMB_ABDUCTION_INFLUENCE_MIN) * thumb_factor
        return thumb_factor

    def _calculate_distance_factor(self, distances: SG_T.Sequence[float], joint_distances: SG_T.Sequence[SG_T.Sequence[float]]) -> Tuple[float, float, int]:
        distances = list(distances)
        joint_distances = list(joint_distances)

        # Per-finger bias gain (compensating for pinky)
        bias_gain = self.finger_bias_gain
        finger_min_distances = [min(d) * bias_gain[i] for i, d in enumerate(joint_distances)]

        # Rank fingers by their minimum distance to the thumb
        ranked_fingers = list(np.argsort(finger_min_distances))
        closest_idx, second_idx = int(ranked_fingers[0]), int(ranked_fingers[1])
        closest_finger = closest_idx + 1
        closest_distance = distances[closest_idx] * bias_gain[closest_idx]

        base_min = self.config.distance_thresholds["min_distance"]
        base_max = self.config.distance_thresholds["max_distance"]

        # Confidence score(0..1) that between two closest fingers
        margin = finger_min_distances[second_idx] - finger_min_distances[closest_idx]
        finger_confidence = self._smooth_step(margin, 0.0, self.finger_switch_margin)

        # Per-finger scaling factor: +10% for each finger after index,
        # Blended smoothly between the two closest fingers by finger_confidence 
        scale_closest = 1.0 + 0.20 * closest_idx
        scale_second  = 1.0 + 0.10 * second_idx
        scale = (1.0 - finger_confidence) * scale_second + finger_confidence * scale_closest

        # Apply scaling
        min_distance = base_min * scale
        max_distance = base_max * scale

        # Compute Distance factor (continuous 0.0 to 1.0)
        # Closer distance = higher influence (invert the smooth step)
        distance_factor = 1.0 - self._smooth_step(closest_distance, min_distance, max_distance)

        return distance_factor, closest_distance, closest_finger

    def _calculate_pinch_factor(self, normal_abdn: SG_T.Sequence[Union[int, float]], distances: SG_T.Sequence[float], joint_distances: SG_T.Sequence[SG_T.Sequence[float]]):
        """
        Calculate continuous pinch influence factor (0.0 to 1.0).

        Returns:
            (pinch_influence, closest_finger_index, thumb_factor, distance_factor)
        """

        thumb_abduction_influence = self._calculate_thumb_abduction_influence(normal_abdn)
        distance_factor, closest_distance, closest_finger = self._calculate_distance_factor(distances, joint_distances)

        # Combined factor
        weights = self.config.blend_weights
        weight_sum = weights["thumb"] + weights["distance"]
        weight_thumb = weights["thumb"] / weight_sum
        weight_distance = weights["distance"] / weight_sum
        pinch_factor = (thumb_abduction_influence**weight_thumb) * (distance_factor**weight_distance)

        pinch_factor = np.clip(pinch_factor, 0.0, 1.0)

        self._update_pinch_state(pinch_factor, closest_distance, closest_finger, thumb_abduction_influence, distance_factor)

    def _update_pinch_state(self, pinch_factor: float, closest_distance: float, closest_finger: int, thumb_factor: float, distance_factor: float):
        """Update internal pinch state using continuous influence"""
        self.state.pinch_factor = pinch_factor
        self.state.thumb_factor = thumb_factor
        self.state.distance_factor = distance_factor
        self.state.active_pinch_finger = closest_finger
        self.state.pinch_mode_active = pinch_factor > 0.1
        self.state.min_distance = closest_distance

    def _get_pinch_targets(self, finger_index: int,
                           normal_flex: SG_T.Sequence[Union[int, float]],
                           normal_abdn: SG_T.Sequence[Union[int, float]]) -> Tuple[List[float], List[float]]:

        # [thumb_abduction, thumb_flexion, finger_flexion]
        thumb_abdn, thumb_flex, finger_flex = \
            self.config.robot_pinch_targets.get(finger_index, [5000, 9000, 3000])

        flex_targets = list(normal_flex)
        abdn_targets = list(normal_abdn)

        # Set the pinch targets for the active finger, leaving others as normal values
        abdn_targets[0] = float(thumb_abdn)
        flex_targets[0] = float(thumb_flex)
        flex_targets[finger_index] = float(finger_flex)

        return flex_targets, abdn_targets

    def compute_rpm_bents(self,
                          normal_flex: SG_T.Sequence[Union[int, float]],
                          normal_abdn: SG_T.Sequence[Union[int, float]],
                          distances: SG_T.Sequence[float],
                          joint_distances: SG_T.Sequence[SG_T.Sequence[float]]) -> Tuple[List[int], List[int]]:
        """
        Data-driven pinch mapping, using the percentage-bent flexion/abduction values directly.

        Args:
            joint_distances: per-finger sequence of thumb-to-joint distances (mm)

        Returns:
            (blended_flex, blended_abdn)
        """
        if self.manual_mode:
            flex, abdn = self._manual_rpm_result()
            result = ([int(v) for v in flex], [int(v) for v in abdn])
            self._last_rpm_result = result
            return result

        # Calculate pinch factor (thumb, distance) and update pinch state
        self._calculate_pinch_factor(normal_abdn, distances, joint_distances)

        self._last_flex = list(normal_flex)
        self._last_abd  = list(normal_abdn)

        pinch = self.state.pinch_factor

        # If not in pinch mode or pinch factor is minimal, return normal values
        if pinch < 0.001:
            result = ([int(v) for v in normal_flex], [int(v) for v in normal_abdn])
            self._last_rpm_result = result
            return result

        # Gets the pinch targets (flex, abd) for the active pinch finger
        # The rest remains the norm flex values
        pinch_flex, pinch_abdn = self._get_pinch_targets(self.state.active_pinch_finger, normal_flex, normal_abdn)

        # Blend between normal and pinch modes for flexion (uses combined thumb + distance influence)
        blended_flex = [int((1 - pinch) * n + pinch * p) for n, p in zip(normal_flex, pinch_flex)]
        blended_abdn = [int((1 - pinch) * n + pinch * p) for n, p in zip(normal_abdn, pinch_abdn)]

        result = (blended_flex, blended_abdn)
        self._last_rpm_result = result
        return result

    def get_manual_bents(self) -> Tuple:
        """Return the current manual-mode values directly."""
        return self._manual_rpm_result()

def _save_pinch_config(config: Robot_Pinch_Config, name: str, directory: Optional[str] = None) -> str:
    """Save Robot_Pinch_Config to a human-readable Python file."""
    root_dir = directory or os.getcwd()
    configs_dir = os.path.join(root_dir, "configs", "robot_hand_mapper")
    os.makedirs(configs_dir, exist_ok=True)

    for pkg_dir in [os.path.join(root_dir, "configs"), configs_dir]:
        init_file = os.path.join(pkg_dir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write("# Auto-generated by Robot_Pinch_Mapper\n")

    path = os.path.join(configs_dir, f"{name}.py")
    class_name = "".join(part.capitalize() for part in name.split("_"))

    def fmt(lst):
        return "[" + ", ".join("None" if v is None else f"{v:.3f}" for v in lst) + "]"

    content = f'''"""
Robot Hand Pinch Configuration
"""

from SG_API.SG_robot_pinch_config import Robot_Pinch_Config

{class_name} = Robot_Pinch_Config(
    name="{class_name}",

    robot_pinch_targets={{
        1: {fmt(config.robot_pinch_targets[1])},  # Pinch Index
        2: {fmt(config.robot_pinch_targets[2])},  # Pinch Middle
        3: {fmt(config.robot_pinch_targets[3])},  # Pinch Ring
        4: {fmt(config.robot_pinch_targets[4])},  # Pinch Pinky
    }},

    thumb_abduction_threshold={config.thumb_abduction_threshold},
    distance_thresholds={{
        "min_distance":   {config.distance_thresholds["min_distance"]},
        "max_distance":   {config.distance_thresholds["max_distance"]},
    }},

    blend_weights={{
        "thumb":      {config.blend_weights["thumb"]},
        "distance":   {config.blend_weights["distance"]},
    }},
)

config = {class_name}
'''
    with open(path, "w") as f:
        f.write(content)
    return path

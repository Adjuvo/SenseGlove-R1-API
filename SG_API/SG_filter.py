"""




Median Filter Module for SenseGlove Rembrandt API.

This module provide filters for the Exo angles jitter.
It contains:
- FilterSuspicion: a custom filter (single number stream), working with suspicion levels to detect if the current frame jitter.
- ExoAnglesFilterSuspicion: for the exo angles data structure, working with suspicion levels to detect if the current frame jitter.
- MedianFilter: a basic single number median filter for smoothing time-series data with configurable window size.
- ExoAnglesMedianFilter: a median filter for the exo angles data structure.

Note: it is currently not optimized for performance, so it tanks FPS if used.

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

import numpy as np
from collections import deque
from typing import List, Union, Optional, Deque, Sequence, Tuple
from dataclasses import dataclass
from . import SG_types as SG_T
from .SG_finger_joint_range_limits import lookup_joint_range_limits


def _median_small(values: Sequence[float]) -> float:
    """Median of a short sequence without numpy allocation overhead."""
    n = len(values)
    if n == 0:
        raise ValueError("median of empty sequence")
    if n == 1:
        return float(values[0])
    if n == 2:
        return (float(values[0]) + float(values[1])) * 0.5
    s = sorted(values)
    return s[n // 2]


@dataclass
class SuspicionChecks:
    """Toggle individual suspicion signals in FilterSuspicion."""
    prediction: bool = True
    slow_filter_check: bool = True
    sibling_joints: bool = True
    finger_range: bool = True
    acceleration: bool = True
    suspicion_hold_on_minimal_change: bool = True
    motion_classifier: bool = True


@dataclass
class FilterSuspicionConfig:
    """Tunable thresholds and buffer sizes for FilterSuspicion."""
    suspicion_threshold: int = 1
    slow_change_threshold: float = 0.4
    prediction_threshold: float = 0.32
    prediction_velocity_frames: int = 3
    min_velocity_samples: int = 3
    acceleration_threshold: float = 0.28
    sibling_isolated_threshold: float = 0.16
    sibling_stable_threshold: float = 0.06
    min_stable_siblings: int = 6
    finger_range_margin_rad: float = 0.05
    suspicion_hold_minimal_change_threshold: float = 0.15
    suspicion_hold_min_entry_level: int = 1
    suspicion_hold_sibling_entry_level: int = 1
    suspicion_hold_max_frames: int = 30
    memory_size: int = 76
    motion_classifier_window: int = 20
    motion_classifier_min_window: int = 10
    motion_classifier_velocity_threshold: float = 0.01
    motion_classifier_max_jump_rad: float = 0.5
    motion_classifier_teleport_ceiling_rad: float = 1.2
    motion_classifier_trend_frames: int = 6
    motion_classifier_monotonic_ratio: float = 0.7
    slow_filter_normal_alpha: float = 0.18
    slow_filter_suspicion_alpha: float = 0.18
    fast_filter_window_size: int = 5

    @property
    def warmup_frames(self) -> int:
        return self.memory_size


@dataclass
class SuspicionSnapshot:
    """Bookmark of suspicion state for duplicate-raw frames."""
    suspicion_level: int = 0
    suspicious_level_slow_filter: int = 0
    suspicious_level_prediction: int = 0
    suspicious_level_sibling_joints: int = 0
    suspicious_level_finger_range: int = 0
    suspicious_level_acceleration: int = 0
    suspicious_level_hold_on_minimal_change: int = 0
    suspicion_hold_only_frame_count: int = 0

    @classmethod
    def capture(cls, filt: "FilterSuspicion") -> "SuspicionSnapshot":
        return cls(
            suspicion_level=filt.suspicion_level,
            suspicious_level_slow_filter=filt.suspicious_level_slow_filter,
            suspicious_level_prediction=filt.suspicious_level_prediction,
            suspicious_level_sibling_joints=filt.suspicious_level_sibling_joints,
            suspicious_level_finger_range=filt.suspicious_level_finger_range,
            suspicious_level_acceleration=filt.suspicious_level_acceleration,
            suspicious_level_hold_on_minimal_change=filt.suspicious_level_hold_on_minimal_change,
            suspicion_hold_only_frame_count=filt.suspicion_hold_only_frame_count,
        )

    def restore(self, filt: "FilterSuspicion") -> None:
        filt.suspicion_level = self.suspicion_level
        filt.suspicious_level_slow_filter = self.suspicious_level_slow_filter
        filt.suspicious_level_prediction = self.suspicious_level_prediction
        filt.suspicious_level_sibling_joints = self.suspicious_level_sibling_joints
        filt.suspicious_level_finger_range = self.suspicious_level_finger_range
        filt.suspicious_level_acceleration = self.suspicious_level_acceleration
        filt.suspicious_level_hold_on_minimal_change = self.suspicious_level_hold_on_minimal_change
        filt.suspicion_hold_only_frame_count = self.suspicion_hold_only_frame_count


# (checks field, FilterSuspicion attr, plot label, plot color)
SUSPICION_COMPONENTS: Tuple[Tuple[str, str, str, str], ...] = (
    ("prediction", "suspicious_level_prediction", "suspicion prediction", "#d35400"),
    ("slow_filter_check", "suspicious_level_slow_filter", "suspicion slow filter", "#16a085"),
    ("sibling_joints", "suspicious_level_sibling_joints", "suspicion sibling joints", "#2980b9"),
    ("finger_range", "suspicious_level_finger_range", "suspicion finger range", "#1abc9c"),
    ("acceleration", "suspicious_level_acceleration", "suspicion acceleration", "#9b59b6"),
    (
        "suspicion_hold_on_minimal_change",
        "suspicious_level_hold_on_minimal_change",
        "suspicion hold minimal change",
        "#8e44ad",
    ),
)


def active_suspicion_components(
    checks: SuspicionChecks,
) -> List[Tuple[str, str, str, str]]:
    return [
        (check_key, attr, label, color)
        for check_key, attr, label, color in SUSPICION_COMPONENTS
        if getattr(checks, check_key)
    ]


class EWMAFilter:
    """
    A Exponentially Weighted Moving Average filter.
    """
    def __init__(self, alpha: float = 0.1):
        self.alpha = alpha
        self.value: Optional[float] = None
    
    def update(self, value: float) -> float:
        if self.value is None:
            self.value = value
        else:
            self.value = self.alpha * value + (1 - self.alpha) * self.value
        return self.value

class MedianFilter:
    """
    A median filter for smoothing time-series data with configurable window size.
    
    The filter maintains a sliding window of the most recent values and returns
    the median of the values in the window. This is effective for removing
    impulse noise while preserving edge information.
    """
    
    def __init__(self, window_size: int = 5):
        """
        Initialize the median filter.
        
        Args:
            window_size (int): Size of the sliding window for median calculation.
                              Must be a positive odd number for best results.
                              Default is 5.
        
        Raises:
            ValueError: If window_size is less than 1.
        """
        if window_size < 1:
            raise ValueError("Window size must be at least 1")
        
        self.window_size = window_size
        self.buffer: Deque[float] = deque(maxlen=window_size)
        self.previous_value: Optional[float] = None
        self.initialized = False
    
    def update(self, value: float) -> float:
        """
        Add a new value to the filter and return the filtered result.
        
        Args:
            value (float): The new input value to be filtered.
        
        Returns:
            float: The median of the current window.
        """
        # Normalize the value to the range [-pi, pi)
        # normalized = ((value + math.pi) % (2 * math.pi)) - math.pi
        # I chose not to so I don't have to deal with the sudden wrap jumps

         # Only append if it's not the same as the last added value
        if self.previous_value is None or self.previous_value != value:
            self.buffer.append(value)
            self.previous_value = value
        
        # Return median of current buffer
        return _median_small(self.buffer)
    
    def reset(self):
        """Clear the filter buffer and reset the filter state."""
        self.buffer.clear()
        self.previous_value = None
        self.initialized = False
    
    def set_window_size(self, window_size: int):
        """
        Change the window size of the filter.
        
        Args:
            window_size (int): New window size. Must be positive.
        
        Raises:
            ValueError: If window_size is less than 1.
        """
        if window_size < 1:
            raise ValueError("Window size must be at least 1")
        
        self.window_size = window_size
        # Create new deque with new max length, preserving existing data
        old_data = list(self.buffer)
        self.buffer = deque(old_data[-window_size:], maxlen=window_size)
    
    def get_window_size(self) -> int:
        """Get the current window size."""
        return self.window_size
    
    def is_ready(self) -> bool:
        """Check if the filter buffer is full and ready for optimal filtering."""
        return len(self.buffer) >= self.window_size


@dataclass
class MedianFilterAngleDebug:
    angle_index: int
    buffer_contents: List[float]
    buffer_length: int
    is_ready: bool
    current_median: Optional[float]


@dataclass
class MedianFingerDebugInfo:
    finger_index: int
    window_size: int
    initialized: bool
    angles: List[MedianFilterAngleDebug]
    error: Optional[str] = None


class ExoAnglesMedianFilter:
    """
    Specialized median filter for exoskeleton angles data structure.
    
    This filter applies median filtering to the nested structure of exo_angles_rad:
    - Outer array: 5 fingers (thumb to pinky)
    - Inner array: 8 angles per finger (proximal to distal)
    """
    
    def __init__(self, window_size: int = 3):
        """
        Initialize the exoskeleton angles median filter.
        
        Args:
            window_size (int): Size of the sliding window for median calculation.
                              Default is 5.
        """
        self.window_size = window_size
        self.filters: List[List[MedianFilter]] = []
        self.initialized = False
    
    def _initialize_filters(self, exo_angles: SG_T.Sequence[Sequence[Union[int, float]]]):
        """
        Initialize the filter structure based on the input data structure.
        
        Args:
            exo_angles: The exoskeleton angles data structure to match.
        """
        self.filters = []
        for finger_idx, finger_angles in enumerate(exo_angles):
            finger_filters = []
            for angle_idx in range(len(finger_angles)):
                finger_filters.append(MedianFilter(self.window_size))
            self.filters.append(finger_filters)
        self.initialized = True
    
    def update(self, exo_angles: SG_T.Sequence[Sequence[Union[int, float]]]) -> SG_T.Sequence[Sequence[Union[int, float]]]:
        """
        Apply median filtering to the exoskeleton angles data.
        
        Args:
            exo_angles: Input exoskeleton angles data structure.
                       Format: [finger_nr][angle_nr] where finger_nr is 0-4 (thumb to pinky)
                       and angle_nr is 0-7 (proximal to distal).
        
        Returns:
            SG_T.Sequence[Sequence[Union[int, float]]]: Filtered exoskeleton angles with the same structure.
        """
        if not self.initialized:
            self._initialize_filters(exo_angles)
        
        # Apply median filter to each angle
        filtered_angles = []
        for finger_idx, finger_angles in enumerate(exo_angles):
            filtered_finger = []
            for angle_idx, angle_value in enumerate(finger_angles):
                # Ensure we have the right number of filters for this finger
                if finger_idx < len(self.filters) and angle_idx < len(self.filters[finger_idx]):
                    filtered_value = self.filters[finger_idx][angle_idx].update(float(angle_value))
                    filtered_finger.append(filtered_value)
                else:
                    # Fallback: if filter structure doesn't match, pass through unfiltered
                    filtered_finger.append(float(angle_value))
            filtered_angles.append(filtered_finger)
        
        return filtered_angles
    
    def reset(self):
        """Reset all filters and clear their buffers."""
        for finger_filters in self.filters:
            for angle_filter in finger_filters:
                angle_filter.reset()
        self.initialized = False
    
    def set_window_size(self, window_size: int):
        """
        Change the window size for all filters.
        
        Args:
            window_size (int): New window size. Must be positive.
        """
        self.window_size = window_size
        for finger_filters in self.filters:
            for angle_filter in finger_filters:
                angle_filter.set_window_size(window_size)
    
    def get_window_size(self) -> int:
        """Get the current window size."""
        return self.window_size
    
    def are_filters_ready(self) -> bool:
        """Check if all filters have full buffers and are ready for optimal filtering."""
        if not self.initialized:
            return False
        
        for finger_filters in self.filters:
            for angle_filter in finger_filters:
                if not angle_filter.is_ready():
                    return False
        return True
    
    def get_debug_info(self, finger_idx: int = 0) -> MedianFingerDebugInfo:
        """
        Get debugging information for a specific finger's filters.
        
        Args:
            finger_idx (int): Index of finger to debug (0=thumb, 1=index, etc.)
        """
        if not self.initialized or finger_idx >= len(self.filters):
            return MedianFingerDebugInfo(
                finger_index=finger_idx,
                window_size=self.window_size,
                initialized=self.initialized,
                angles=[],
                error="Filter not initialized or invalid finger index",
            )

        angles: List[MedianFilterAngleDebug] = []
        for angle_idx, angle_filter in enumerate(self.filters[finger_idx]):
            angles.append(
                MedianFilterAngleDebug(
                    angle_index=angle_idx,
                    buffer_contents=list(angle_filter.buffer),
                    buffer_length=len(angle_filter.buffer),
                    is_ready=angle_filter.is_ready(),
                    current_median=(
                        _median_small(angle_filter.buffer)
                        if len(angle_filter.buffer) > 0
                        else None
                    ),
                )
            )

        return MedianFingerDebugInfo(
            finger_index=finger_idx,
            window_size=self.window_size,
            initialized=self.initialized,
            angles=angles,
        )
    
    def print_debug_info(self, finger_idx: int = 0, angle_indices: Optional[List[int]] = None):
        """
        Print debugging information for a specific finger.
        
        Args:
            finger_idx (int): Index of finger to debug (0=thumb, 1=index, etc.)
            angle_indices (List[int], optional): Specific angle indices to print. If None, prints all.
        """
        debug_info = self.get_debug_info(finger_idx)

        if debug_info.error is not None:
            print(f"Debug Error: {debug_info.error}")
            return

        finger_names = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
        finger_name = finger_names[finger_idx] if finger_idx < len(finger_names) else f"Finger_{finger_idx}"

        angles_to_show = angle_indices if angle_indices is not None else range(len(debug_info.angles))

        for angle_idx in angles_to_show:
            if angle_idx < len(debug_info.angles):
                angle_info = debug_info.angles[angle_idx]
                buffer_str = [f"{x:.3f}" for x in angle_info.buffer_contents]
                median_str = (
                    f"{angle_info.current_median:.3f}"
                    if angle_info.current_median is not None
                    else "None"
                )
                print(f"{finger_name}[{angle_idx}] Buffer: {buffer_str} -> Median: {median_str}")
    
    def print_debug_info_verbose(self, finger_idx: int = 0, angle_indices: Optional[List[int]] = None):
        """
        Print detailed debugging information for a specific finger (original verbose version).
        
        Args:
            finger_idx (int): Index of finger to debug (0=thumb, 1=index, etc.)
            angle_indices (List[int], optional): Specific angle indices to print. If None, prints all.
        """
        debug_info = self.get_debug_info(finger_idx)

        if debug_info.error is not None:
            print(f"Debug Error: {debug_info.error}")
            return

        finger_names = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
        finger_name = finger_names[finger_idx] if finger_idx < len(finger_names) else f"Finger_{finger_idx}"

        print(f"\n=== Median Filter Debug Info for {finger_name} ===")
        print(f"Window Size: {debug_info.window_size}")
        print(f"Filter Initialized: {debug_info.initialized}")

        angles_to_show = angle_indices if angle_indices is not None else range(len(debug_info.angles))

        for angle_idx in angles_to_show:
            if angle_idx < len(debug_info.angles):
                angle_info = debug_info.angles[angle_idx]
                print(f"\nAngle {angle_idx}:")
                print(f"  Buffer: {angle_info.buffer_contents}")
                print(f"  Length: {angle_info.buffer_length}/{self.window_size}")
                print(f"  Ready: {angle_info.is_ready}")
                print(f"  Current Median: {angle_info.current_median}")
        print("=" * 50)



class FilterSuspicion:
    """
    Per-joint suspicion filter: trusted raw samples go into correct_buffer;
    jitter-like frames are rejected and output stays at correct_buffer[-1].

    final_smoothing_EWMA: If 0, no final smoothing is applied. If > 0, the final smoothing is applied using the EWMA filter. 
    The higher the number (0 to 1), the more responsive. The closer to 0, the more smooth and more delayed.
    """

    def __init__(
        self,
        final_smoothing_EWMA: float = 0.25,
        checks: Optional[SuspicionChecks] = None,
        config: Optional[FilterSuspicionConfig] = None,
    ):
        self.final_smoothing_EWMA = final_smoothing_EWMA
        self.checks = checks if checks is not None else SuspicionChecks()
        self.config = config if config is not None else FilterSuspicionConfig()
        c = self.config
        self.suspicion_threshold = c.suspicion_threshold
        self.slow_change_threshold = c.slow_change_threshold
        self.prediction_threshold = c.prediction_threshold
        self.prediction_velocity_frames = c.prediction_velocity_frames
        self.min_velocity_samples = c.min_velocity_samples
        self.acceleration_threshold = c.acceleration_threshold
        self.sibling_isolated_threshold = c.sibling_isolated_threshold
        self.sibling_stable_threshold = c.sibling_stable_threshold
        self.min_stable_siblings = c.min_stable_siblings
        self.finger_range_margin_rad = c.finger_range_margin_rad
        self.suspicion_hold_minimal_change_threshold = c.suspicion_hold_minimal_change_threshold
        self.suspicion_hold_min_entry_level = c.suspicion_hold_min_entry_level
        self.suspicion_hold_sibling_entry_level = c.suspicion_hold_sibling_entry_level
        self.suspicion_hold_max_frames = c.suspicion_hold_max_frames
        self.memory_size = c.memory_size
        self.motion_classifier_window = c.motion_classifier_window
        self.motion_classifier_min_window = c.motion_classifier_min_window
        self.motion_classifier_velocity_threshold = c.motion_classifier_velocity_threshold
        self.motion_classifier_max_jump_rad = c.motion_classifier_max_jump_rad
        self.motion_classifier_teleport_ceiling_rad = c.motion_classifier_teleport_ceiling_rad
        self.motion_classifier_trend_frames = c.motion_classifier_trend_frames
        self.motion_classifier_monotonic_ratio = c.motion_classifier_monotonic_ratio
        self.warmup_frames = c.warmup_frames
        self.slow_filter_normal_alpha = c.slow_filter_normal_alpha
        self.slow_filter_suspicion_alpha = c.slow_filter_suspicion_alpha

        self.suspicion_level = 0
        self.suspicious_level_slow_filter = 0
        self.suspicious_level_prediction = 0
        self.suspicious_level_sibling_joints = 0
        self.suspicious_level_finger_range = 0
        self.suspicious_level_acceleration = 0
        self.suspicious_level_hold_on_minimal_change = 0
        self.debug_wrongly_suspected = False

        self.angle_min_limit: Optional[float] = None
        self.angle_max_limit: Optional[float] = None

        self.time_since_suspicious_value = 0
        self.time_since_correct_val = 0
        self.update_count = 0
        self.previous_value: Optional[float] = None

        self.correct_buffer = None
        self.suspicious_buffer = None

        self.is_suspicious = False
        self.first_suspicious_raw_value: Optional[float] = None
        self.suspicion_level_at_entry: Optional[int] = None
        self.suspicion_hold_sibling_qualifies = False
        self.suspicion_hold_only_frame_count = 0
        self._suspicion_snapshot: Optional[SuspicionSnapshot] = None

        self.slow_filter = EWMAFilter(alpha=self.slow_filter_normal_alpha)
        self.final_EWMA_filter = EWMAFilter(alpha=self.final_smoothing_EWMA) # Is applied after filtering to smooth out the sudden jumps
        self.fast_filter = MedianFilter(window_size=self.config.fast_filter_window_size)
        self.raw_history: Deque[float] = deque(
            maxlen=max(self.prediction_velocity_frames, self.motion_classifier_window + 1)
        )

    def _predict_from_velocity(self) -> Optional[float]:
        """Extrapolate next value from median velocity over recent raw samples."""
        hist = list(self.raw_history)[-self.prediction_velocity_frames:]
        n = len(hist)
        if n < self.min_velocity_samples:
            return None
        if n == 2:
            velocity = hist[1] - hist[0]
        else:
            deltas = [hist[i] - hist[i - 1] for i in range(1, n)]
            velocity = _median_small(deltas)
        return hist[-1] + velocity

    def _record_raw_sample(self, value: float) -> None:
        self.raw_history.append(value)

    def _acceleration_from_value(self, value: float) -> Optional[float]:
        """Change in velocity between the last two frames (needs two prior raw samples)."""
        if len(self.raw_history) < 2:
            return None
        current_velocity = value - self.raw_history[-1]
        previous_velocity = self.raw_history[-1] - self.raw_history[-2]
        return current_velocity - previous_velocity

    def _is_motion_continuation(self, value: float) -> bool:
        """Classifier (not a suspicion signal): is this excursion a continuation of
        established motion (genuine) rather than a jump from rest (jitter)?

        Compares the jump direction against the average velocity of the trusted
        history (correct_buffer). The trusted buffer excludes rejected frames, so
        it is not poisoned by the excursion itself.
        """
        if self.correct_buffer is None:
            return False
        n = len(self.correct_buffer)
        w = min(self.motion_classifier_window, n - 1)
        if w < self.motion_classifier_min_window:
            return False
        baseline = self.correct_buffer[-1]
        avg_velocity = (baseline - self.correct_buffer[-1 - w]) / w
        if abs(avg_velocity) < self.motion_classifier_velocity_threshold:
            return False
        jump = value - baseline
        if jump * avg_velocity <= 0:
            return False
        # Genuine motion is monotonic; a jitter staircase bounces (down/up/down)
        # while riding on top of a real prior trend. Reject when the recent raw
        # path is incoherent (net displacement small vs total path travelled).
        if not self._recent_motion_is_coherent(value):
            return False
        # Small jumps consistent with established motion: accept immediately.
        if abs(jump) <= self.motion_classifier_max_jump_rad:
            return True
        # Jumps far beyond a plausible single-frame move are teleports (jitter),
        # never genuine motion — reject regardless of what follows.
        if abs(jump) > self.motion_classifier_teleport_ceiling_rad:
            return False
        # Gray zone (fast genuine move vs jitter look identical on the jump frame).
        # The filter is already holding, so use that hold as hindsight: only release
        # once the rejected samples keep progressing in the motion direction
        # (genuine momentum), not revert or sit flat at a teleported level.
        return self._excursion_is_progressing(value, baseline, avg_velocity)

    def _recent_motion_is_coherent(self, value: float) -> bool:
        """Net displacement vs total path over the window (~1 smooth, low if bouncing)."""
        seq = list(self.raw_history)[-self.motion_classifier_window:]
        if len(seq) < self.motion_classifier_min_window:
            return True
        seq.append(value)
        total = sum(abs(seq[i] - seq[i - 1]) for i in range(1, len(seq)))
        if total < 1e-9:
            return True
        net = abs(seq[-1] - seq[0])
        return (net / total) >= self.motion_classifier_monotonic_ratio

    def _excursion_is_progressing(self, value: float, baseline: float, avg_velocity: float) -> bool:
        """Have the held excursion samples kept moving in the motion direction?

        Only the current episode counts: time_since_correct_val is the number of
        suspicious samples appended this episode, so requiring >= k-1 of them
        guarantees the window is built purely from current-excursion samples (the
        suspicious_buffer is not cleared between episodes and would otherwise be
        polluted by stale values from an earlier episode).
        """
        buf = self.suspicious_buffer
        k = self.motion_classifier_trend_frames
        if buf is None or self.time_since_correct_val < k - 1:
            return False
        recent = list(buf)[-(k - 1):]
        recent.append(value)
        direction = 1.0 if avg_velocity > 0 else -1.0
        # All recent samples on the motion side of the baseline.
        if any((s - baseline) * direction <= 0 for s in recent):
            return False
        # Still progressing away from baseline at >= the established velocity
        # (a teleport-and-hold plateau stays flat and fails this).
        progress = (recent[-1] - recent[0]) * direction
        return progress >= self.motion_classifier_velocity_threshold * (k - 1)

    def _append_to_correct_buffer(self, value: float) -> None:
        if self.correct_buffer is None:
            self.correct_buffer = deque()
        if len(self.correct_buffer) < self.memory_size:
            self.correct_buffer.append(value)
        else:
            self.correct_buffer.popleft()
            self.correct_buffer.append(value)

    def _reseed_slow_filter_from_correct_buffer(self) -> None:
        """Replay raw correct-buffer history through EWMA with slow alpha (on suspicion entry)."""
        self.slow_filter.alpha = self.slow_filter_suspicion_alpha
        self.slow_filter.value = None
        if self.correct_buffer is None:
            return
        for raw_value in self.correct_buffer:
            self.slow_filter.update(float(raw_value))

    def _check_slow_filter_suspicion(self, value: float) -> None:
        slow = self.slow_filter.value
        if slow is not None and abs(slow - value) > self.slow_change_threshold:
            self.suspicion_level += 1
            self.suspicious_level_slow_filter += 1
        # Keep the EWMA tracking the signal during suspicion so a sustained value
        # is eventually trusted again (recovery from a wrongly-held joint). Skip
        # physically impossible values so out-of-range jitter never corrupts it.
        if not self._is_out_of_exo_range(value):
            self.slow_filter.update(value)


    def _warmup_update(self, value: float) -> float:
        self.fast_filter.update(value)
        self._record_raw_sample(value)
        if self._evaluate_finger_range_suspicion(value):
            self.suspicious_level_finger_range = 1
            if self.correct_buffer is not None and len(self.correct_buffer) > 0:
                return self.correct_buffer[-1]
            return value
        self.suspicious_level_finger_range = 0
        self._append_to_correct_buffer(value)
        return self.correct_buffer[-1]

    def _reset_suspicion_components(self) -> None:
        self.suspicion_level = 0
        self.suspicious_level_slow_filter = 0
        self.suspicious_level_prediction = 0
        self.suspicious_level_sibling_joints = 0
        self.suspicious_level_finger_range = 0
        self.suspicious_level_acceleration = 0
        self.suspicious_level_hold_on_minimal_change = 0

    def _save_suspicion_snapshot(self) -> None:
        self._suspicion_snapshot = SuspicionSnapshot.capture(self)

    def _restore_suspicion_snapshot(self) -> None:
        if self._suspicion_snapshot is not None:
            self._suspicion_snapshot.restore(self)

    def _required_hold_entry_level(self) -> int:
        if self.suspicion_hold_sibling_qualifies:
            return self.suspicion_hold_sibling_entry_level
        return self.suspicion_hold_min_entry_level

    def _hold_entry_qualifies(self) -> bool:
        return (
            self.suspicion_level_at_entry is not None
            and self.suspicion_level_at_entry >= self._required_hold_entry_level()
        )

    def _snapshot_has_active_checks(self, snap: SuspicionSnapshot) -> bool:
        return (
            snap.suspicious_level_prediction > 0
            or snap.suspicious_level_sibling_joints > 0
            or snap.suspicious_level_finger_range > 0
            or snap.suspicious_level_acceleration > 0
            or snap.suspicious_level_slow_filter > 0
        )

    def _apply_hold_tick_on_duplicate(self, value: float) -> None:
        """On repeated raw while suspicious: only advance hold-only frame budget."""
        if not self.checks.suspicion_hold_on_minimal_change:
            return
        snap = self._suspicion_snapshot
        if snap is None or self.first_suspicious_raw_value is None:
            return
        if not self._hold_entry_qualifies():
            return
        if abs(value - self.first_suspicious_raw_value) > self.suspicion_hold_minimal_change_threshold:
            return
        if self._snapshot_has_active_checks(snap):
            return

        self.suspicion_hold_only_frame_count = snap.suspicion_hold_only_frame_count + 1
        if self.suspicion_hold_only_frame_count > self.suspicion_hold_max_frames:
            self._reset_suspicion_components()
            self.suspicion_hold_only_frame_count = 0
            return

        self.suspicion_level = self.suspicion_threshold
        self.suspicious_level_hold_on_minimal_change = 1

    def _update_suspicious_duplicate(self, value: float) -> float:
        """Repeated raw while suspicious: keep prior suspicion level; only tick hold budget."""
        self._restore_suspicion_snapshot()
        self._apply_hold_tick_on_duplicate(value)

        if self.suspicion_level >= self.suspicion_threshold:
            self.add_value_to_suspicious_buffer(value)
            self._save_suspicion_snapshot()
        else:
            self.add_value_to_correct_buffer(value)
            self._suspicion_snapshot = None

        self._record_raw_sample(value)

        if self.is_suspicious and self.time_since_correct_val > self.memory_size - 1:
            if not self._should_skip_wrongly_suspected_reset(value):
                self.wrongly_suspected_reset()
            self._suspicion_snapshot = None

        if self.correct_buffer is None:
            return value
        return self.correct_buffer[-1]

    def _apply_suspicion_hold_on_minimal_change(self, value: float, was_suspicious: bool) -> None:
        """Keep suspicion active while raw stays near the first value that triggered it."""
        if not self.checks.suspicion_hold_on_minimal_change:
            return
        if not was_suspicious or self.first_suspicious_raw_value is None:
            return
        if not self._hold_entry_qualifies():
            return
        if self.suspicion_level >= self.suspicion_threshold:
            self.suspicion_hold_only_frame_count = 0
            return
        if abs(value - self.first_suspicious_raw_value) <= self.suspicion_hold_minimal_change_threshold:
            if self.suspicion_hold_only_frame_count >= self.suspicion_hold_max_frames:
                return
            self.suspicion_level = self.suspicion_threshold
            self.suspicious_level_hold_on_minimal_change = 1
            self.suspicion_hold_only_frame_count += 1
        else:
            self.suspicion_hold_only_frame_count = 0

    def _evaluate_suspicion(
        self,
        value: float,
        last_raw: Optional[float],
        finger_raw: Optional[Sequence[float]] = None,
        finger_prev: Optional[Sequence[float]] = None,
        joint_idx: Optional[int] = None,
        was_suspicious: bool = False,
    ) -> None:
        self._reset_suspicion_components()

        predicted = self._predict_from_velocity()

        if self.checks.prediction and predicted is not None:
            if abs(value - predicted) > self.prediction_threshold:
                self.suspicion_level += 1
                self.suspicious_level_prediction += 1

        if self.checks.slow_filter_check and was_suspicious:
            self._check_slow_filter_suspicion(value)

        if self.checks.acceleration:
            acceleration = self._acceleration_from_value(value)
            if acceleration is not None and abs(acceleration) > self.acceleration_threshold:
                self.suspicion_level += 1
                self.suspicious_level_acceleration += 1

    def _evaluate_sibling_joints_suspicion(
        self,
        value: float,
        last_raw: Optional[float],
        finger_raw: Optional[Sequence[float]],
        finger_prev: Optional[Sequence[float]],
        joint_idx: Optional[int],
    ) -> bool:
        """Isolated joint spike while siblings stay stable."""
        if not self.checks.sibling_joints:
            return False
        if (
            last_raw is None
            or finger_raw is None
            or finger_prev is None
            or joint_idx is None
            or len(finger_raw) != len(finger_prev)
        ):
            return False
        if abs(value - last_raw) <= self.sibling_isolated_threshold:
            return False

        stable_siblings = 0
        for k, (cur, prev) in enumerate(zip(finger_raw, finger_prev)):
            if k == joint_idx:
                continue
            if abs(cur - prev) <= self.sibling_stable_threshold:
                stable_siblings += 1
        return stable_siblings >= self.min_stable_siblings

    def _is_out_of_exo_range(self, value: float) -> bool:
        """True if the raw angle is physically impossible for the exo (outside calibrated min/max + margin)."""
        if self.angle_min_limit is None or self.angle_max_limit is None:
            return False
        margin = self.finger_range_margin_rad
        return (
            value < self.angle_min_limit - margin
            or value > self.angle_max_limit + margin
        )

    def _evaluate_finger_range_suspicion(self, value: float) -> bool:
        """Raw angle outside calibrated joint min/max (with margin)."""
        if not self.checks.finger_range:
            return False
        return self._is_out_of_exo_range(value)

    def _should_skip_wrongly_suspected_reset(self, value: Optional[float] = None) -> bool:
        """Finger-range violations are not false holds — never merge them back as trusted."""
        if not self.checks.finger_range:
            return False
        if value is not None and self._evaluate_finger_range_suspicion(value):
            return True
        if (
            self.first_suspicious_raw_value is not None
            and self._evaluate_finger_range_suspicion(self.first_suspicious_raw_value)
        ):
            return True
        if self.suspicious_buffer is not None:
            for sample in self.suspicious_buffer:
                if self._evaluate_finger_range_suspicion(float(sample)):
                    return True
        return False

    def _apply_sibling_suspicion_pass(
        self,
        value: float,
        last_raw: Optional[float],
        finger_raw: Optional[Sequence[float]],
        finger_prev: Optional[Sequence[float]],
        joint_idx: Optional[int],
    ) -> None:
        """Sibling check runs last; when it fires, always meet suspicion threshold."""
        if not self._evaluate_sibling_joints_suspicion(
            value, last_raw, finger_raw, finger_prev, joint_idx
        ):
            return
        self.suspicious_level_sibling_joints = 1
        self.suspicion_hold_sibling_qualifies = True
        if self.suspicion_level < self.suspicion_threshold:
            self.suspicion_level = self.suspicion_threshold

    def _apply_finger_range_suspicion_pass(self, value: float) -> None:
        """Finger-range check runs last; when it fires, same threshold/hold as sibling."""
        if not self._evaluate_finger_range_suspicion(value):
            return
        self.suspicious_level_finger_range = 1
        self.suspicion_hold_sibling_qualifies = True
        if self.suspicion_level < self.suspicion_threshold:
            self.suspicion_level = self.suspicion_threshold

    def _record_suspicion_entry_level(self) -> None:
        self.suspicion_level_at_entry = self.suspicion_level
        if self.suspicious_level_sibling_joints > 0 or self.suspicious_level_finger_range > 0:
            self.suspicion_hold_sibling_qualifies = True

    def _update_suspicious(
        self,
        value: float,
        finger_raw: Optional[Sequence[float]] = None,
        finger_prev: Optional[Sequence[float]] = None,
        joint_idx: Optional[int] = None,
        other_joint_values: Optional[Sequence[float]] = None,
        other_joint_previous: Optional[Sequence[float]] = None,
    ) -> float:
        

        self.update_count += 1
        in_warmup = self.update_count <= self.warmup_frames

        # Repeated raw: skip re-evaluation; while suspicious, keep prior suspicion level.
        if self.previous_value is not None and value == self.previous_value and not in_warmup:
            if self.is_suspicious:
                return self._update_suspicious_duplicate(value)
            if self.correct_buffer is not None and len(self.correct_buffer) > 0:
                return self.correct_buffer[-1]
            return value

        if in_warmup:
            self.previous_value = value
            return self._warmup_update(value)

        last_raw = self.previous_value
        self.previous_value = value

        if finger_raw is None and other_joint_values is not None:
            finger_raw = other_joint_values
            finger_prev = other_joint_previous

        was_suspicious = self.is_suspicious
        self._evaluate_suspicion(
            value, last_raw, finger_raw, finger_prev, joint_idx, was_suspicious=was_suspicious
        )
        self._apply_suspicion_hold_on_minimal_change(value, was_suspicious)
        self._apply_sibling_suspicion_pass(
            value, last_raw, finger_raw, finger_prev, joint_idx
        )
        self._apply_finger_range_suspicion_pass(value)

        would_hold = self.suspicion_level >= self.suspicion_threshold
        if would_hold and self.checks.motion_classifier and self._is_motion_continuation(value):
            would_hold = False

        if would_hold:
            if not was_suspicious:
                self._reseed_slow_filter_from_correct_buffer()
                if self.checks.slow_filter_check:
                    self._check_slow_filter_suspicion(value)
            self.add_value_to_suspicious_buffer(value)
        else:
            self.add_value_to_correct_buffer(value)

        self._record_raw_sample(value)


        if self.is_suspicious:
            # reset if suspicous for too long
            if self.time_since_correct_val > self.memory_size - 1:
                if not self._should_skip_wrongly_suspected_reset(value): #for example if impossible angle, it can't be wrongly suspected
                    self.wrongly_suspected_reset()
                self._suspicion_snapshot = None
            else:
                self._save_suspicion_snapshot()
        else:
            self._suspicion_snapshot = None

        if self.correct_buffer is None:
            return value


        return self.correct_buffer[-1]



    def update(
        self,
        value: float,
        finger_raw: Optional[Sequence[float]] = None,
        finger_prev: Optional[Sequence[float]] = None,
        joint_idx: Optional[int] = None,
        other_joint_values: Optional[Sequence[float]] = None,
        other_joint_previous: Optional[Sequence[float]] = None,
    ) -> float:

        suspicious_filter_value = self._update_suspicious(value, finger_raw, finger_prev, joint_idx, other_joint_values, other_joint_previous)

        if self.final_smoothing_EWMA > 0:
            result = self.final_EWMA_filter.update(suspicious_filter_value)
            return result
        else:
            return suspicious_filter_value

    
    def add_value_to_suspicious_buffer(self, value: float):
        self.is_suspicious = True
        if self.first_suspicious_raw_value is None:
            self.first_suspicious_raw_value = value
            self._record_suspicion_entry_level()
        if self.suspicious_buffer is None:
            self.suspicious_buffer = deque(maxlen=self.memory_size)
        self.suspicious_buffer.append(value)
        self.time_since_suspicious_value = 0
        self.time_since_correct_val += 1
    
    def add_value_to_correct_buffer(self, value: float):
        self.is_suspicious = False
        self.first_suspicious_raw_value = None
        self.suspicion_level_at_entry = None
        self.suspicion_hold_sibling_qualifies = False
        self.suspicion_hold_only_frame_count = 0
        self._suspicion_snapshot = None
        self.slow_filter.value = None
        self.slow_filter.alpha = self.slow_filter_normal_alpha
        self._append_to_correct_buffer(value)
        self.time_since_correct_val = 0
        self.time_since_suspicious_value += 1

    def wrongly_suspected_reset(self):
        self.is_suspicious = False
        self.first_suspicious_raw_value = None
        self.suspicion_level_at_entry = None
        self.suspicion_hold_sibling_qualifies = False
        self.suspicion_hold_only_frame_count = 0
        self._suspicion_snapshot = None
        self.slow_filter.value = None
        self.slow_filter.alpha = self.slow_filter_normal_alpha
        self._reset_suspicion_components()
        if self.suspicious_buffer is not None and len(self.suspicious_buffer) > 0:
            self.correct_buffer = self.suspicious_buffer
        self.suspicious_buffer = None
        self.time_since_correct_val = 0
        self.time_since_suspicious_value = 0
        if self.debug_wrongly_suspected:
            print("Wrongly suspected")


class ExoAnglesFilterSuspicion:
    """
    Applies FilterSuspicion to each joint, passing sibling joint context on the same finger.

    
    final_smoothing_EWMA: If 0, no final smoothing is applied. If > 0, the final smoothing is applied using the EWMA filter. 
    The higher the number (0 to 1), the more responsive. The closer to 0, the more smooth and more delayed.
    """

    def __init__(self, hand: SG_T.Hand, final_smoothing_EWMA: float = 0.25, checks: Optional[SuspicionChecks] = None):
        self.final_smoothing_EWMA = final_smoothing_EWMA
        self.checks = checks if checks is not None else SuspicionChecks()
        self.hand = hand
        self.filters: List[List[FilterSuspicion]] = []
        self.initialized = False
        self._prev_finger_raw: Optional[List[List[float]]] = None
        self._finger_scratch: List[List[float]] = []
        self._finger_out: List[List[float]] = []

    def _initialize_filters(self, exo_angles: SG_T.Sequence[Sequence[Union[int, float]]]) -> None:
        self.filters = []
        self._finger_scratch = []
        self._finger_out = []
        self._prev_finger_raw = []
        for finger_angles in exo_angles:
            n_joints = len(finger_angles)
            finger_filters = [
                FilterSuspicion(final_smoothing_EWMA=self.final_smoothing_EWMA, checks=self.checks)
                for joint_idx in range(n_joints)
            ]
            for joint_idx, joint_filter in enumerate(finger_filters):
                min_lim, max_lim = lookup_joint_range_limits(len(self.filters), joint_idx, self.hand)
                joint_filter.angle_min_limit = min_lim
                joint_filter.angle_max_limit = max_lim
            self.filters.append(finger_filters)
            self._finger_scratch.append([0.0] * n_joints)
            self._finger_out.append([0.0] * n_joints)
            self._prev_finger_raw.append([0.0] * n_joints)
        self.initialized = True

    def update(
        self,
        exo_angles: SG_T.Sequence[Sequence[Union[int, float]]],
    ) -> SG_T.Sequence[Sequence[float]]:
        if not self.initialized:
            self._initialize_filters(exo_angles)

        for finger_idx, finger_angles in enumerate(exo_angles):
            finger_raw = self._finger_scratch[finger_idx]
            filtered_finger = self._finger_out[finger_idx]
            finger_prev = self._prev_finger_raw[finger_idx]
            finger_filters = self.filters[finger_idx]

            for joint_idx, angle in enumerate(finger_angles):
                finger_raw[joint_idx] = float(angle)

            for joint_idx, value in enumerate(finger_raw):
                filtered_finger[joint_idx] = finger_filters[joint_idx].update(
                    value,
                    finger_raw=finger_raw,
                    finger_prev=finger_prev,
                    joint_idx=joint_idx,
                )

            for joint_idx, value in enumerate(finger_raw):
                finger_prev[joint_idx] = value

        return self._finger_out

    def reset(self) -> None:
        self.filters = []
        self.initialized = False
        self._prev_finger_raw = None
        self._finger_scratch = []
        self._finger_out = []

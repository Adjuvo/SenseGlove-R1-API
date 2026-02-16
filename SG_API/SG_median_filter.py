"""
Median Filter Module for SenseGlove Rembrandt API.

This module provides a median filter implementation with customizable window size
for filtering exoskeleton angle data to reduce noise and improve signal quality.
This is especially useful to filter out the jitter in tracking data occuring once in a while.

Note: it is currently not optimized for performance, so it tanks FPS if used.

Questions? Written by:
- Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api
Support: https://www.senseglove.com/support/
"""

import numpy as np
from collections import deque   
from typing import List, Union, Optional, Deque, Dict, Any, Sequence
from . import SG_types as SG_T


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
        self.initialized = False
    
    def update(self, value: float) -> float:
        """
        Add a new value to the filter and return the filtered result.
        
        Args:
            value (float): The new input value to be filtered.
        
        Returns:
            float: The median of the current window.
        """
         # Only append if it's not the same as the last added value
        if not self.buffer or self.buffer[-1] != value:
            self.buffer.append(value)
        
        # Return median of current buffer
        return float(np.median(list(self.buffer)))
    
    def reset(self):
        """Clear the filter buffer and reset the filter state."""
        self.buffer.clear()
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
    
    def get_debug_info(self, finger_idx: int = 0) -> Dict[str, Any]:
        """
        Get debugging information for a specific finger's filters.
        
        Args:
            finger_idx (int): Index of finger to debug (0=thumb, 1=index, etc.)
        
        Returns:
            dict: Debug information including buffer contents for each angle
        """
        if not self.initialized or finger_idx >= len(self.filters):
            return {"error": "Filter not initialized or invalid finger index"}
        
        debug_info = {
            "finger_index": finger_idx,
            "window_size": self.window_size,
            "initialized": self.initialized,
            "angles": []
        }
        
        for angle_idx, angle_filter in enumerate(self.filters[finger_idx]):
            angle_info = {
                "angle_index": angle_idx,
                "buffer_contents": list(angle_filter.buffer),
                "buffer_length": len(angle_filter.buffer),
                "is_ready": angle_filter.is_ready(),
                "current_median": float(np.median(list(angle_filter.buffer))) if len(angle_filter.buffer) > 0 else None
            }
            debug_info["angles"].append(angle_info)
        
        return debug_info
    
    def print_debug_info(self, finger_idx: int = 0, angle_indices: Optional[List[int]] = None):
        """
        Print debugging information for a specific finger.
        
        Args:
            finger_idx (int): Index of finger to debug (0=thumb, 1=index, etc.)
            angle_indices (List[int], optional): Specific angle indices to print. If None, prints all.
        """
        debug_info = self.get_debug_info(finger_idx)
        
        if "error" in debug_info:
            print(f"Debug Error: {debug_info['error']}")
            return
        
        finger_names = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
        finger_name = finger_names[finger_idx] if finger_idx < len(finger_names) else f"Finger_{finger_idx}"
        
        angles_to_show = angle_indices if angle_indices is not None else range(len(debug_info["angles"]))
        
        for angle_idx in angles_to_show:
            if angle_idx < len(debug_info["angles"]):
                angle_info = debug_info["angles"][angle_idx]
                buffer_str = [f"{x:.3f}" for x in angle_info['buffer_contents']]
                median_str = f"{angle_info['current_median']:.3f}" if angle_info['current_median'] is not None else "None"
                print(f"{finger_name}[{angle_idx}] Buffer: {buffer_str} -> Median: {median_str}")
    
    def print_debug_info_verbose(self, finger_idx: int = 0, angle_indices: Optional[List[int]] = None):
        """
        Print detailed debugging information for a specific finger (original verbose version).
        
        Args:
            finger_idx (int): Index of finger to debug (0=thumb, 1=index, etc.)
            angle_indices (List[int], optional): Specific angle indices to print. If None, prints all.
        """
        debug_info = self.get_debug_info(finger_idx)
        
        if "error" in debug_info:
            print(f"Debug Error: {debug_info['error']}")
            return
        
        finger_names = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
        finger_name = finger_names[finger_idx] if finger_idx < len(finger_names) else f"Finger_{finger_idx}"
        
        print(f"\n=== Median Filter Debug Info for {finger_name} ===")
        print(f"Window Size: {debug_info['window_size']}")
        print(f"Filter Initialized: {debug_info['initialized']}")
        
        angles_to_show = angle_indices if angle_indices is not None else range(len(debug_info["angles"]))
        
        for angle_idx in angles_to_show:
            if angle_idx < len(debug_info["angles"]):
                angle_info = debug_info["angles"][angle_idx]
                print(f"\nAngle {angle_idx}:")
                print(f"  Buffer: {angle_info['buffer_contents']}")
                print(f"  Length: {angle_info['buffer_length']}/{self.window_size}")
                print(f"  Ready: {angle_info['is_ready']}")
                print(f"  Current Median: {angle_info['current_median']}")
        print("=" * 50)
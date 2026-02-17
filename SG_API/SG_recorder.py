"""
Can make recordings of the glove data, and play them back as a simulated glove.
For use see examples/record_glove.py and examples/play_recording.py.

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

import time
import numpy as np
import json
from typing import List, Dict, Any, cast, Optional
from SG_API import SG_main
from SG_API import SG_types as SG_T
from SG_API import SG_simulator as SG_sim
import os

# Global recorder instance for playback
_playback_recorder: Optional['GloveRecorder'] = None

class GloveRecorder:
    def __init__(self, device_info: SG_T.Device_Info):
        """
        Initialize the glove recorder for a specific device
        """
        self.device_info = device_info
        self.recorded_data: List[Dict[str, Any]] = []
        self.is_recording = False
        self.start_time = 0
        self.is_playing = False
        self.playback_start_time = 0
        self.current_frame_index = 0
        self.loop = True
        self._recording_metadata: Optional[Dict[str, Any]] = None

    def start_recording(self):
        """
        Start recording glove data
        """
        self.recorded_data = []
        self.is_recording = True
        self.start_time = time.time()

    def stop_recording(self):
        """
        Stop recording glove data
        """
        self.is_recording = False

    def update(self):
        """
        Record current glove state if recording is active
        """
        if not self.is_recording:
            return

        current_time = time.time() - self.start_time
        angles_rad = SG_main.get_exo_angles_rad(self.device_info.device_id)
        
        # Convert numpy array to list for JSON serialization
        angles_list = [[float(x) for x in angles] for angles in angles_rad]
        
        self.recorded_data.append({
            'timestamp': current_time,
            'angles_rad': angles_list
        })

    def set_loop(self, loop: bool):
        self.loop = loop

    def save_recording(self, filename: str):
        """
        Save recorded data to a JSON file with metadata
        """
        if not self.recorded_data:
            raise ValueError("No data recorded to save")

        # Create recording with metadata
        recording_with_metadata = {
            'metadata': {
                'exo_linkage_type': self.device_info.exo_linkage_type.value,
                'hand': self.device_info.hand.value,
                'nr_fingers_tracking': self.device_info.nr_fingers_tracking,
                'nr_fingers_force': self.device_info.nr_fingers_force
            },
            'frames': self.recorded_data
        }

        with open(filename, 'w') as f:
            json.dump(recording_with_metadata, f)

    def load_recording(self, filename: str):
        """
        Load recorded data from a JSON file
        Supports both old format (list) and new format (dict with metadata)
        """
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Check if new format with metadata
        if isinstance(data, dict) and 'metadata' in data and 'frames' in data:
            self.recorded_data = cast(List[Dict[str, Any]], data['frames'])
            # Store metadata for later use
            self._recording_metadata = data['metadata']
        else:
            # Old format - just frames
            self.recorded_data = cast(List[Dict[str, Any]], data)
            self._recording_metadata = None

    def start_playback(self):
        """
        Start playing back the loaded recording
        """
        if not self.recorded_data:
            raise ValueError("No recording loaded to play back")
        
        self.is_playing = True
        self.playback_start_time = time.time()
        self.current_frame_index = 0

    def update_playback(self):
        """
        Update playback state - should be called in the main update loop
        """
        if not self.is_playing:
            return

        current_time = time.time() - self.playback_start_time
        
        # Find the next frame to play
        while (self.current_frame_index < len(self.recorded_data) - 1 and 
               self.recorded_data[self.current_frame_index + 1]['timestamp'] <= current_time):
            self.current_frame_index += 1

        # If we've reached the end of the recording
        if (self.current_frame_index >= len(self.recorded_data) - 1 and 
            current_time > self.recorded_data[-1]['timestamp']):
            self.is_playing = False
            if self.loop:
                self.current_frame_index = 0
                self.playback_start_time = time.time()
                self.is_playing = True
            return

        # Play the current frame
        frame = self.recorded_data[self.current_frame_index]
        angles_rad = cast(List[List[float]], frame['angles_rad'])
        SG_sim.set_angles_rad(self.device_info, angles_rad)

def record_glove_data(device_id: int, duration: float, output_file: str):
    """
    Record glove data for a specified duration and save to file
    Args:
        device_id: The ID of the glove to record from
        duration: How long to record in seconds
        output_file: Path to save the recording relative to the recordings folder (filename only or with/without folder)
    """
    # Ensure the recordings directory exists
    recordings_dir = "recordings"
    os.makedirs(recordings_dir, exist_ok=True)
    # If output_file is a path, get only the filename
    filename = os.path.basename(output_file)
    output_path = os.path.join(recordings_dir, filename)

    recorder = GloveRecorder(SG_main.get_device_info(device_id))
    recorder.start_recording()
    
    start_time = time.time()
    while time.time() - start_time < duration:
        recorder.update()
        time.sleep(0.001)  # Small sleep to prevent CPU overload
    
    recorder.stop_recording()
    recorder.save_recording(output_path)
    print(f"Recording saved to {output_path}")

def play_recording(device_info: SG_T.Device_Info, input_file: str, loop: bool = True):
    """
    Play back a recorded glove data file
    
    Args:
        device_info: Device info of the simulator to play back on
        input_file: Path to the recording file
        loop: Whether to loop the recording
        
    Note: The simulator should be in STEADY_MODE to avoid conflicts with recording playback
    """
    global _playback_recorder
    # If input_file is not absolute, look in 'recordings' folder
    if not os.path.isabs(input_file):
        input_file = os.path.join("recordings", os.path.basename(input_file))
    
    _playback_recorder = GloveRecorder(device_info)
    _playback_recorder.load_recording(input_file)
    
    # Initialize with first frame if available
    if _playback_recorder.recorded_data:
        first_frame = _playback_recorder.recorded_data[0]
        first_frame_angles = cast(List[List[float]], first_frame['angles_rad'])
        SG_sim.set_angles_rad(device_info, first_frame_angles)
    
    _playback_recorder.start_playback()
    _playback_recorder.set_loop(loop)

def get_device_info(input_file: str) -> Optional[SG_T.Device_Info]:
    """
    Read metadata from a recording file without loading the entire recording.
    Returns a Device_Info object with the recording's configuration, or None if no metadata.
    
    Args:
        input_file: Path to the recording file
        
    Returns:
        Device_Info with the recording's configuration, or None if old format without metadata
        
    Example:
        ```python
        metadata_info = SG_recorder.get_recording_metadata("my_recording.json")
        if metadata_info:
            print(f"Recording uses: {metadata_info.exo_linkage_type}, {metadata_info.hand}")
        ```
    """
    # If input_file is not absolute, look in 'recordings' folder
    if not os.path.isabs(input_file):
        input_file = os.path.join("recordings", os.path.basename(input_file))
    
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Check if new format with metadata
    if isinstance(data, dict) and 'metadata' in data:
        metadata = data['metadata']
        
        # Create a Device_Info from the metadata
        device_info = SG_T.Device_Info(
            device_id=0,  # Placeholder, will be replaced when creating simulator
            hand=SG_T.Hand(metadata['hand']),
            nr_fingers_tracking=metadata['nr_fingers_tracking'],
            nr_fingers_force=metadata['nr_fingers_force'],
            firmware_version="0.0.0-sim",
            device_type=SG_T.DeviceType.REMBRANDT,
            communication_type=SG_T.Com_type.SIMULATED_GLOVE,
            exo_linkage_type=SG_T.Exo_linkage_type(metadata['exo_linkage_type']),
            encoding_type=SG_T.Encoding_type.REMBRANDT_v01,
            data_origin=SG_T.Data_Origin.LIVE_TEST_SIM
        )
        return device_info
    else:
        # Old format - no metadata available
        print(f"Warning: Recording '{input_file}' has no metadata (old format)")
        return None

def update():
    """
    Update function to be called in the main update loop
    """
    global _playback_recorder
    if _playback_recorder is not None:
        _playback_recorder.update_playback() 
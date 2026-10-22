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
import csv
import re
from typing import List, Dict, Any, cast, Optional, Callable
from SG_API import SG_main
from SG_API import SG_types as SG_T
from SG_API import SG_simulator as SG_sim
import os




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
        self.playback_time_origin = 0.0
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

    def update_manually(self, raw_angles_rad, filtered_angles_rad):

        current_time = time.time() - self.start_time
        # Convert numpy array to list for JSON serialization
        raw_angles_list = [[float(x) for x in angles] for angles in raw_angles_rad]
        filtered_angles_list = [[float(x) for x in angles] for angles in filtered_angles_rad]
        
        self.recorded_data.append({
            'timestamp': current_time,
            'angles_rad': raw_angles_list,
            'filtered_angles_rad': filtered_angles_list
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
        Load recorded data from a JSON or CSV file.
        JSON supports old format (list) and new format (dict with metadata).
        CSV uses raw_/filtered_ columns when present (see GloveCsvRecorder).
        """
        if _is_csv_recording(filename):
            self._load_csv_into(filename)
            return

        with open(filename, "r") as f:
            data = json.load(f)
        
        # Check if new format with metadata
        if isinstance(data, dict) and "metadata" in data and "frames" in data:
            self.recorded_data = cast(List[Dict[str, Any]], data["frames"])
            self._recording_metadata = data["metadata"]
        else:
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
        self.playback_time_origin = float(self.recorded_data[0]["timestamp"])
        self.current_frame_index = 0

    def _playback_elapsed(self) -> float:
        return time.time() - self.playback_start_time

    def _frame_playback_offset(self, frame_index: int) -> float:
        return float(self.recorded_data[frame_index]["timestamp"]) - self.playback_time_origin

    def update_playback(self):
        """
        Update playback state - should be called in the main update loop
        """
        if not self.is_playing:
            return

        elapsed = self._playback_elapsed()
        
        # Find the next frame to play
        while (self.current_frame_index < len(self.recorded_data) - 1 and 
               self._frame_playback_offset(self.current_frame_index + 1) <= elapsed):
            self.current_frame_index += 1

        # If we've reached the end of the recording
        if (self.current_frame_index >= len(self.recorded_data) - 1 and 
            elapsed > self._frame_playback_offset(len(self.recorded_data) - 1)):
            self.is_playing = False
            if self.loop:
                self.current_frame_index = 0
                self.playback_start_time = time.time()
                self.is_playing = True
            return

        # Play the current frame
        frame = self.recorded_data[self.current_frame_index]
        angles_rad = cast(
            List[List[float]],
            frame.get('filtered_angles_rad', frame['angles_rad']),
        )
        SG_sim.set_angles_rad(self.device_info, angles_rad)

    def _load_csv_into(self, filename: str) -> None:
        with open(filename, "r", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            if not header or "timestamp" not in header:
                raise ValueError("CSV must have a header row with a timestamp column")

            recorded_data: List[Dict[str, Any]] = []
            for row in reader:
                if not row:
                    continue
                ts = float(row[header.index("timestamp")])
                has_prefixed_cols = any(
                    name.startswith("raw_") or name.startswith("filtered_")
                    for name in header
                    if name != "timestamp"
                )
                if has_prefixed_cols:
                    angles_rad = _unflatten_angles(header, row, prefix="raw_")
                    if any(name.startswith("filtered_") for name in header):
                        filtered_angles_rad = _unflatten_angles(header, row, prefix="filtered_")
                    else:
                        filtered_angles_rad = angles_rad
                else:
                    angles_rad = _unflatten_angles(header, row, prefix="")
                    filtered_angles_rad = angles_rad
                recorded_data.append({
                    "timestamp": ts,
                    "angles_rad": angles_rad,
                    "filtered_angles_rad": filtered_angles_rad,
                })


        self.recorded_data = recorded_data
        sidecar = load_sidecar_metadata(filename)
        self._recording_metadata = sidecar



_playback_recorders: Dict[int, GloveRecorder] = {}

def get_recorder(device_id: int) -> Optional[GloveRecorder]:
    global _playback_recorders
    if device_id in _playback_recorders:
        return _playback_recorders[device_id]
    else:
        return None

def create_recorder(device_info: SG_T.Device_Info) -> GloveRecorder:
    global _playback_recorders
    recorder = GloveRecorder(device_info)
    _playback_recorders[device_info.device_id] = recorder
    return recorder


def update_all_recorders():
    global _playback_recorders
    for recorder in _playback_recorders.values():
        recorder.update_playback()


def _package_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _package_recordings_dir() -> str:
    """Bundled demo recordings shipped inside SG_API/."""
    return os.path.join(_package_dir(), "recordings")


def _cwd_recordings_dir() -> str:
    """User recordings folder under the process current working directory."""
    return os.path.join(os.getcwd(), "recordings")


def _recordings_search_dirs() -> List[str]:
    """Playback lookup order: cwd first, then packaged demos, then internal/dev."""
    pkg = _package_dir()
    repo_root = os.path.dirname(pkg)
    return [
        _cwd_recordings_dir(),
        _package_recordings_dir(),
        os.path.join(repo_root, "internal", "recordings"),
    ]


def _normalize_user_path(path: str) -> str:
    """Expand ~ and accept both / and \\ separators (Windows-style paths)."""
    path = os.path.expanduser(str(path).strip())
    if "\\" in path:
        path = path.replace("\\", "/")
    return path


def _is_absolute_path(path: str) -> bool:
    """True for POSIX abs, Windows drive-letter (C:/...), and UNC (//server/share)."""
    if os.path.isabs(path):
        return True
    if len(path) >= 3 and path[0].isalpha() and path[1] == ":" and path[2] == "/":
        return True
    if path.startswith("//"):
        return True
    return False


def _resolve_recording_path(input_file: str) -> str:
    """Resolve a recording for playback.

    Absolute / ~/ paths are used as-is. Relative paths are relative to cwd.
    Bare filenames are searched under cwd/recordings/, then packaged demos.
    """
    path = _normalize_user_path(input_file)
    if _is_absolute_path(path):
        return os.path.normpath(path)
    if os.path.dirname(path):
        # Explicit relative path (./out/x.csv, recordings/x.csv, ...) — cwd-based
        return os.path.abspath(path)
    if os.path.isfile(path):
        return os.path.abspath(path)
    name = os.path.basename(path)
    for directory in _recordings_search_dirs():
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(_cwd_recordings_dir(), name)


def _resolve_output_path(output_file: str) -> str:
    """Resolve where to save a recording.

    Absolute / ~/ paths are used as-is. Relative paths are relative to cwd.
    Bare filenames go under cwd/recordings/ (created if needed), never site-packages.
    """
    path = _normalize_user_path(output_file)
    if _is_absolute_path(path) or os.path.dirname(path):
        if not _is_absolute_path(path):
            path = os.path.abspath(path)
        else:
            path = os.path.normpath(path)
        parent = os.path.dirname(path)
        if parent:
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError:
                # e.g. UNC roots; save/open will report a clearer error if unusable
                pass
        return path
    recordings_dir = _cwd_recordings_dir()
    os.makedirs(recordings_dir, exist_ok=True)
    return os.path.join(recordings_dir, path)


def _is_csv_path(path: str) -> bool:
    """True when the path extension selects CSV format (save or new recordings)."""
    return os.path.splitext(path)[1].lower() == ".csv"


def _is_csv_recording(path: str) -> bool:
    if os.path.splitext(path)[1].lower() != ".csv":
        return False
    with open(path, "r", encoding="utf-8") as f:
        return f.read(1) != "{"


_ANGLE_COL_PATTERN = re.compile(r"^(?:raw_|filtered_)?f(\d+)_j(\d+)$")


def _unflatten_angles(header: List[str], row: List[str], prefix: Optional[str] = None) -> List[List[float]]:
    col_index = {name: i for i, name in enumerate(header)}
    by_finger: Dict[int, Dict[int, float]] = {}
    for name in header:
        if name == "timestamp":
            continue
        if prefix is not None:
            if prefix == "" and (name.startswith("raw_") or name.startswith("filtered_")):
                continue
            elif prefix and not name.startswith(prefix):
                continue
        match = _ANGLE_COL_PATTERN.match(name)
        if not match:
            raise ValueError(f"Invalid angle column: {name}")
        fi, ji = int(match.group(1)), int(match.group(2))
        by_finger.setdefault(fi, {})[ji] = float(row[col_index[name]])
    return [
        [by_finger[fi][ji] for ji in sorted(by_finger[fi].keys())]
        for fi in sorted(by_finger.keys())
    ]


def _count_fingers_from_csv_header(header: List[str]) -> int:
    fingers = set()
    for name in header:
        if name == "timestamp":
            continue
        match = _ANGLE_COL_PATTERN.match(name)
        if match:
            fingers.add(int(match.group(1)))
    return len(fingers) if fingers else 5


def _sidecar_path(csv_path: str) -> str:
    base, _ = os.path.splitext(csv_path)
    return base + ".meta.json"


def metadata_from_device_info(device_info: SG_T.Device_Info) -> Dict[str, Any]:
    """Build sidecar metadata dict (same fields as JSON recording metadata)."""
    meta: Dict[str, Any] = {
        "exo_linkage_type": device_info.exo_linkage_type.value,
        "hand": int(device_info.hand),
        "nr_fingers_tracking": device_info.nr_fingers_tracking,
        "nr_fingers_force": device_info.nr_fingers_force,
    }
    if device_info.firmware_version:
        meta["firmware_version"] = device_info.firmware_version
    if device_info.device_id:
        meta["device_id"] = device_info.device_id
    return meta


def device_info_from_metadata(
    metadata: Dict[str, Any],
    nr_fingers_tracking: Optional[int] = None,
) -> SG_T.Device_Info:
    """Create Device_Info from sidecar or JSON metadata."""
    nr_fingers = nr_fingers_tracking if nr_fingers_tracking is not None else metadata["nr_fingers_tracking"]
    return SG_T.Device_Info(
        device_id=int(metadata.get("device_id", 0)),
        hand=SG_T.Hand(metadata["hand"]),
        nr_fingers_tracking=nr_fingers,
        nr_fingers_force=int(metadata.get("nr_fingers_force", 4)),
        firmware_version=str(metadata.get("firmware_version", "0.0.0-sim")),
        device_type=SG_T.DeviceType.REMBRANDT,
        communication_type=SG_T.Com_type.SIMULATED_GLOVE,
        exo_linkage_type=SG_T.Exo_linkage_type(metadata["exo_linkage_type"]),
        encoding_type=SG_T.Encoding_type.REMBRANDT_v01,
        data_origin=SG_T.Data_Origin.LIVE_TEST_SIM,
    )


def save_sidecar_metadata(csv_path: str, device_info: SG_T.Device_Info) -> str:
    """Write `<recording>.meta.json` next to a CSV file. Returns sidecar path."""
    sidecar = _sidecar_path(csv_path)
    with open(sidecar, "w", encoding="utf-8") as f:
        json.dump(metadata_from_device_info(device_info), f, indent=2)
    return sidecar


def load_sidecar_metadata(csv_path: str) -> Optional[Dict[str, Any]]:
    """Load `<recording>.meta.json` if present."""
    sidecar = _sidecar_path(csv_path)
    if not os.path.isfile(sidecar):
        return None
    with open(sidecar, "r", encoding="utf-8") as f:
        return cast(Dict[str, Any], json.load(f))


def default_playback_device_info(
    hand: SG_T.Hand = SG_T.Hand.RIGHT,
    exo_linkage_type: SG_T.Exo_linkage_type = SG_T.Exo_linkage_type.REMBRANDT_PROTO_05,
    nr_fingers_tracking: int = 5,
    nr_fingers_force: int = 4,
) -> SG_T.Device_Info:
    """Default simulator device info for CSV recordings (no embedded metadata)."""
    return SG_T.Device_Info(
        device_id=0,
        hand=hand,
        nr_fingers_tracking=nr_fingers_tracking,
        nr_fingers_force=nr_fingers_force,
        firmware_version="0.0.0-sim",
        device_type=SG_T.DeviceType.REMBRANDT,
        communication_type=SG_T.Com_type.SIMULATED_GLOVE,
        exo_linkage_type=exo_linkage_type,
        encoding_type=SG_T.Encoding_type.REMBRANDT_v01,
        data_origin=SG_T.Data_Origin.LIVE_TEST_SIM,
    )






def _angle_column_names(
    angles_rad: List[List[float]],
    filtered_angles_rad: Optional[List[List[float]]] = None,
) -> List[str]:
    names: List[str] = []
    for fi, finger in enumerate(angles_rad):
        for ji in range(len(finger)):
            names.append(f'raw_f{fi}_j{ji}')
    if filtered_angles_rad is not None:
        for fi, finger in enumerate(filtered_angles_rad):
            for ji in range(len(finger)):
                names.append(f'filtered_f{fi}_j{ji}')
    return names


def _flatten_angles(angles_rad: List[List[float]]) -> List[float]:
    return [float(x) for finger in angles_rad for x in finger]


class GloveCsvRecorder(GloveRecorder):
    """
    Records timestamps and exo angles. Saves flat CSV plus a `.meta.json` sidecar.
    Column layout: timestamp, raw_f0_j0, ... optional filtered_f0_j0, ...
    """

    def __init__(self, device_info: SG_T.Device_Info, record_filtered: bool = False):
        super().__init__(device_info)
        self.record_filtered = record_filtered

    def update(self):
        if not self.is_recording:
            return

        from SG_API import SG_devices

        current_time = time.time() - self.start_time
        rb_device = SG_devices.get_rembrandt_device(self.device_info.device_id)
        raw_angles_rad = rb_device.get_exo_angles_rad_raw()
        raw_angles_list = [[float(x) for x in angles] for angles in raw_angles_rad]

        frame: Dict[str, Any] = {
            'timestamp': current_time,
            'angles_rad': raw_angles_list,
        }
        if self.record_filtered:
            filtered_angles_rad = rb_device.get_exo_angles_rad_filtered()
            frame['filtered_angles_rad'] = [
                [float(x) for x in angles] for angles in filtered_angles_rad
            ]

        self.recorded_data.append(frame)

    def update_manually(self, raw_angles_rad, filtered_angles_rad):
        current_time = time.time() - self.start_time
        raw_angles_list = [[float(x) for x in angles] for angles in raw_angles_rad]

        frame: Dict[str, Any] = {
            'timestamp': current_time,
            'angles_rad': raw_angles_list,
        }
        if self.record_filtered:
            frame['filtered_angles_rad'] = [
                [float(x) for x in angles] for angles in filtered_angles_rad
            ]

        self.recorded_data.append(frame)

    def save_recording(self, filename: str):
        if not self.recorded_data:
            raise ValueError("No data recorded to save")

        first_frame = self.recorded_data[0]
        raw_angles = cast(List[List[float]], first_frame['angles_rad'])
        filtered_angles = (
            cast(List[List[float]], first_frame['filtered_angles_rad'])
            if self.record_filtered
            else None
        )
        angle_cols = _angle_column_names(raw_angles, filtered_angles)
        expected_len = len(angle_cols)

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp'] + angle_cols)
            for frame in self.recorded_data:
                flat = _flatten_angles(cast(List[List[float]], frame['angles_rad']))
                if self.record_filtered:
                    filtered = frame.get('filtered_angles_rad', frame['angles_rad'])
                    flat += _flatten_angles(cast(List[List[float]], filtered))
                if len(flat) != expected_len:
                    raise ValueError("Inconsistent angles shape across frames")
                writer.writerow([frame['timestamp']] + flat)

        sidecar = save_sidecar_metadata(filename, self.device_info)
        print(f"Recording metadata saved at: {sidecar}")




def _create_recorder(
    device_info: SG_T.Device_Info,
    output_path: str,
    record_filtered: bool = False,
) -> GloveRecorder:
    if _is_csv_path(output_path):
        return GloveCsvRecorder(device_info, record_filtered=record_filtered)
    return GloveRecorder(device_info)


def record_glove_data(
    device_id: int,
    duration: float,
    output_file: str,
    pump_events: Optional[Callable[[], None]] = None,
    record_filtered: bool = False,
):
    """
    Record glove data for a specified duration and save to file.
    Format is chosen from the file extension: ``.json`` (default) or ``.csv``.
    On Ctrl+C, any captured frames are saved before the interrupt is re-raised.
    Args:
        device_id: The ID of the glove to record from
        duration: How long to record in seconds
        output_file: Bare filename under cwd/recordings/ (created if needed), or an
            absolute / cwd-relative path (e.g. "take.csv", "/tmp/take.csv", "./out/take.csv")
        pump_events: Optional callback (e.g. QApplication.processEvents) so a GUI can repaint during recording
        record_filtered: For CSV output, also record filtered angle columns (default: raw only)
    """
    output_path = _resolve_output_path(output_file)

    device_info = SG_main.get_device_info(device_id)
    recorder = _create_recorder(device_info, output_path, record_filtered=record_filtered)
    recorder.start_recording()

    interrupted = False
    try:
        start_time = time.time()
        while time.time() - start_time < duration:
            recorder.update()
            if pump_events is not None:
                pump_events()
            time.sleep(0.001)  # Small sleep to prevent CPU overload
    except KeyboardInterrupt:
        interrupted = True
    finally:
        recorder.stop_recording()
        if recorder.recorded_data:
            recorder.save_recording(output_path)
            if interrupted:
                print(f"Recording interrupted — partial data saved to {output_path}")
            else:
                print(f"Recording saved to {output_path}")
        elif interrupted:
            print("Recording interrupted with no frames captured.")

    if interrupted:
        raise KeyboardInterrupt


def record_glove_data_csv(
    device_id: int,
    duration: float,
    output_file: str,
    pump_events: Optional[Callable[[], None]] = None,
    record_filtered: bool = False,
):
    """
    Record glove angles and timestamps for a duration and save to CSV.
    Prefer ``record_glove_data`` with a ``.csv`` filename; this alias remains for compatibility.
    """
    if not _is_csv_path(output_file):
        output_file = os.path.splitext(output_file)[0] + ".csv"
    record_glove_data(
        device_id, duration, output_file,
        pump_events=pump_events,
        record_filtered=record_filtered,
    )



def play_recording(device_info: SG_T.Device_Info, input_file: str, loop: bool = True):
    """
    Play back a recorded glove data file (.json or .csv)
    
    Args:
        device_info: Device info of the simulator to play back on
        input_file: Bare filename (cwd/recordings/ then packaged demos), or an absolute /
            cwd-relative path to a recording (.json or .csv)
        loop: Whether to loop the recording
        
    Note: Put the simulator in PLAYBACK_MODE (not STEADY_MODE) so angles are driven only by
    this playback and on_new_data is not fired twice per sample.
    """
    
    input_file = _resolve_recording_path(input_file)
    print("loading recording: ", input_file)
    
    _playback_recorder = create_recorder(device_info)
    _playback_recorder.load_recording(input_file)
    
    # Initialize with first frame if available
    if _playback_recorder.recorded_data:
        first_frame = _playback_recorder.recorded_data[0]
        first_frame_angles = cast(
            List[List[float]],
            first_frame.get('filtered_angles_rad', first_frame['angles_rad']),
        )
        SG_sim.set_angles_rad(device_info, first_frame_angles)
    
    _playback_recorder.start_playback()
    _playback_recorder.set_loop(loop)

def get_device_info(input_file: str) -> Optional[SG_T.Device_Info]:
    """
    Read metadata from a recording file without loading the entire recording.
    Returns a Device_Info object with the recording's configuration.
    
    JSON: reads embedded metadata.
    CSV: reads `<name>.meta.json` sidecar if present, else defaults.
    
    Args:
        input_file: Bare filename (cwd/recordings/ then packaged demos), or an absolute /
            cwd-relative path to a recording (.json or .csv)
        
    Returns:
        Device_Info with the recording's configuration, or None for legacy JSON without metadata
    """
    input_file = _resolve_recording_path(input_file)
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"Recording not found: {input_file}")

    if _is_csv_recording(input_file):
        with open(input_file, "r", newline="") as f:
            header = next(csv.reader(f))
        if not header or "timestamp" not in header:
            raise ValueError("CSV must have a header row with a timestamp column")
        nr_fingers = _count_fingers_from_csv_header(header)
        sidecar = load_sidecar_metadata(input_file)
        if sidecar is not None:
            return device_info_from_metadata(sidecar, nr_fingers_tracking=nr_fingers)
        return default_playback_device_info(nr_fingers_tracking=nr_fingers)
    
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Check if new format with metadata
    if isinstance(data, dict) and 'metadata' in data:
        return device_info_from_metadata(data['metadata'])
    else:
        # Old format - no metadata available
        print(f"Warning: Recording '{input_file}' has no metadata (old format)")
        return None

def restart_playback(device_id: int):
    """Reset playback clock to frame 0. Call when the 1 kHz timer actually starts."""
    recorder = get_recorder(device_id)
    if recorder is not None:
        recorder.start_playback()


def update(device_id: int):
    """
    Update function to be called in the main update loop
    """
    recorder = get_recorder(device_id)
    if recorder is not None:
        recorder.update_playback() 
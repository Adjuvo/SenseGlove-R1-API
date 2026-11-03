"""
Turn a glove recording (exo angles CSV/JSON) into an all_data (fingertips, percentage bents, exo angles) CSV for analysis (still suitable for playback).

1. Set recording_filename / output_filename in main() below.
2. From the repo root:  python examples/recording_and_playback/recording_to_all_data_csv.py
3. Play the result with play_recording.py (same as any other recording).

Output columns (in order): timestamp_unix_us, fingertip_pos, fingertip_rot,
flexion_perc, abduction_perc, exo_angles.

Note: currently timestamp_unix_ms is calculated in this script. For R2 timestamps will be sent with the glove.


Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

import csv
import os
import sys
import time
from typing import List, Sequence, Union

#------------ Necessary for SG_API include ------------------------
sys.path.append(os.path.abspath('.'))  # so it recognizes the SG_API folder

from SG_API import SG_main, SG_types as SG_T
from SG_API import SG_recorder


XYZ = ("x", "y", "z")
WXYZ = ("w", "x", "y", "z")


def derived_csv_header(nr_fingers: int, nr_joints: int) -> List[str]:
    header = ["timestamp_unix_us"]
    for fi in range(nr_fingers):
        for axis in XYZ:
            header.append(f"fingertip_pos_f{fi}_{axis}")
    for fi in range(nr_fingers):
        for axis in WXYZ:
            header.append(f"fingertip_rot_f{fi}_{axis}")
    for fi in range(nr_fingers):
        header.append(f"flexion_perc_f{fi}")
    for fi in range(nr_fingers):
        header.append(f"abduction_perc_f{fi}")
    for fi in range(nr_fingers):
        for ji in range(nr_joints):
            header.append(f"exo_f{fi}_j{ji}")
    return header


def relative_s_to_unix_us(
    relative_s: float,
    recording_origin_s: float,
    unix_start_s: float,
) -> int:
    """Map recording-relative seconds onto Unix epoch microseconds starting at unix_start_s."""
    return int(round((unix_start_s + (relative_s - recording_origin_s)) * 1_000_000))


def flatten_derived_row(
    timestamp_us: int,
    fingertips_poss: Sequence[Sequence[float]],
    fingertips_rots: Sequence[Sequence[float]],
    flexion_perc_bents: Sequence[Union[int, float]],
    abduction_perc_bents: Sequence[Union[int, float]],
    exo_angles: Sequence[Sequence[float]],
) -> List[Union[int, float]]:
    row: List[Union[int, float]] = [int(timestamp_us)]
    for pos in fingertips_poss:
        row.extend(float(v) for v in pos)
    for rot in fingertips_rots:
        row.extend(float(v) for v in rot)
    row.extend(float(v) for v in flexion_perc_bents)
    row.extend(float(v) for v in abduction_perc_bents)
    for finger in exo_angles:
        row.extend(float(v) for v in finger)
    return row


def _default_output_name(input_file: str) -> str:
    base = os.path.splitext(os.path.basename(input_file))[0]
    return f"{base}_derived.csv"


def _resolve_output_path(output_file: str) -> str:
    """Bare filename -> cwd/recordings/; otherwise absolute or cwd-relative path."""
    if os.path.isabs(output_file) or os.path.dirname(output_file):
        return os.path.abspath(output_file)
    out_dir = os.path.join(os.getcwd(), "recordings")
    return os.path.join(out_dir, output_file)


def export_recording_derived(input_file: str, output_file: str) -> str:
    """
    Load a recording, compute derived data per frame, write CSV.
    Returns the absolute path written.
    """
    # get_device_info also resolves bare names (cwd/recordings, SG_API/recordings, ...)
    recording_device_info = SG_recorder.get_device_info(input_file)
    if recording_device_info is None:
        raise ValueError(
            f"Recording '{input_file}' has no metadata. "
            "Use a JSON recording from record_glove.py, or a CSV (raw_/filtered_ columns)."
        )

    SG_main.init(0, SG_T.Com_type.SIMULATED_GLOVE)

    recording_device_info.device_id = (
        9999 if recording_device_info.hand == SG_T.Hand.RIGHT else 9998
    )
    simulator = SG_main.SG_sim.create_glove_sim_device(
        recording_device_info,
        SG_main.SG_sim.Simulation_Mode.PLAYBACK_MODE,
    )
    hand_id = simulator.device_id
    device_info = simulator.device_info

    SG_main.set_filter(hand_id, SG_T.Filter_type.OFF, 0.0)

    # Load frames only — do not start playback (timer would race with offline set_angles)
    resolved_input = SG_recorder._resolve_recording_path(input_file)
    recorder = SG_recorder.create_recorder(device_info)
    recorder.load_recording(resolved_input)
    if not recorder.recorded_data:
        raise ValueError(f"Recording '{input_file}' has no frames")

    first_angles = recorder.recorded_data[0].get(
        "filtered_angles_rad", recorder.recorded_data[0]["angles_rad"]
    )
    nr_fingers = len(first_angles)
    nr_joints = len(first_angles[0])
    header = derived_csv_header(nr_fingers, nr_joints)

    output_path = _resolve_output_path(output_file)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    recording_origin_s = float(recorder.recorded_data[0]["timestamp"])
    unix_start_s = time.time()  # treat first frame as "recorded now"

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for frame in recorder.recorded_data:
            angles_rad = frame.get("filtered_angles_rad", frame["angles_rad"])
            SG_main.SG_sim.set_angles_rad(device_info, angles_rad)

            fingertips_poss, fingertips_rots = SG_main.get_fingertips_pos_rot(hand_id)
            flexion_perc_bents, abduction_perc_bents = SG_main.get_percentage_bents(hand_id)
            # Write the angles we set (source of truth); do not re-read under a racing timer
            timestamp_us = relative_s_to_unix_us(
                float(frame["timestamp"]), recording_origin_s, unix_start_s
            )

            writer.writerow(
                flatten_derived_row(
                    timestamp_us,
                    fingertips_poss,
                    fingertips_rots,
                    flexion_perc_bents,
                    abduction_perc_bents,
                    angles_rad,
                )
            )

    SG_main.exit()
    return output_path


def main():
    recording_filename = "finger_close_open.csv"  # or absolute/relative path
    output_filename = "SG_API/recordings/finger_close_open_all_data.csv"

    print(f"Exporting derived data from '{recording_filename}' -> '{output_filename}' ...")
    output_path = export_recording_derived(recording_filename, output_filename)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

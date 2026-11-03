"""CSV load/playback helpers for raw and all_data recording formats."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from SG_API import SG_recorder
from SG_API import SG_types as SG_T

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_RECORDING = REPO_ROOT / "SG_API" / "recordings" / "finger_close_open.csv"
ALL_DATA_RECORDING = REPO_ROOT / "SG_API" / "recordings" / "finger_close_open_all_data.csv"


def test_timestamp_column_accepts_unix_us_label():
    assert SG_recorder._timestamp_column(["timestamp_unix_us", "exo_f0_j0"]) == "timestamp_unix_us"
    assert SG_recorder._timestamp_column(["timestamp", "raw_f0_j0"]) == "timestamp"
    with pytest.raises(ValueError):
        SG_recorder._timestamp_column(["exo_f0_j0"])


def test_angles_from_all_data_csv_row_ignores_extra_columns():
    header = [
        "timestamp_unix_us",
        "fingertip_pos_f0_x",
        "fingertip_pos_f0_y",
        "fingertip_pos_f0_z",
        "flexion_perc_f0",
        "abduction_perc_f0",
        "exo_f0_j0",
        "exo_f0_j1",
        "exo_f1_j0",
        "exo_f1_j1",
    ]
    row = ["1000000", "1", "2", "3", "10", "20", "0.1", "0.2", "0.3", "0.4"]
    angles, filtered = SG_recorder._angles_from_csv_row(header, row)
    assert angles == [[0.1, 0.2], [0.3, 0.4]]
    assert filtered == angles


def test_angles_from_raw_csv_still_works():
    header = ["timestamp", "raw_f0_j0", "raw_f0_j1", "raw_f1_j0", "raw_f1_j1"]
    row = ["0.01", "1.0", "2.0", "3.0", "4.0"]
    angles, filtered = SG_recorder._angles_from_csv_row(header, row)
    assert angles == [[1.0, 2.0], [3.0, 4.0]]
    assert filtered == angles


def test_count_fingers_from_all_data_header():
    header = [
        "timestamp_unix_us",
        "fingertip_pos_f0_x",
        "exo_f0_j0",
        "exo_f1_j0",
        "exo_f2_j0",
        "exo_f3_j0",
        "exo_f4_j0",
    ]
    assert SG_recorder._count_fingers_from_csv_header(header) == 5


def test_load_all_data_csv_uses_relative_seconds_from_unix_us(tmp_path):
    assert ALL_DATA_RECORDING.is_file(), f"missing {ALL_DATA_RECORDING}"

    with ALL_DATA_RECORDING.open("r", newline="", encoding="utf-8") as src:
        reader = csv.reader(src)
        header = next(reader)
        rows = [next(reader) for _ in range(3)]

    tiny = tmp_path / "all_data_tiny.csv"
    with tiny.open("w", newline="", encoding="utf-8") as dst:
        writer = csv.writer(dst)
        writer.writerow(header)
        writer.writerows(rows)

    device_info = SG_recorder.default_playback_device_info(nr_fingers_tracking=5)
    device_info.device_id = 4242
    recorder = SG_recorder.GloveRecorder(device_info)
    recorder.load_recording(str(tiny))

    assert len(recorder.recorded_data) == 3
    ts0 = recorder.recorded_data[0]["timestamp"]
    ts1 = recorder.recorded_data[1]["timestamp"]
    # Relative to first frame (not absolute unix seconds)
    assert ts0 == pytest.approx(0.0)
    expected_delta_s = (int(rows[1][0]) - int(rows[0][0])) / 1_000_000.0
    assert ts1 == pytest.approx(expected_delta_s)

    angles = recorder.recorded_data[0]["angles_rad"]
    assert len(angles) == 5
    assert len(angles[0]) == 8
    exo_idx = header.index("exo_f0_j0")
    assert angles[0][0] == pytest.approx(float(rows[0][exo_idx]))


def test_get_device_info_accepts_all_data_csv():
    assert ALL_DATA_RECORDING.is_file()
    info = SG_recorder.get_device_info(str(ALL_DATA_RECORDING))
    assert info is not None
    assert info.nr_fingers_tracking == 5
    assert info.device_type == SG_T.DeviceType.REMBRANDT


def test_load_raw_csv_unchanged():
    assert RAW_RECORDING.is_file()
    device_info = SG_recorder.default_playback_device_info(nr_fingers_tracking=5)
    device_info.device_id = 4243
    recorder = SG_recorder.GloveRecorder(device_info)
    recorder.load_recording(str(RAW_RECORDING))
    assert len(recorder.recorded_data) > 100
    assert recorder.recorded_data[0]["timestamp"] == pytest.approx(9.298324584960938e-06)
    assert len(recorder.recorded_data[0]["angles_rad"]) == 5


def test_all_data_timing_matches_raw_deltas():
    """Relative frame spacing should match the original raw recording."""
    raw_info = SG_recorder.default_playback_device_info(nr_fingers_tracking=5)
    raw_info.device_id = 5001
    raw_rec = SG_recorder.GloveRecorder(raw_info)
    raw_rec.load_recording(str(RAW_RECORDING))

    all_info = SG_recorder.default_playback_device_info(nr_fingers_tracking=5)
    all_info.device_id = 5002
    all_rec = SG_recorder.GloveRecorder(all_info)
    all_rec.load_recording(str(ALL_DATA_RECORDING))

    n = 50
    raw_origin = raw_rec.recorded_data[0]["timestamp"]
    for i in range(1, n):
        raw_off = raw_rec.recorded_data[i]["timestamp"] - raw_origin
        all_off = all_rec.recorded_data[i]["timestamp"]  # already relative to 0
        assert all_off == pytest.approx(raw_off, abs=1e-6)

import os
import sys
from unittest.mock import patch

import numpy as np
import pytest

sys.path.append(os.path.abspath("."))

from SG_API import SG_types as SG_T
from SG_API.SG_simulator import Glove_Simulator, Simulation_Mode, smoothstep


def _make_sim(mode):
    sim = Glove_Simulator.__new__(Glove_Simulator)
    sim.device_id = 999
    sim.device_info = SG_T.Device_Info(
        999,
        hand=SG_T.Hand.RIGHT,
        nr_fingers_tracking=5,
        nr_fingers_force=4,
        firmware_version="0.0.0-sim",
        device_type=SG_T.DeviceType.REMBRANDT,
        communication_type=SG_T.Com_type.SIMULATED_GLOVE,
        exo_linkage_type=SG_T.Exo_linkage_type.REMBRANDT_PROTO_04,
        encoding_type=SG_T.Encoding_type.REMBRANDT_v01,
        data_origin=SG_T.Data_Origin.LIVE_TEST_SIM,
    )
    sim.mode = mode
    sim.starting_angles_rad_hand = np.zeros((5, 8))
    sim.start_time = 100.0
    sim.custom_sim_fn = None
    return sim


def _capture_updates(sim):
    captured = []

    def capture(angles):
        captured.append(np.array(angles, copy=True))

    sim.update_exo_hand_angles_rad = capture
    return captured


def _expected_fingers_open_close_angles(sim, elapsed_s):
    min_angle_rad = np.radians(55)
    max_angle_rad = np.radians(90)
    # Matches SG_simulator.FINGERS_OPEN_CLOSE: half-speed cycle (t * 0.5)
    t_normalized = 0.5 * (1 - np.cos(2 * np.pi * elapsed_s * 0.5))
    angle = min_angle_rad + smoothstep(t_normalized) * (max_angle_rad - min_angle_rad)
    return sim.starting_angles_rad_hand + np.cos(angle)


@pytest.mark.parametrize(
    "mode,expected_fn",
    [
        (Simulation_Mode.SINE_MODE, lambda sim, t: sim.starting_angles_rad_hand + np.sin(2 * t)),
        (Simulation_Mode.FINGERS_OPEN_CLOSE, _expected_fingers_open_close_angles),
    ],
)
def test_animation_uses_elapsed_wall_time_not_update_count(mode, expected_fn):
    sim = _make_sim(mode)
    captured = _capture_updates(sim)
    elapsed_s = 0.75

    with patch("SG_API.SG_simulator.time.perf_counter", return_value=100.0 + elapsed_s):
        sim.update()
    single_update = captured[-1]

    captured.clear()
    with patch(
        "SG_API.SG_simulator.time.perf_counter",
        side_effect=[100.0 + (i + 1) * (elapsed_s / 50) for i in range(50)],
    ):
        for _ in range(50):
            sim.update()
    many_updates = captured[-1]

    np.testing.assert_allclose(single_update, many_updates)
    np.testing.assert_allclose(single_update, expected_fn(sim, elapsed_s))


def test_custom_function_receives_elapsed_wall_time():
    sim = _make_sim(Simulation_Mode.CUSTOM_FUNCTION)
    received = []

    def custom_fn(t):
        received.append(t)
        return sim.starting_angles_rad_hand

    sim.custom_sim_fn = custom_fn
    captured = _capture_updates(sim)
    sim.start_time = 50.0

    with patch("SG_API.SG_simulator.time.perf_counter", return_value=51.25):
        sim.update()

    assert received == [1.25]
    np.testing.assert_allclose(captured[-1], sim.starting_angles_rad_hand)

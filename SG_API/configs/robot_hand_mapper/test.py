"""
Robot Hand Pinch Configuration
"""

from SG_API.SG_robot_hand_mapper import PinchConfig

config = PinchConfig(
    # Robot Hand Pinch Targets (from percentage bent values)
    # Format: Finger_index: [thumb_abduction, thumb_flexion, finger_flexion]
    robot_pinch_targets={
        1: [5135.000, 8991.000, 3303.000],  # Pinch Index
        2: [5267.000, 8982.000, 5603.000],  # Pinch Middle
        3: [5267.000, 8983.000, 3919.000],  # Pinch Ring
        4: [5267.000, 8982.000, 3310.000],  # Pinch Pinky
    },

    # Pinch detection parameters
    thumb_abduction_threshold=9000,         # Minimum thumb abduction to start considering pinch
    distance_thresholds={
        "enter_distance": 420.0,
        "exit_distance": 55.0,
        "max_distance": 70.0,
        "min_distance": 5.0,
    },

    # Blending and detection settings
    blend_rate=0.12,           # Smooth transition rate (0=instant, 1=very slow)
    primary_pinch_finger=1,   # 0=thumb, 1=index, 2=middle, 3=ring, 4=pinky
)

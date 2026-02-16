"""
Robot Hand Pinch Configuration
"""

from SG_API.SG_robot_hand_mapper import PinchConfig

config = PinchConfig(
    # Robot Hand Pinch Targets (from percentage bent values)
    # Format: Finger_index: [thumb_abduction, thumb_flexion, finger_flexion]
    robot_pinch_targets={
        1: [5000, 9000, 3000],  # Pinch Index
        2: [4500, 9000, 3500],  # Pinch Middle
        3: [4000, 9000, 3200],  # Pinch Ring
        4: [3500, 9000, 2800],  # Pinch Pinky
    },

    # Pinch detection parameters
    thumb_abduction_threshold=9000,  # Minimum thumb abduction to start considering pinch
    distance_thresholds={
        "enter_distance": 20,   # Enter pinch mode when fingertips < 20mm apart
        "exit_distance": 30,    # Exit pinch mode when fingertips > 30mm apart
        "max_distance": 30,     # Max distance for pinch calculation (0% influence)
        "min_distance": 5,      # Min distance for pinch calculation (100% influence)
    },

    # Blending and detection settings
    blend_rate=0.1,            # Smooth transition rate (0=instant, 1=very slow)
    primary_pinch_finger=1,    # 0=thumb, 1=index, 2=middle, 3=ring, 4=pinky
)
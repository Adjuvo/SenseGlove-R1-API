"""
Contains all types used throughout the whole API.

Questions? Written by:
- Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api/
Support: https://www.senseglove.com/support/
"""

# This file has all definitions used throughout the whole API
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Dict, Union, List, Tuple, Optional, Any, Sequence
import numpy as np
import numpy.typing as npt

# Only C convertable types allowed, since this will be used in C

# enum classes are obviously all enums
class Hand(IntEnum):
    LEFT = 0
    RIGHT = 1

class Finger(IntEnum):
    THUMB  = 0
    INDEX  = 1
    MIDDLE = 2
    RING   = 3
    PINKY  = 4


class ErrorTypeDevice(IntEnum):
    FOUND    = 0
    NOTFOUND = 1

class DeviceType(Enum):
    REMBRANDT = "rembrandt"

class Com_type(Enum):
    UNIT_TEST = "unit_test"
    SIMULATED_GLOVE = "simulated_glove: customize from SG_main.SG_sim" 
    REAL_GLOVE_USB = "raw_usb: default rembrandt communication"


class Data_Origin(Enum):
    CPP_SDK = "DATA_BUFFER" # also for CPP API
    LIVE_TEST_SIM = "LIVE_TEST_SIM"
    
class Control_Mode(IntEnum):
    FORCE_GOAL_DEFAULT  = 0
    """This is the default mode. The motors will try to reach the force goal set. Set the force goal to 0 to move freely."""
    OFF = 9999 
    """Motors will fully turn off, so also not move with your finger"""
    CALIBRATE_TRACKING_NEVER_EVER_USE = 42666 
    """DON'T EVER SEND THIS TO THE GLOVE, it will reset tracking offset angles. It will ruin it the glove for good and requires customer support to fix it."""


    



# currently not distinguishing between encoding type to the buffer and encoding type from firmware.
# maybe in the future
class Encoding_type(Enum):
    REMBRANDT_v01 = "rembrandt_v01"


# for what linkage dimension is, see exo_dimensions.py
class Exo_linkage_type(Enum):
    REMBRANDT_PROTO_02 = "rembrandt_linkage_v02"
    REMBRANDT_PROTO_03 = "rembrandt_linkage_v03"
    REMBRANDT_PROTO_04 = "rembrandt_linkage_v04"
    REMBRANDT_PROTO_05 = "rembrandt_linkage_v05"




@dataclass
class Device_Info:
     device_id : int
     hand : Hand
     nr_fingers_tracking : int
     nr_fingers_force : int
     firmware_version : str
     device_type : DeviceType
     communication_type: Com_type
     exo_linkage_type : Exo_linkage_type
     encoding_type : Encoding_type
     data_origin : Data_Origin


# Type definitions for data structures
# Accepts both Python types (list/tuple) and NumPy arrays for API compatibility
Vec3_type = Sequence[Union[int, float]]# Python list/tuple

"""List, tuple, or np array of 3 numbers: x, y, z"""          

Quat_type = Sequence[Union[int, float]] # Python list/tuple/numpy
"""List, tuple, or np array of 4 numbers: w, x, y, z"""

@dataclass
class Thimble_dims:
    """
    To draw the users fingertip thimble, we use a sphere and a cilinder. These are the dimensions of the sphere and cilinder.
    """
    sphere_center_pos: Vec3_type
    rot: Quat_type
    radius: float
    cylinder_center_pos: Vec3_type
    cylinder_length: float




# -------------------firmware sends int, convert to type functions -----------------

code_to_linkage_type : Dict[int, Exo_linkage_type] = { 
    2 : Exo_linkage_type.REMBRANDT_PROTO_02,
    3 : Exo_linkage_type.REMBRANDT_PROTO_03,
    4 : Exo_linkage_type.REMBRANDT_PROTO_04
}


def linkage_type_from_nr(linkage_config_code : int):
    return code_to_linkage_type[linkage_config_code]


code_to_device_type : Dict[int, DeviceType] = { 66 : DeviceType.REMBRANDT }
def device_type_from_nr(device_type_code : int):
    return code_to_device_type[device_type_code]

"""
SG_main contains all functions the user needs from the API. See Getting Started docs for a general explanation of how to use it.

Questions? Written by:

- Amber Elferink

Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/

"""

import numpy as np
import warnings
from typing import Any, List, Tuple, Callable, Optional
import numpy.typing as npt
from datetime import datetime
import sys
import traceback
import signal
import time
from typing import Dict, Sequence, Union

from SG_API import SG_RB_buffer, SG_math
from SG_API import SG_devices

from SG_API import SG_simulator as SG_sim
from SG_API import SG_exo_dimensions as SG_exo
from SG_API import SG_callback_manager as SG_cb
from SG_API import SG_types as SG_T
from SG_API import SG_recorder
from SG_API import SG_timer
from SG_API.SG_robot_hand_mapper import RobotHandMapper, PinchConfig
# PinchMapperGUI imported lazily in create_rhm_pinch_gui() to avoid GUI dependencies in testing
from SG_API.SG_logger import sg_logger



# main file, C compatible language to communicate with API (no class objects passed by returns/parameters)

# this class contains the C++ and user friendly layer. This will transition through a user non-friendly C layer to pass language barriers. Basically the same class will exist behind the C layer again. 
# The functions below it are the C layer that will exist and translate that.




#  --------------- Init, ALWAYS CALL AT START OF PROGRAM ---------------
def init(wait_for_x_gloves : int, com_type : SG_T.Com_type, SIMULATION_MODE : SG_sim.Simulation_Mode = SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE) -> List[int]:
    """
    Initializes the API and connection searching. 
    
    If wait_for_x_gloves is not 0, the program will not move on until it finds at least x gloves. Returns list of device_ids connected after init.
    
    If setting Com_type to SIMULATED_GLOVE it will generate a single right hand simulator. The movement can be set with the SIMULATION_MODE parameter (which is not used when the REAL glove mod is on).
    
    **Examples:**
    ```python
    device_ids = SG_main.init(1, SG_T.Com_type.REAL_GLOVE_USB)  # Block program until 1 glove connects
    device_ids = SG_main.init(2, SG_T.Com_type.REAL_GLOVE_USB)  # Block program until 2 gloves connect
    device_ids = SG_main.init(1, SG_T.Com_type.SIMULATED_GLOVE)  # Simulate 1 glove (max 1 simulated glove via this init, create more with init_rembrandt_sim())
    device_ids = SG_main.init(0, SG_T.Com_type.REAL_GLOVE_USB)  # Doesn't block the program, may return no device_ids. 
    ```
    If you choose to set it to 0, you can use the `add_on_connected_callback()` function to capture the device_id on connection, or retrieve the device_ids with `get_device_ids()`, `get_right_hand_deviceid()`, `get_left_hand_deviceid()` after a connection.
    """
    SG_cb.running = True

    #Logging
    sg_logger.enable_file_logging(datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "-SG_API.log")
    sg_logger.set_console_level(sg_logger.WARNING)

    def log_uncaught_exceptions(exctype, value, tb):
        tb_str = ''.join(traceback.format_exception(exctype, value, tb))
        sg_logger.log("Uncaught exception:\n", tb_str, level=sg_logger.CRITICAL)
        
    sys.excepthook = log_uncaught_exceptions


    sg_logger.log("Waiting for glove to connect...", level=sg_logger.USER_INFO)

    SG_devices.initiate_add_device_on_connection(com_type)
    if com_type == SG_T.Com_type.SIMULATED_GLOVE:
        init_rembrandt_sim(SG_T.Hand.RIGHT, SIMULATION_MODE)
    if com_type == SG_T.Com_type.SIMULATED_GLOVE and wait_for_x_gloves > 1:
        init_rembrandt_sim(SG_T.Hand.LEFT,  SIMULATION_MODE)


    SG_cb.on_high_freq_loop_callback_manager.add(_update)
    SG_cb.init_high_freq_timer()

    while(len(get_device_ids()) < wait_for_x_gloves):
        if SG_cb.device_connected_event.is_set() == False:
            sg_logger.log("Blocking program until", wait_for_x_gloves, "gloves connected. If you want the program to continue despite not having a connected glove, instead call SG_main.init(wait_for_x_gloves = 0), or set to SIMULATED_GLOVE.", level=sg_logger.USER_INFO)          
        SG_cb.device_connected_event.wait() # it will hang on here until it has a connection to a glove.
        SG_cb.device_connected_event.clear()        

    sg_logger.log("Unblocked waiting for glove.", level=sg_logger.USER_INFO)


    
    device_ids = get_device_ids()
    sg_logger.info("Initiated Device ids: " + str(device_ids))
    if len(device_ids) == 0:
        sg_logger.warn("No glove device initialized! Call SG_main.init(1) to make sure it always has 1 glove before here.")
    return device_ids


       

def init_rembrandt_sim(handedness : SG_T.Hand, simulation_mode: SG_sim.Simulation_Mode, starting_angles = [0.0, -0.2617993877991494, 0.7853981633974483, -1.5707963267948966, 2.0943951023931953, -1.7453292519943295, 1.5707963267948966, 0.7]) -> Optional[SG_sim.Glove_Simulator]:
    """
    Creates a simulated hand to test without physical Rembrandt glove. For more options directly create it via SG_sim.create_glove_sim_device(). Currently does max 2 gloves from this function. A right and a left one.
    
    Examples:
    ```python
    right_sim = SG_main.init_rembrandt_sim(SG_T.Hand.RIGHT, SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
    left_sim = SG_main.init_rembrandt_sim(SG_T.Hand.LEFT, SG_sim.Simulation_Mode.STATIC)
    ```
    """
    #TODO: This currently only supports one LEFT and one RIGHT glove (id 0 and 1). So to fix that make this a loop that increases device_id if not odd/even for handedness AND not present in current get_device_ids(). Use that device_id to make the glove. 
    device_id = 9998
    if handedness == SG_T.Hand.RIGHT:  device_id = 9999
    if handedness == SG_T.Hand.LEFT:  device_id = 9998

    device_info = SG_T.Device_Info(
        device_id=device_id,
        hand=handedness,
        nr_fingers_tracking=5,
        nr_fingers_force=4,
        firmware_version="0.0.0-sim",
        device_type=SG_T.DeviceType.REMBRANDT,
        communication_type=SG_T.Com_type.SIMULATED_GLOVE,
        exo_linkage_type=SG_T.Exo_linkage_type.REMBRANDT_PROTO_04,
        encoding_type=SG_T.Encoding_type.REMBRANDT_v01,
        data_origin=SG_T.Data_Origin.LIVE_TEST_SIM
    )
    glove_sim = SG_sim.create_glove_sim_device(device_info, simulation_mode)
    return glove_sim
    # final link orientation seems to be stupid. TODO!!

def get_COM_type(device_id: int) -> SG_T.Com_type:
    """
    Returns the communication type of the specified device.
    Use:
    ```python
    com_type = SG_main.get_COM_type(device_id)
    ```
    
    Examples:
    ```python
    com_type = SG_main.get_COM_type(12345)  # SG_T.Com_type.REAL_GLOVE_USB or SG_T.Com_type.SIMULATED_GLOVE
    ```
    """
    return SG_devices.get_device(device_id).communication_type


# ----------------- Update, This is called by the high_freq_update_callback. Updates INCOMING DATA FOR PROTOCOLS THAT USE POLLING (such as livesim or python serial) ----------
def _update():
    """
    Refreshes incoming data for simulation and polling functions. Automatically called by the update_callback (subscribed from init).
    
    Preferably run this >1kHz. In the API version of July 2025 (current), this does not impact the real glove, but only simulation.

    ```python
    while True:
        SG_main.update()
        time.sleep(0.001)
        # your main loop code
    ```

        
    > ⚠️ **Important Note**
    >
    > Add the `time.sleep(0.001)` or it will eat up all the CPU, not allowing the real glove to update the callback at 1kHz!
    
    """
    if SG_cb.running:
        SG_sim.update_all_glove_sims()
        SG_recorder.update() 



def keep_program_running():
    """
    This is a while true loop with a sleep and exit check. 
    Exits cleanly on Ctrl+C, window close, or stop_program_running()

    > ⚠️ **Important Notes**
    
    > 1. Code after this call will NOT execute until exit
    > 2. Use this instead of a custom while loop to avoid performance issues with 1000hz glove data (subscr_rembrandt_data_callback)


    Usage:
    ```python
    SG_main.subscr_rembrandt_data_callback(on_new_data)
    SG_main.keep_program_running()
    # code here won't execute until exit
    ```

    How it's implemented (for reference):
    ```python
    def keep_program_running():
        try:
            while SG_main.SG_cb.running:
                time.sleep(1)  # This loop does not do anything but keep the program alive. Some sleep is important to not eat all CPU capacity.
        except: 
            pass # important errors will still log due to sg_logger. This try/except just ignores the keyboard interrupt error on Ctrl+C.
    ```

    If you use your own while loop instead (without the sleep), that may steal all CPU capacity, and the data callback will not be called often, which can result in only 70fps glove data update rate in bad cases.
    
    So if you use your own while loop, make sure to add the sleep, and preferably the shutdown check for clean exit.
    """
    try:
        while SG_cb.running:
            time.sleep(1)  # Sleep 1 second at a time, check if still running. Sleep is important to not eat all CPU capacity.
    except:
        pass

# ----------------- Device ID/specific device info retrieval -----------

def is_device_active(device_id: int) -> bool:
    """
    Checks if a device with given device_id is currently active/connected.
    Use:
    ```python
    is_active = SG_main.is_device_active(device_id)
    ```
    """
    device = SG_devices.get_device(device_id)
    if device == None:
        return False
    else:
        return True

def get_device_ids() -> List[int]:
    """
    Returns list with device_ids of all active devices.  

    Examples:
    ```python
    device_ids = SG_main.get_device_ids()  # [123, 678] - two gloves connected
    ```
    """
    return SG_devices.get_deviceIds()


def get_right_hand_deviceid() -> Optional[int]:
    """
    Returns the first right hand device_id found in active devices.
    Use:
    ```
    right_id = SG_main.get_right_hand_deviceid() #returns device_id, or None if no right hand
    ```
    """
    return SG_devices.hand_to_id(SG_T.Hand.RIGHT)
    

def get_left_hand_deviceid() -> Optional[int]:
    """
    Returns the first left hand device_id found in active devices.

    Examples:

    ```python
    left_id = SG_main.get_left_hand_deviceid()  # returns device_id or None if no left hand
    ```
    """
    return SG_devices.hand_to_id(SG_T.Hand.LEFT)

def is_left_hand(device_id: int):
    """
    Checks if a device is left handed. Returns True for left hand, False for right hand.
    
    ```python
    is_left = SG_main.is_left_hand(device_id)
    ```
    """
    if SG_devices.get_device(device_id).handedness == SG_T.Hand.LEFT:
        return True
    else:
        return False

def get_handedness(device_id: int) -> SG_T.Hand:
    """
    Returns the handedness (left or right) of the specified device.
    
    ```python
    handedness = SG_main.get_handedness(device_id)   # SG_T.Hand.LEFT or SG_T.Hand.RIGHT
    ```

    """
    return SG_devices.get_rembrandt_device(device_id).get_handedness()

def nr_of_fingers_tracking(device_id: int):
    """
    Returns the number of fingers supported by the device for tracking.
    Use:
    ```python
    finger_count = SG_main.nr_of_fingers_tracking(device_id)
    ```
    """
    return SG_devices.get_rembrandt_device(device_id).nr_of_fingers_tracking()

def nr_of_fingers_force(device_id: int):
    """
    Returns the number of fingers supported by the device for force feedback.
    Use:
    ```python
    finger_count = SG_main.nr_of_fingers_force(device_id)
    ```
    """
    return SG_devices.get_rembrandt_device(device_id).nr_of_fingers_force()

# ------------------------ Obtaining tracking data -------------------------

# ------------------------ CALLBACK BASED ---------------------------------------------
def subscr_r1_data_callback(cb : Callable[[int], None]):
    """
    Expects a callback function that takes device_id as a parameter. 
    
    That function will trigger if new data is available for the Rembrandt device.
    Within your function, call other API functions to retrieve specific data.


    > ⚠️ **Important Note**
    >
    > Do not put too heavy computing into this callback, since it will slow down the update rate of data retrieval from the glove, which must remain ~1kHz for optimal haptic performance. Preferably only place data into variables here.
    
    ```python
    # on_new_data will be called when new data is available for the Rembrandt device
    def on_new_data(device_id): 
        angles = SG_main.get_exo_angles_rad(device_id)
        
    SG_main.add_r1_data_callback(on_new_data)  # subscribes on_new_data to be called
    ```
    """
    SG_cb.on_new_rembrandt_data.add(cb)

def subscr_on_connected_callback(cb : Callable[[SG_T.Device_Info], None]):
    """
    Expects a callback function that takes SG_types.Device_Info as a parameter. 
    
    That function will trigger if a new device is connected.
    Within your function, call other API functions to retrieve specific data.

    You can add the following code even before the SG_main.init() call to make sure you capture the connection..
    ```python
    def on_new_device(device_info):
        print(f"New device connected: {device_info.device_id}")
    SG_main.add_on_connected_callback(on_new_device)
    ```
    """
    SG_cb.on_connected_callback_manager.add(cb)

# ------------------------ POLLING BASED ------------------------------------------------
# Note: The Qt GUI will not animate with a while loop running in the main thread. And threats in python perform horribly. So use callback based if you need our GUI.

def get_exo_angles_rad(device_id: int) -> Sequence[Sequence[float]]:
    """
    Retrieves exoskeleton joint angles in radians.
    
    ```python
    exo_angles = SG_main.get_exo_angles_rad(device_id)
    ```
    
    **Can be indexed like:**
    
    - ``exo_angle = exo_angles[finger_nr][exo_joint_nr]``

    **Angle definitions:** 
    
    - A fully extended straight exoskeleton gives all angles 0
    - Rotating a joint towards hand palm gives angle > 0
    - Rotating joint towards back of hand angle < 0 
    - The first angle is the splay angle. Those after are the flexion angles
    
    **Examples:**
    ```python
    thumb_splay_angle = exo_angles[0][0]  # thumb splay angle in radians
    index_flex1_angle = exo_angles[1][1]  # index finger 1st flexion in radians
    ```
    """
    rb_device = SG_devices.get_rembrandt_device(device_id)
    return rb_device.get_exo_angles_rad()

def get_device_info(device_id: int) -> SG_T.Device_Info:
    """
    Returns the device info (such as firmware version, nr_fingers, handedness, etc) for the specified device.
    Use:
    ```python
    device_info = SG_main.get_device_info(device_id)
    ```
    """
    return SG_devices.get_rembrandt_device(device_id).get_device_info()

def get_exo_angles_deg(device_id: int) -> Sequence[Sequence[float]]:
    """
    Retrieves exoskeleton joint angles in degrees (same as get_exo_angles_rad but degrees).
    Use:
    ```python
    exo_angles = SG_main.get_exo_angles_deg(device_id)
    ```
    
    Examples:
    ```python
    thumb_splay_deg = exo_angles[0][0]  # thumb splay angle in degrees
    index_flex1_angle = exo_angles[1][1]  # index finger 1st flexion in degrees
    ```
    """
    rb_device = SG_devices.get_rembrandt_device(device_id)
    return rb_device.get_exo_angles_deg()

def get_exo_linkage_lengths(device_id: int) -> Sequence[Sequence[Union[int, float]]]:
    """
    Returns the linkage lengths of the exoskeleton for the specified device in mm.
    Use:
    ```python
    linkage_lengths = SG_main.get_exo_linkage_lengths(device_id) # [11.62, 35, 35, 35, 35, 35, 35, 10] # in mm
    ```
    """
    device = SG_devices.get_rembrandt_device(device_id)
    return SG_exo.get_linkage_lengths(device._device_info)

def get_fingertips_pos_rot(device_id: int) -> Tuple[Sequence[SG_T.Vec3_type], Sequence[SG_T.Quat_type]]:
    """
    Returns tuple of positions (x,y,z) and rotations (quat) of each fingertip with respect to the finger base origin. See tracking documentation for more info.
    
    ```python
    fingertips_pos, fingertips_rot = SG_main.get_fingertips_pos_rot(device_id)
    ```
    
    **Can be indexed like:**
    
    - `fingertip_pos_xyz = fingertips_pos[finger_nr][xyz_index]`
    - `fingertip_rot_quat = fingertips_rot[finger_nr][quat_wxyz_index]`
    
    **Examples:**
    ```python
    thumb_pos_x = fingertips_pos[0][0]  # thumb x position
    index_rot_w = fingertips_rot[1][0]  # index finger quaternion w
    ```
    """
    poss, rots = SG_devices.get_rembrandt_device(device_id).get_fingertips_pos_rot()
    return poss, rots

def get_fingertip_thimble_dims(device_id: int) -> List[SG_T.Thimble_dims]:
    """
    Returns thimble dimensions info for each fingertip to approximate its drawing with sphere and a cylinder. See SG_types.Thimble_dims for more info.
    ```python
    thimble_dims = SG_main.get_fingertip_thimble_dims(device_id)
    ```
    
    **Example:**
    ```python
    thumb_dims = thimble_dims[0].radius  # thumb thimble radius
    ```
    """
    return SG_devices.get_rembrandt_device(device_id).get_fingertip_thimble_dims()


def get_fingertip_distances(device_id: int) -> Sequence[float]:
    """
    returns: fingertip distances between thumb and [index, middle, ring, pinky] (float in mm)
    """
    return SG_devices.get_rembrandt_device(device_id).get_fingertip_distances()

# 
def get_exo_joints_poss_rots(device_id: int) -> Tuple[Sequence[Sequence[SG_T.Vec3_type]], Sequence[Sequence[SG_T.Quat_type]]]:
    """
    Returns tuple of positions (x,y,z) and rotations (quat) of each exoskeleton joint.
    Use: 
    ```python
    exo_poss, exo_rot = SG_main.get_exo_joints_poss_rots(hand_id)
    ```
    Can be indexed like: 
    - `joint_pos_xyz = exo_poss[finger_nr][exo_joint_nr][xyz_index]`
    - `joint_rot_quat = exo_rot[finger_nr][exo_joint_nr][quat_wxyz_index]`

    **Examples:**
    ```python
    thumb_flexion_1_z: exo_poss[0][1][2] # thumb 1st flexion joint z
    middlefinger_splay_y: exo_poss[2][0][1] # middle finger splay joint y
    ```
    """
    return SG_devices.get_rembrandt_device(device_id).get_exo_joints_poss_rots()


def get_percentage_bents(device_id: int) -> Tuple[SG_T.Sequence[int], SG_T.Sequence[int]]:
    """
    Returns percentage bent values for flexion and abduction of each finger.
    
    Returns tuple containing:
    
    - **flexion_perc_bents**: Array of flexion percentages (0-out_max_perc_bent, 10000 by default)
    - **abduction_perc_bents**: Array of abduction percentages (0-out_max_perc_bent, 10000 by default)
    
    ```python
    flex_bents, abd_bents = SG_main.get_percentage_bents(device_id)
    ```
    
    **Can be indexed like:**
    
    - `finger_flex_bent = flex_bents[finger_nr]`
    - `finger_abd_bent = abd_bents[finger_nr]`
    
    **Examples:**
    ```python
    thumb_flex_bent = flex_bents[0]  # 0 (open) to 10000 (closed)
    thumb_abd_bent = abd_bents[0]    # 0 (in plane with palm) to 10000 (maximally radially extended)
    index_abd_bent = abd_bents[1]    # 0 abducted to y, 5000 (neutral) to 10000 (abducted to the -y)
    ```

    **Notes:**
    
    - Values range from 0 (finger open) to out_max_perc_bent (finger closed)
    - **For the thumb:**
        - Flexion: 0 = extended, out_max_perc_bent = fully flexed
        - Abduction: 0 = in plane with palm, out_max_perc_bent = maximally radially extended
    - **For other fingers:**
        - Flexion: 0 = extended, out_max_perc_bent = fully flexed
        - Abduction: 0 = neutral, out_max_perc_bent = maximally abducted

    **Other notes:**
    
    - 10000 is used by default instead of 100 to avoid floating point inaccuracies
    - It calculates this based on the fingertip orientation with respect to the finger base orientation
    - This method is used because it's independent of user hand sizes, and requires no calibration
    - Use set_perc_bent_vars() to change the max perc bent values to control and how 0 and 10000 are mapped to the raw values (from raw_percentage_bent_angles())
    """
    result =  SG_devices.get_rembrandt_device(device_id).get_percentage_bents()
    return result


def get_raw_percentage_bent_angles(device_id: int) -> Tuple[SG_T.Sequence[float], SG_T.Sequence[float]]:
    """
    Returns the raw flexion and abduction angles used to calculate percentage bent.
    Returns: (flex_angles, abd_angles)
    Each is an array of the fingers, containing the raw angles in radians. See the tracking documentation for more info.
    Use:
    ```python
    flex_angles, abd_angles = SG_main.get_raw_percentage_bent_angles(device_id)
    ```
    Can be indexed like:
    - `finger_flex_angle = flex_angles[finger_nr]`
    - `finger_abd_angle = abd_angles[finger_nr]`
    
    Examples:
    ```python
    thumb_flex = flex_angles[0]  # thumb flexion angle in radians
    index_abd = abd_angles[1]   # index abduction angle in radians
    ```
    """
    rb_device = SG_devices.get_rembrandt_device(device_id)
    return rb_device.get_raw_percentage_bent_angles()



def set_percentage_bent_vars(device_id: int,        
        min_thetas_flexion: npt.NDArray[np.float64] = np.array([0, 0.524, 0.345, 0.414, 0.4]), 
        max_thetas_flexion: npt.NDArray[np.float64] = np.array([1.8, 3.265, 3.00, 3.00, 2.75]), 
        min_thetas_abduction: npt.NDArray[np.float64] = np.array([0.0, -0.3, -0.3, -0.3, -0.3]), 
        max_thetas_abduction: npt.NDArray[np.float64] = np.array([0.5, 0.3, 0.3, 0.3, 0.3]), 
        out_max_perc_bent: int = 10000):
    """
    Sets the variables used to calculate percentage bent values.
    With this you can override when a finger is considered bent or open:
    
    **Steps:**
    
    1. Monitor your values from get_raw_percentage_bent_angles()
    2. Move your fingers and note down the values per finger of your desired bent and open
    3. Set the min and max values to the values you noted down on startup of your program, just after init()
    
    **Example:**
    ```python
    device_ids = SG_main.init(1, SG_T.Com_type.REAL_GLOVE_USB)
    device_id = device_ids[0]
    SG_main.set_percentage_bent_vars(device_id, 
        min_flex = [0.23, -0.27, -0.27, -0.27, 0.1], 
        max_flex = [1.00, 2.75, 2.75, 2.75, 2.75], 
        min_abd = [0.04, -0.18, -0.27, -0.27, 0.1], 
        max_abd = [0.6, 0.18, 0.27, 0.27, 0.1])

    # using SG_main.get_percentage_bents(device_id) you can now see the adjusted percentage bent values for each finger.
    ```
    """
    rb_device = SG_devices.get_rembrandt_device(device_id)
    rb_device.set_percentage_bent_vars(min_thetas_flexion, max_thetas_flexion, min_thetas_abduction, max_thetas_abduction, out_max_perc_bent)

_robot_mappers : Dict[int, RobotHandMapper] = {}
def create_robot_hand_mapper(device_id: int, config: Optional[PinchConfig] = None) -> RobotHandMapper:
    """
    Create and return a RobotHandMapper instance.
    If no config is provided, the default pinch mapping config is used.

    Args:
        device_id: Rembrandt device ID
        config: Optional custom PinchConfig

    Returns:
        Configured RobotHandMapper instance
    """
    if config is None:
        mapper = RobotHandMapper(device_id)
    else:
        mapper = RobotHandMapper(device_id, config)
    _robot_mappers[device_id] = mapper
    return mapper

def get_robot_hand_mapper(device_id: int) -> RobotHandMapper:
    """
    Return the RobotHandMapper instance for the specified device.
    If no config is provided, the default pinch mapping config is used.

    Args:
        device_id: Rembrandt device ID

    Returns:
        Configured RobotHandMapper instance
    """
    mapper = _robot_mappers.get(device_id)
    
    if mapper is None:
        sg_logger.warn(f"No RobotHandMapper registered for device {device_id}.")
        raise RuntimeError(f"No RobotHandMapper registered for device {device_id}.")

    return mapper

def create_rhm_pinch_gui(device_id: int):
    """
    Create and register a PinchMapperGUI for the given device_id.
    """
    from SG_API.SG_robot_pinch_gui import PinchMapperGUI

    mapper = get_robot_hand_mapper(device_id)
    pinch_gui = PinchMapperGUI(mapper)
    _robot_mappers[device_id].register_gui(pinch_gui)
    return pinch_gui


def get_pinch_debug_info(device_id: int):
    """
    Retrieve pinch-config debug info from the RobotHandMapper.
    Returns pinch diagnostics as dictionary.

    Args:
        device_id: Rembrandt device ID
    """
    mapper = _robot_mappers.get(device_id)
    
    if mapper is None:
        sg_logger.warn(f"No RobotHandMapper registered for device {device_id}.")
        raise RuntimeError(f"No RobotHandMapper registered for device {device_id}.")

    try:
        debug_info = mapper.get_pinch_debug_info()
        return debug_info
    except Exception as e:
        sg_logger.warn(f"Failed to retrieve pinch debug info for device {device_id}: {e}")
        raise

def get_rhm_percentage_bents(device_id: int) -> Tuple[SG_T.Sequence[Union[int, float]], SG_T.Sequence[Union[int, float]]]:
    """
    Retrieve robot-mapped percentage flexion and abduction values (pinch mapping).

    Args:
        device_id: Rembrandt device ID

    Returns:
        tuple: (robot_flex, robot_abd)
    """
    mapper = _robot_mappers.get(device_id)

    if mapper is None:
        sg_logger.warn(f"No RobotHandMapper registered for device {device_id}.")
        raise RuntimeError(f"No RobotHandMapper registered for device {device_id}.")
    
    try:
        return mapper.get_rhm_percentage_bents()
    except Exception as e:
        sg_logger.warn(f"Failed to retrieve pinch data for device {device_id}: {e}")
        raise

def update_robot_hand_mapper_gui(device_id: int):
    """
    Update the RHM GUI

    Args:
        device_id: Rembrandt device ID
    """
    mapper = _robot_mappers.get(device_id)
    if mapper is None:
        sg_logger.warn(f"No RobotHandMapper registered for device {device_id}.")
        raise RuntimeError(f"No RobotHandMapper registered for device {device_id}.")

    gui = getattr(mapper, "_gui", None)
    if gui is None:
        sg_logger.warn(f"No GUI registered for RobotHandMapper (device {device_id}).")
        return

    try:
        mapper.update_mapper_gui()
    except Exception as e:
        sg_logger.warn(f"Failed to update RobotHandMapper GUI for device {device_id}: {e}")




############## TODO:

#def set_fingertip_offset_pos_rot(device_id, finger)
#def get_fingertip_offset_pos_rot(device_id, finger)


########################### FORCES ----------------------------------------------


def get_forces_sensed(device_id: int) -> SG_T.Sequence[Union[int, float]]:
    """
    Returns the currently sensed forces for each finger.
    Use:
    ```python
    forces = SG_main.get_forces_sensed(device_id)
    ```
    Can be indexed like:
    - `finger_force = forces[finger_nr]`
    
    Examples:
    ```python
    thumb_force = forces[0]  # thumb sensed force
    index_force = forces[1]  # index finger sensed force
    ```
    """
    rb_device = SG_devices.get_rembrandt_device(device_id)
    return rb_device.get_forces_sensed()


def set_force_goals(device_id: int, force_goals : SG_T.Sequence[Union[int, float]]):
    """
    Sets force goals for each finger (thumb to ringfinger) in milliNewtons. Note: pinky has no force module
    
    > ⚠️ **Development Status**
    >
    > The resulting force on the wire might differ from the force goal requested to allow stable control. Scale up the forces if necessary.
    > The milliNewtons is the tension in the wire pulling the finger back.

    > ⚠️ **Warning for motor jitter**
    >
    > Do not use `if contact -> set force_goal to full force` logic, since that is not stable around the contact point. Instead, use: `force_goal = K * distance_to_contact` or another gradual function, tuning K to stability.
    
    **Use:**
    ```python
    force_goals = [3000, 3000, 3000, 3000]  # forces in mN per finger thumb to ring. 
    SG_main.set_force_goals(device_id, force_goals)
    ```

    **Parameters:**
    - **force_goals**: List of force goals per finger

    **Troubleshooting jittering:**
    - If you notice jittering, plot your input data (easy with Teleplot extension VScode).
    - Check sudden force goal changes you command, improve data FPS, reduce K or in another way transition force goals more gradually. 
    - Note that filtering/averaging your data too much can cause delays, which can cause instable feedback loops as result!
    

    """

    rb_device = SG_devices.get_rembrandt_device(device_id)
    rb_device.set_force_goals(force_goals)


def set_force_goals_with_control_mode(device_id: int, force_goals : SG_T.Sequence[Union[int, float]], control_modes : Optional[Sequence[SG_T.Control_Mode]]):
    rb_device = SG_devices.get_rembrandt_device(device_id)
    rb_device.set_force_goals_with_control_mode(force_goals, control_modes)
    
 

def set_raw_vibro_data(device_id: int, vibro_data : Sequence[Sequence[int]]):
    """
    Sets vibration data for the specified device.
    
    Parameters:
    - device_id: ID of the device
    - vibro_data: List of vibration data per actuator.

    Still in development. See examples/vibration_example.py for an example of the current format.
    """
    device = SG_devices.get_rembrandt_device(device_id)
    device.set_vibro_data(vibro_data)


# ----------------- Exit -----------------


def exit():
    """
    Closes all connections and cleans up resources. This is AUTOMATICALLY CALLED by the atexit module. (no need to manually call this)
    
    ```python
    SG_main.exit()
    ```
    """
    SG_sim.stop_all_glove_sims()
    #TODO: stop_glove_data_exchanges, with in there stop_glove_sim, but also set force back to free mode, and no longer wanting to receive cb bool
    SG_devices.close_devices() # first this to send final zero value haptic data
    SG_cb.close() #then this to prevent callbacks
    SG_RB_buffer.clear_buffers()
    sg_logger.log("Exited and Closed SenseGlove API", level=sg_logger.USER_INFO)
    SG_cb.running = False



import atexit
atexit.register(exit)
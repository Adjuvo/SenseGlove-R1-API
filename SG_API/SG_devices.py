"""
This class holds the internal state and callable functions for each device.
Thereby it has general functions to manage all devices, such as adding and removing devices, and updating the data of each device.

Questions? Written by:
- Amber Elferink
- Max Lammers: Percentage bent 
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""


from .SG_logger import sg_logger

from . import SG_types as SG_T
from datetime import datetime

from . import SG_rembrandt_data 
from . import SG_math as SG_math
from . import SG_exo_dimensions
from . import SG_RB_buffer
from . import SG_simulator as SG_sim
from . import SG_callback_manager as SG_cb
from . import SG_FPS

from . import SG_data_exchange as SG_data
from . import SG_median_filter

import math
import numpy as np
import numpy.typing as npt
import copy

from typing import List, Dict, Tuple, Sequence, Union, Optional

# For now, this will be the way users interface with devices.
# But eventually it is the idea that this is only internal (in C++), and then only accessed through the C layer
# this internal C++ layer is called.
# then behind the C layer, a similar class layout as this is built up again (in any language, python or C++), using those C layer functions internally

# TODO: handle removing device from the _active_devices list if no longer used. Also stop the connection first and destroy the connection

# TODO: PUT Device types everywhere

class SG_IDevice_Internal:
    def __init__(self, id, handedness : SG_T.Hand, firmware_version, device_type : SG_T.DeviceType, communication_type : SG_T.Com_type, buffer : SG_RB_buffer.RB_buffer):
        self._device_id = id
        self.device_type = device_type
        self.handedness = handedness
        self.firmware_version = firmware_version
        self.communication_type = communication_type
        self.buffers = buffer

        

_active_deviceIds : List[int] = []
_active_devices : List[SG_IDevice_Internal] = []
_shutdown_in_progress = False



# device id to device
_device_dict  : Dict[int, SG_IDevice_Internal] = {}  


def normalize_angle_to_2pi(angle):
    """Normalize angle to range [-2π, 2π]"""
    angle = np.asarray(angle)
    return ((angle + 2*np.pi) % (4*np.pi)) - 2*np.pi

def wrap_to_pi(angle):
    """Wrap an angle in radians to the range [-π, π)."""
    #return (angle + math.pi) % (2 * math.pi) - math.pi
    if angle > math.pi: #toto; more refined...
        return (angle + math.pi) % (2 * math.pi) - math.pi
    elif angle < -math.pi:
        return (angle + math.pi) % (2 * math.pi) - math.pi
    return angle


# Wrapping all angles (that will be +/- 2Pi into the -60 to 300 range. Could possibly also be 0 .. 360 range.)
#defined here for efficiency
perc_b_low  = math.radians(-60)
perc_b_high = math.radians(300)
range_size = perc_b_high - perc_b_low  # full cycle. Should be 2Pi!
def wrap_angle_to_perc_range(angle):
    # Shift into [0, 2π) and add perc_b_low.
    angle = (angle - perc_b_low) % range_size + perc_b_low
    return angle


# this will be a child class of a glove interface in C++
# Do not make an instance of this yourself. Instead add_device should be called from the communication setup
class Rembrandt_Device_Internal(SG_IDevice_Internal):

    def __init__(self, device_info : SG_T.Device_Info):
        self.callback_fps_updated_data = SG_FPS.FPSCounter(1.0, "update_data_device_" + str(device_info.device_id) + " FPS", sg_logger.USER_INFO)
        self._device_id = device_info.device_id
        self._device_info = device_info

        # Create buffers first
        self.buffer = SG_RB_buffer.create_buffer(device_info)
        
        # Use the buffer's data as our main data instance (unified data structure)
        self._data = self.buffer.data
        SG_rembrandt_data.init_data_values(self._data)

        SG_IDevice_Internal.__init__(self, 
                                     id= self._device_id, 
                                     handedness=self.get_handedness(), 
                                     firmware_version= self._data.device_info.firmware_version, 
                                     device_type= SG_T.DeviceType.REMBRANDT, 
                                     communication_type=self._data.device_info.communication_type, 
                                     buffer=self.buffer)
        
        #TODO: also for rotations, preferably from the same function
        self._data.exo_joints_poss = SG_exo_dimensions.get_default_exo_poss(device_info)
        
        self.set_percentage_bent_vars()
        # Initialize median filter for exo_angles with default window size of 5
        self.exo_angles_median_filter = SG_median_filter.ExoAnglesMedianFilter(window_size=5)

        self.flex_angles = []
        self.abd_angles = []

    #def update_received_data(self):
        
        
        # if self.buffers.get_nr_packets_received() > 0:
        #     message = self.buffers.get_latest_received_message()
        #     self._data.exo_angles, self._data.forces_sensed = SG_transcode.rembrandt_v02.get_received_data(message) 

    # returns a dataclass (should be implemented as struct in C) of all data
    def get_all_data(self) -> SG_rembrandt_data.Rembrandt_v1_data:
        return self._data
    
    def get_exo_type(self) -> SG_T.Exo_linkage_type:
        return self._data.device_info.exo_linkage_type
    

    
    def update_data(self):
        # Get raw exo angles data
        raw_exo_angles = SG_data.get_exo_angles_rad(self._device_info)

        #print("SG_device-raw_exo_angles: " + sg_logger.nested_array_to_str(raw_exo_angles))

        # # Apply median filter to reduce noise
        if self.communication_type == SG_T.Com_type.SIMULATED_GLOVE:
            self._data.exo_angles_rad_filtered = raw_exo_angles
        elif self.communication_type == SG_T.Com_type.REAL_GLOVE_USB:
            self._data.exo_angles_rad_filtered = raw_exo_angles#self.exo_angles_median_filter.update(raw_exo_angles)
        
       # print("exo_angles_rad " + sg_logger.nested_array_to_str(self._data.exo_angles_rad))
        self._data.exo_joints_poss, self._data.exo_joint_rots = SG_exo_dimensions.get_exo_joints_poss_rots(self.get_exo_type(), self.handedness, self._data.exo_angles_rad_filtered)
        
        # # Calculate both world-space and local fingertip rotations
        self._data.fingertips_pos, self._data.fingertips_rot, self._data.fingertips_rot_local = SG_exo_dimensions.get_fingertips_pos_rot_with_local(self.get_exo_type(), self.handedness, (self._data.exo_joints_poss, self._data.exo_joint_rots))

        self._perc_bent_calc()

        self._data.forces_sensed = SG_data.get_force_sensors(self._device_info)
        SG_cb.on_new_rembrandt_data.call_all(self._device_id)
        #self.callback_fps_updated_data.update()

        if not _shutdown_in_progress:
            SG_data.send_haptic_data(self._device_info) # bundle latest vibro + force data and send to glove


    def get_exo_angles_rad(self) -> SG_T.Sequence[Sequence[Union[int, float]]]:
        """
        returns: [[]]. outer array: 5 fingers, thumb to pinky. #inner array: 8 angles of the exoskeleton in radians (note the first one is perpendicular, for finger splay), proximal to distal
        """
        return self._data.exo_angles_rad
    
    def get_exo_angles_deg(self) -> SG_T.Sequence[Sequence[Union[int, float]]]:
        rads = self.get_exo_angles_rad()
        angles_deg = SG_math.to_clamped_degrees(rads)
        return angles_deg.tolist()
    
    
    def debug_median_filter(self, finger_idx: int = 0, angle_indices=None, verbose: bool = False):
        """
        Print debugging information for the median filter.
        
        Args:
            finger_idx (int): Index of finger to debug (0=thumb, 1=index, etc.)
            angle_indices (list, optional): Specific angle indices to print. If None, prints all.
            verbose (bool): If True, prints detailed info. If False, prints compact single-line format.
        
        Example usage:
            device.debug_median_filter(0, [4])  # Debug angle 4 for thumb (compact)
            device.debug_median_filter(0, [4], verbose=True)  # Debug angle 4 for thumb (detailed)
        """
        if verbose:
            self.exo_angles_median_filter.print_debug_info_verbose(finger_idx, angle_indices)
        else:
            self.exo_angles_median_filter.print_debug_info(finger_idx, angle_indices)
    
    # outer array: 5 fingers, thumb to pinky. Each 
    def get_forces_sensed(self) -> SG_T.Sequence[Union[int, float]]: 
        """
        returns: []. array: 5 fingers, thumb to pinky, with the force of each finger.
        """
        return self._data.forces_sensed
    
           
    
    #odd number is right, uneven is left
    def get_handedness(self) -> SG_T.Hand:
        return self._device_info.hand
    

    def nr_of_fingers_tracking(self):
        return self._device_info.nr_fingers_tracking

    def nr_of_fingers_force(self):
        return self._device_info.nr_fingers_force

    def get_finger_offsets(self) -> Tuple[List[SG_T.Vec3_type], List[SG_math.Quaternion]]:
        """
        Returns positional vec [x,y,z], rotational quat ([w,x,y,z]) offset of each finger
        Position is x, y of the first joint of the exoskeleton (splay), at the z where the next flexion joint is, relative to a base position in the hub."
        """
        return SG_exo_dimensions.get_finger_offsets(self.get_exo_type(), self.handedness)

    def get_fingertips_pos_rot(self):
        # TODO: make this cache the forward kinematics and only recalculate that on new data
        """
        returns: fingertip position (vec3), fingertip rotation (quat)
        """
        return self._data.fingertips_pos, self._data.fingertips_rot


    def get_fingertip_distances(self) -> Sequence[float]:
        """
        returns: fingertip distances between thumb and [index, middle, ring, pinky] (float in mm)
        Only calculates distances for fingers that are present for tracking.
        """
        np.array(self._data.fingertips_pos)
        
        nr_fingers = self.nr_of_fingers_tracking()
        distances = []
        
        # Calculate distances from thumb (index 0) to other fingers (indices 1 to nr_fingers-1)
        for finger_idx in range(1, nr_fingers):
            distances.append(SG_math.distance(self._data.fingertips_pos[0], self._data.fingertips_pos[finger_idx]))
        
        return distances
    
    def get_fingertip_thimble_dims(self):
        """
        returns: List of Thimble_dims for each finger
        """
        return SG_exo_dimensions.get_fingertip_thimble_dims(self.get_exo_type(), self.handedness, self._data.exo_joints_poss, (self._data.fingertips_pos, self._data.fingertips_rot))
    
    def get_exo_joints_poss_rots(self) -> Tuple[SG_T.Sequence[Sequence[SG_T.Vec3_type]], SG_T.Sequence[Sequence[SG_T.Quat_type]]]:
        """
        Returns tuple of positions (x,y,z) and rotations (quat) of each exoskeleton joint
        Call: 
        Can be indexed like: `[finger_nr][exo_joint_nr][xyz_index/quat_wxyz_index]`
        """
        return self._data.exo_joints_poss, self._data.exo_joint_rots
    

    def _get_percentage_bents_flat(self, fingertip_rots, min_angles, max_angles, axes):
        nr_fingers = len(fingertip_rots)
        zeros = np.zeros(nr_fingers, dtype=np.float64)

        angles = SG_math.batch_quat_to_axis_angle_optimized(fingertip_rots, axes)
        # print("angles", angles)
        # print("angles", angles)
        # print("min_angles", min_angles)
        # print("max_angles", max_angles)
        # print("self._out_max_perc_bents", self._out_max_perc_bents)
        percentage_bent =  SG_math.rescale(angles, min_angles, max_angles, zeros, self._out_max_perc_bents)
        percentage_bent = SG_math.clamp(percentage_bent, zeros, self._out_max_perc_bents)
        result =  (percentage_bent, angles)
        return result

    def set_percentage_bent_vars(self,   
        min_thetas_flexion: npt.NDArray[np.float64] = np.array([0, 0.524, 0.345, 0.414, 0.4]), 
        max_thetas_flexion: npt.NDArray[np.float64] = np.array([1.8, 3.265, 3.00, 3.00, 2.75]), 
        min_thetas_abduction: npt.NDArray[np.float64] = np.array([0.0, -0.3, -0.3, -0.3, -0.3]), 
        max_thetas_abduction: npt.NDArray[np.float64] = np.array([0.5, 0.3, 0.3, 0.3, 0.3]), 
        out_max_perc_bent: int = 10000) -> None:
        self._out_max_perc_bents = np.array([out_max_perc_bent] * self.nr_of_fingers_tracking())
        self._min_thetas_flexion = min_thetas_flexion
        self._max_thetas_flexion = max_thetas_flexion
        self._min_thetas_abduction = min_thetas_abduction
        self._max_thetas_abduction = max_thetas_abduction


    


    def set_force_goals_with_control_mode(self, force_goals : SG_T.Sequence[Union[int, float]], control_modes : Optional[Sequence[SG_T.Control_Mode]]):
        """
        Sets force goals for each finger.
        
        > ⚠️ **Development Status**
        >
        > This is still in development. For the final version it will be in Newtons. Right now it accepts between 0 and 800 (raw sensor values)

        **Use:**
        ```python
        force_goals = [100, 200, 150, 180, 120]  # forces per finger
        SG_main.set_force_goals(device_id, force_goals)
        ```

        **Parameters:**
        - **force_goals**: List of force goals per finger

        """
        # Input validation: Check if force_goals is a valid list-like type
        if not hasattr(force_goals, '__len__'):
            sg_logger.log("Invalid input type for force_goals. Expected list, numpy array, or single number, but got: " + str(type(force_goals)), level=sg_logger.CRITICAL)
            return
        
        if len(force_goals) < self.nr_of_fingers_force():
            sg_logger.log("Attempted to set force goals for " + str(len(force_goals)) + " fingers, but the device has " + str(self.nr_of_fingers_tracking()) + " fingers. Provide force goals for at least that many fingers.", level=sg_logger.CRITICAL)
            return

        modes = control_modes

        current_percentage_bent_flexion, _ = self.get_percentage_bents()
        current_percentage_bent_flexion_np = np.array(current_percentage_bent_flexion) * 6.5534 
        current_percentage_bent_flexion_np = SG_math.clamp(current_percentage_bent_flexion_np, 0, 65535)

        self._data.perc_bents_flexion_firmware = current_percentage_bent_flexion_np.astype(np.uint16).tolist()
        #forces_glove = force_goals + K * (from_percentage_bent - current_percentage_bent)
        self._data.force_goals = np.maximum(force_goals, 0).astype(np.uint16).tolist()

        self._data.control_modes = [int(mode) for mode in modes]
            

    def set_force_goals(self, force_goals : SG_T.Sequence[Union[int, float]]):
        """
        Sets force goals for each finger.
        
        > ⚠️ **Development Status**
        >
        > This is still in development. For the final version it will be in Newtons. Right now it accepts between 0 and 800 (raw sensor values)

        **Use:**
        ```python
        force_goals = [100, 200, 150, 180, 120]  # forces per finger
        SG_main.set_force_goals(device_id, force_goals)
        ```

        **Parameters:**
        - **force_goals**: List of force goals per finger

        """

        self.set_force_goals_with_control_mode(force_goals, [SG_T.Control_Mode.FORCE_GOAL_DEFAULT] * len(force_goals))

    def set_vibro_data(self, vibro_data):
        """
        Sets vibration data for the device.
        
        Parameters:
        - vibro_data: List of vibration data per actuator
        """
        self._data.raw_vibro_data = vibro_data


        

    def _perc_bent_calc(self):
        #2.10 max, 0.23 min for thumb

        simple_approach = True # set to true for the simple(st) approach.

        if simple_approach:

            # Simplest approach: 
            # - Abduction: direct from exo angles
            # - Flexion: direct from exo angles, summed.
            # Extract flexion angles by 'summing' all of the angles.
            nr_fingers = len(self._data.exo_angles_rad)
            
            flex_angles_from_fingertips = []
            for finger_idx in range(nr_fingers):
                finger_angles = np.array(self._data.exo_angles_rad[finger_idx], dtype=float)
                flexion_sum = 0
                for i in range(1, len(finger_angles)):
                    # flexion_sum += wrap_to_pi(finger_angles[i])
                    flexion_sum += finger_angles[i]
                flexion_sum -= math.pi/2 # now point the thimble forward
                
                flexion_sum = wrap_angle_to_perc_range(flexion_sum)
                flex_angles_from_fingertips.append(flexion_sum)
            
            #flex_angles_from_fingertips = [sum(sub[1:]) for sub in self._data.exo_angles_rad]
            #for finger_idx in range(nr_fingers):
            #    flex_angles_from_fingertips[finger_idx] -= math.pi/2 # subtract 90 degrees because, when all angles are at 0, the exo 

            #    testFloat = wrap_to_pi(flex_angles_from_fingertips[finger_idx])
            #    flex_angles_from_fingertips[finger_idx] = testFloat
            
            #todo: correct these for the '90 degrees' to bring it 'forward' again?

            # Extract abduction angles directly from exo joint angles (this works correctly)
            abd_angles_direct = []
            for finger_idx in range(nr_fingers):
                finger_angles = np.array(self._data.exo_angles_rad[finger_idx], dtype=float)
                if self.handedness == SG_T.Hand.LEFT:
                    finger_angles[0] = finger_angles[0] * -1
                    # finger_angles[0] = finger_angles[0] * -1

                elif self.handedness == SG_T.Hand.RIGHT:
                    finger_angles[0] = finger_angles[0]

                splay_angle = finger_angles[0]  # Index 0 is splay (abduction around Z)
                abd_angles_direct.append(splay_angle)
        else:
            # Hybrid approach: 
            # - Abduction: direct from exo angles (works well, no coupling)
            # - Flexion: from fingertip rotations (preserves original meaning)
            
            fingertip_rots_local = self._data.fingertips_rot_local #copy.deepcopy(self._data.fingertips_rot_local)
            nr_fingers = len(fingertip_rots_local)
            
            # Extract abduction angles directly from exo joint angles (this works correctly)
            abd_angles_direct = []
            for finger_idx in range(nr_fingers):
                finger_angles = np.array(self._data.exo_angles_rad[finger_idx], dtype=float)
                if self.handedness == SG_T.Hand.LEFT:
                    finger_angles[0] = finger_angles[0] * -1
                    # finger_angles[0] = finger_angles[0] * -1

                elif self.handedness == SG_T.Hand.RIGHT:
                    finger_angles[0] = finger_angles[0]

                splay_angle = finger_angles[0]  # Index 0 is splay (abduction around Z)
                abd_angles_direct.append(splay_angle)
            
            # Extract flexion angles from fingertip rotations (original approach)
            flexion_axes = [[0,1,0]]*nr_fingers # Y-axis for flexion
            _, flex_angles_from_fingertips = self._get_percentage_bents_flat(fingertip_rots_local, [0]*nr_fingers, [1]*nr_fingers, flexion_axes)
            

        # Truncate min/max theta arrays to match the number of fingers
        min_thetas_flexion = self._min_thetas_flexion[:nr_fingers]
        max_thetas_flexion = self._max_thetas_flexion[:nr_fingers]
        min_thetas_abduction = self._min_thetas_abduction[:nr_fingers]
        max_thetas_abduction = self._max_thetas_abduction[:nr_fingers]
        
        # Calculate percentage bent
        zeros = [0] * nr_fingers
        
        # Flexion from fingertip rotations
        flexion = SG_math.rescale(flex_angles_from_fingertips, min_thetas_flexion, max_thetas_flexion, zeros, self._out_max_perc_bents).tolist()
        self._data.perc_bents_flexion = SG_math.clamp(flexion, zeros, self._out_max_perc_bents).tolist()
        self.flex_angles = flex_angles_from_fingertips
        
        # Abduction from direct exo angles
        abductions = SG_math.rescale(abd_angles_direct, min_thetas_abduction, max_thetas_abduction, zeros, self._out_max_perc_bents)
        self._data.abd_perc_bents = SG_math.clamp(abductions, zeros, self._out_max_perc_bents).tolist()
        self.abd_angles = abd_angles_direct


    def get_percentage_bents(self) -> Tuple[SG_T.Sequence[int], SG_T.Sequence[int]]:
        """
        Returns the percentage bent values for flexion and abduction of each finger.

        Returns:
            Tuple[List[int], List[int]]: A tuple containing:
                - flexion_perc_bents: Array of flexion percentages (0-out_max_perc_bent (10000 by default))
                - abduction_perc_bents: Array of abduction percentages (0-out_max_perc_bent (10000 by default))

        Notes:
            - Values range from 0 (finger open) to out_max_perc_bent (finger closed)
            - For the thumb:
                - Flexion: 0 = extended, out_max_perc_bent = fully flexed
                - Abduction: 0 = in plane with palm, out_max_perc_bent = maximally radially extended
            - For other fingers:
                - Flexion: 0 = extended, out_max_perc_bent = fully flexed
                - Abduction: 0 = neutral, out_max_perc_bent = maximally abducted
            - 10000 is used by default instead of 100 to avoid floating point inaccuracies.
            - Use set_perc_bent_vars to change the max perc bent value and how 0 and 10000 are mapped to the finger angles.
            - It calculates this based on the fingertip orientation with respect to the finger base orientation.
            - This method is used because it's independent of user hand sizes, and requires no calibration.
        """
        return self._data.perc_bents_flexion, self._data.abd_perc_bents

    def get_device_info(self) -> SG_T.Device_Info:
        return self._device_info

    def get_raw_percentage_bent_angles(self) -> Tuple[SG_T.Sequence[Union[int, float]], SG_T.Sequence[Union[int, float]]]:
        """
        Returns the raw flexion and abduction angles used to calculate percentage bent.
        Returns: (flex_angles, abd_angles)
        Each is an array of the fingers, containing the raw angles in radians.
        These angles are calculated from the fingertip orientations.
        """
        return self.flex_angles, self.abd_angles






attempts_add_device = 0
def _add_device(device_info : SG_T.Device_Info):
    global attempts_add_device
    device_id = device_info.device_id
    if device_info.device_id not in _active_deviceIds:
        if device_info.device_type == SG_T.DeviceType.REMBRANDT:

            _device = Rembrandt_Device_Internal(device_info)
            SG_data.setup_data_origin(device_id, device_info.data_origin)
    
            _active_devices.append(_device)
            _active_deviceIds.append(device_id)
            _device_dict[device_id] = _device

            SG_cb.on_data_source_updated.add(update_data_rembrandt)

            attempts_add_device = 0

            sg_logger.log(
                "Device connected!    ID:" + str(device_info.device_id) + 
                " | Connected device_ids:" + str(_active_deviceIds) +
                " | " + str(_device.handedness) + 
                " | Firmware: " + str(device_info.firmware_version) + 
                " | Communication type: " + str(device_info.communication_type), 
                level=sg_logger.USER_INFO
            )
    else:
        _remove_device(device_id)
        if attempts_add_device < 3:
            _add_device(device_info)
            sg_logger.warn("Attempted to add device " + str(device_id) + ". This device already existed, so closed connection, destroyed, and recreated the device.")
            attempts_add_device += 1
        
        # delete buffer, communication and other objects related to a device.



    


def _remove_device(device_id : int):
    if device_id in _active_deviceIds:
        # disable connection TODO

        # Buffers will be cleaned up by Python garbage collection

        

        # remove from both lists
        if get_device(device_id) is not None:
            _active_devices.remove(_device_dict[device_id])
            _active_deviceIds.remove(device_id)
        
        # destroy object
        del _device_dict[device_id]
        sg_logger.info("Device " + str(device_id) + " and sub components destroyed.")
    else:
        sg_logger.warn("attempted to destroy device " + str(device_id) + " but the device was not in _active_deviceIds anymore")


        
        
     



# scans port and refreshes which devices are found in the devices list
def initiate_add_device_on_connection(com_type : SG_T.Com_type):
    if com_type == SG_T.Com_type.REAL_GLOVE_USB:
        SG_cb.on_connected_callback_manager.add(_add_device)
        SG_cb.on_disconnected_callback_manager.add(_remove_device)
        SG_cb.init()

    if com_type == SG_T.Com_type.SIMULATED_GLOVE:
        SG_cb.on_connected_callback_manager.add(_add_device)

    return


def nr_active_devices():
    return len(_active_devices)

def get_deviceIds():
    return _active_deviceIds



def get_device(device_id : int) -> SG_IDevice_Internal: 
    if device_id in _device_dict:
        return _device_dict[device_id]
    else:
        raise RuntimeError("deviceId " + str(device_id) + " not found in active devices")
    
def get_rembrandt_device(device_id : int) -> Rembrandt_Device_Internal:
    device = None
    if device_id is not None and device_id in _device_dict:
        device = _device_dict[device_id]
        if device.device_type == SG_T.DeviceType.REMBRANDT:
            return device  # type: ignore
        else:
            raise RuntimeError("device " + str(device_id) + " found but not of type rembrandt as requested")
    else:
        raise RuntimeError("deviceId " + str(device_id) + " not found in active devices")

def hand_to_id(handedness :SG_T.Hand):
    for device in _active_devices:
        if device.handedness == handedness:
             return device._device_id
    sg_logger.warn("no " + str(handedness) + " hand device found")
    return None


def update_data_rembrandt(device_id : int):
    rb = get_rembrandt_device(device_id)
    rb.update_data()






def close_devices():
    global _shutdown_in_progress
    sg_logger.log("Closing devices", level=sg_logger.INFO)
    
    # Set shutdown flag to prevent any further haptic data sending
    _shutdown_in_progress = True
    
    # Stop all data update callbacks to prevent overwriting our zero values
    SG_cb.on_data_source_updated.clear()
    
    for id in _active_deviceIds:
        rb_device = get_rembrandt_device(id)
        if rb_device is not None:
            # Set all forces to zero
            rb_device.set_force_goals([0] * rb_device.nr_of_fingers_tracking())
            
            # Set all vibration actuators to off (correct format: 8 actuators, each with [0, 0, 0])
            rb_device.set_vibro_data([[0, 0, 0]] * 8)
            
            # Send the zero values immediately (bypass shutdown flag for this final send)
            SG_data.send_haptic_data(rb_device.get_device_info())
            sg_logger.log("Closing, set force goals to 0 for device " + str(id), level=sg_logger.USER_INFO)







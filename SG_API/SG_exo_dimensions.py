"""
    This class holds all functions to convert the raw data from the glove to the exo dimensions, fingertip positions, etc.

    We use the following axes definitions: https://adjuvo.github.io/SenseGlove-R1-API/tracking/
    # right hand coordinate system:
    # - x along stretched fingers
    # - for right hand, y towards thumb. For left hand, y towards outside hand.
    # - z pointing up.

    Questions? Written by:
    - Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api
Support: https://www.senseglove.com/support/
"""



import math
import warnings
from typing import List, Tuple, Optional
import numpy as np


from abc import ABC, abstractmethod

from . import SG_math
from . import SG_types as SG_T

from typing import Dict, Sequence, Union


###################### BASE CLASSES ###########################################################################################################################


class Exo_dimensions(ABC):
    @abstractmethod
    def get_linkage_lengths(self):
        pass
    
    @abstractmethod
    def convert_halls_to_rads(self, hall):
        pass

    @abstractmethod
    def get_fingertip_pos_rot(self, exo_pos_rot : Tuple[SG_T.Sequence[SG_T.Vec3_type], SG_T.Sequence[SG_T.Quat_type]]) -> Tuple[SG_T.Vec3_type, SG_T.Quat_type]:
        pass

    @abstractmethod
    def get_exo_joints_poss_rots(self, exo_angles_rad) -> Tuple[List[List[float]], List[List[float]]]:
        pass

    @abstractmethod
    def get_fingers_offset_pos_rot(self) -> Tuple[List[SG_T.Vec3_type], List[SG_T.Quat_type]]:
        pass

    @abstractmethod
    def get_fingertip_thimble_dims(self, last_exo_pos : SG_T.Vec3_type, fingertip_pos_rot : Tuple[SG_T.Vec3_type, SG_T.Quat_type]) -> SG_T.Thimble_dims:
        pass

    @abstractmethod
    def get_starting_exo_poss(self) -> SG_T.Sequence[Sequence[SG_T.Vec3_type]]: # type: ignore
        pass

    # @abstractmethod
    # def get_fingertip_pos_rot_offset(self):
    #     """
    #     Returns position and rotation offset the fingertip will add with respect to the exoskeleton endpoint (middle of the latest square thimble (on top of the fingernail), pointing into the finger)
    #     """
    #     pass

    # @abstractmethod
    # def set_fingertip_pos_rot_offset(self, pos_offset, rot_offset):
    #     pass


class Thimble_dimensions(ABC):
    @abstractmethod
    def get_thimble_dims(self, last_exo_pos : SG_T.Vec3_type, thimble_pos_rot : Tuple[SG_T.Vec3_type, SG_T.Quat_type]) -> SG_T.Thimble_dims:
        pass



class Thimble_dimensions_Base(Thimble_dimensions):
    def __init__(self):
        self.END_EXO_TO_MID_FRONT_OFFSET = [15, 0, -11]
        self.RADIUS = 19.5/2 #21 mm, -1.5mm to center exo point /2 for radius
        self.END_EXO_TO_SPHERE_CENTER_OFFSET =np.array(self.END_EXO_TO_MID_FRONT_OFFSET, dtype=np.float64) + np.array([-self.RADIUS, 0., 0.]) 
        self.THIMBLE_LENGTH = 25
        self.CYLINDER_LENGTH = self.THIMBLE_LENGTH - self.RADIUS
        self.CYLINDER_TO_SPHERE_OFFSET = np.array([-self.THIMBLE_LENGTH/2, 0, 0])

    def get_thimble_dims(self, last_exo_pos : SG_T.Vec3_type, thimble_tip_pos_rot : Tuple[SG_T.Vec3_type, SG_T.Quat_type]) -> SG_T.Thimble_dims:
        
        sphere_center_pos = last_exo_pos + SG_math.rotate_vec_by_quat(thimble_tip_pos_rot[1], self.END_EXO_TO_SPHERE_CENTER_OFFSET)
        thimble_rot = thimble_tip_pos_rot[1]
        
        cylinder_center_pos = sphere_center_pos - np.array([-self.CYLINDER_LENGTH/2, 0, 0])
        return SG_T.Thimble_dims(sphere_center_pos, thimble_rot, self.RADIUS, cylinder_center_pos, self.CYLINDER_LENGTH)



class Thimble_dimensions_RB_v03(Thimble_dimensions_Base):
    def __init__(self):
        self.END_EXO_TO_MID_FRONT_OFFSET = [14.5, 0, -11] #[19.5, 0, -11]
        self.RADIUS = 19.5/2 #21 mm, -1.5mm to center exo point /2 for radius
        super().__init__()


angle_offsets_2steps = [ # jig calibrated for calibrating with 2 steps (1 empty spot in between)
    0,
    -64.623,
    50.754 + 180,
    50.754 + 180,
    50.754 + 180,
    50.754 + 180,
    50.754 + 180,
    25.38
]

angle_offsets_no_jig = [
    0,
    95.3 + 180,
    25.123 + 180,
    25.123 + 180,
    25.123 + 180,
    25.123 + 180,
    25.123 + 180,
    -90
]




class Exo_finger_dimensions_Base(Exo_dimensions):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, thimble : Thimble_dimensions, angle_offsets=None, linkage_lengths=None):
        self._FINGER_TO_WRIST_OFFSET = FINGER_TO_WRIST_OFFSET
        self._FINGER_TO_WRIST_ROT_EULER_OFFSET = FINGER_TO_WRIST_ROT_OFFSET

        self._thimble = thimble

        if FINGER_TO_WRIST_ROT_OFFSET is not None:
            self.FINGER_TO_WRIST_ROT_QUAT_OFFSET = SG_math.Quaternion.from_euler(*SG_math.radians(self._FINGER_TO_WRIST_ROT_EULER_OFFSET))
        else:
            self.FINGER_TO_WRIST_ROT_QUAT_OFFSET = None

        self.ANGLE_OFFSETS = angle_offsets if angle_offsets else [0] * 8
        self.LINKAGE_LENGTHS = linkage_lengths if linkage_lengths else [0] * 8
        
        #TODO: function to set these by the user
        self._FINGERTIP_OFFSET = [14, 0, 0] # top front of thimble
        self._FINGERTIP_OFFSET_ROT = [0, -math.pi/2, 0]


        
        self._MAX_HALL_VALUE = 16383

    def get_linkage_lengths(self):
        return self.LINKAGE_LENGTHS

    def _hal_to_degrees(self, hall):
        val = (360.0 / self._MAX_HALL_VALUE) * hall
        if val > 180:
            val -= 360
        if val < -180:
            val += 360
        return val


    #TODO: speed this up by using numpy
    
    def convert_halls_to_rads(self, hall):
        to_rads = (math.pi / 180.0)

        rad = [0] * 8
        for i in range(8):
            rad[i] = -(self._hal_to_degrees(hall[i]) + self.ANGLE_OFFSETS[i]) * to_rads

        #TODO: split this up to separate function
        # apply sensor inversion
        rad[0] = rad[0]
        rad[1] = rad[1] * -1
        rad[3] = rad[3] * -1
        rad[5] = rad[5] * -1
        rad[7] = rad[7] * -1

        return rad

    def get_exo_joints_poss_rots(self, exo_angles_rad_finger):
        linkages_lengths_flexion = self.get_linkage_lengths()
        angles_flexion = exo_angles_rad_finger[1:]
        angles_3d = [(0, ay, 0) for ay in angles_flexion]
        angles_3d.insert(0, self._get_splay_angle(exo_angles_rad_finger[0]))  # use customizable splay

        linkages = [[length, 0, 0] for length in linkages_lengths_flexion]
        pos_array, rot_array = SG_math.forward_kinematics_3d(self._FINGER_TO_WRIST_OFFSET, linkages, angles_3d, self.FINGER_TO_WRIST_ROT_QUAT_OFFSET)
        assert pos_array is not None and rot_array is not None, "forward_kinematics_3d_python returned None"
        return pos_array, rot_array

    def get_fingertip_pos_rot(self, exo_pos_rot : Tuple[SG_T.Sequence[SG_T.Vec3_type], SG_T.Sequence[SG_T.Quat_type]]):
        pos_array, rot_array = exo_pos_rot

        assert pos_array is not None and rot_array is not None, "get_exo_joints_poss_rots returned None"

        exo_end_pos = pos_array[-1]

        fingertip_rot = SG_math.rotate_quat_euler(rot_array[-1], self._FINGERTIP_OFFSET_ROT)
        fingertip_off = SG_math.rotate_vec_by_quat(fingertip_rot, self._FINGERTIP_OFFSET)
        fingertip_pos = exo_end_pos + fingertip_off
        return fingertip_pos, fingertip_rot
    
    def get_fingertip_thimble_dims(self, last_exo_pos : SG_T.Vec3_type, fingertip_pos_rot : Tuple[SG_T.Vec3_type, SG_T.Quat_type]) -> SG_T.Thimble_dims:
        thimble_dims = self._thimble.get_thimble_dims(last_exo_pos, fingertip_pos_rot)
        return thimble_dims
    

    def get_fingers_offset_pos_rot(self) -> Tuple[SG_T.Vec3_type, Optional[SG_math.Quaternion]]:
        return self._FINGER_TO_WRIST_OFFSET, self.FINGER_TO_WRIST_ROT_QUAT_OFFSET
    
    
    def get_starting_exo_poss(self) -> SG_T.Sequence[Sequence[SG_T.Vec3_type]]:
        linkage_lengths = self.get_linkage_lengths()
        start_pos = np.array(self._FINGER_TO_WRIST_OFFSET)
        finger_exo_poss = [start_pos]
        for length in linkage_lengths:
            next_pos = finger_exo_poss[-1] + np.array([0, length, 0])
            finger_exo_poss.append(next_pos)
        return finger_exo_poss # [pos.tolist() for pos in finger_exo_poss] #type: ignore



    def _get_splay_angle(self, splay_angle_rad):
        return (0, 0, splay_angle_rad)
    





##################### Finger prototype implementations - Linkage lengths and start angles  ###########################################################################################################################


#0.5

# The (output) angles when placed inside the 0.5 calibration Jig
# for a single finger
_0_5_calibrationAngles = [0, -52.2, 120, -120, 120, -120, 120, 60]

#since angle_offsets are calculated oddly, I've automated the process here.
angle_offset_0_5_jig = [
    _0_5_calibrationAngles[0],
    _0_5_calibrationAngles[1],
    360 - abs(_0_5_calibrationAngles[2]),
    360 - abs(_0_5_calibrationAngles[3]),
    360 - abs(_0_5_calibrationAngles[4]),
    360 - abs(_0_5_calibrationAngles[5]),
    360 - abs(_0_5_calibrationAngles[6]),
    _0_5_calibrationAngles[7]
]

#if you don't wish to automate; here's the hard-coded values
#angle_offset_0_5_jig = [
#    0,
#    -52.2,
#    240,
#    240,
#    240,
#    240,
#    240,
#    60
#]

class Exo_dimensions_RB_v05_Finger(Exo_finger_dimensions_Base):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET= None):
        angle_offsets = angle_offset_0_5_jig
        #s print("angle_offsets", angle_offsets)
        linkage_lengths = [13.3, 35, 35, 35, 35, 35, 35, 10] # in mm


        self._thimble = Thimble_dimensions_RB_v03()
        super().__init__(FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, self._thimble, angle_offsets, linkage_lengths)

    def convert_halls_to_rads(self, hall):
        rad = [0] * 8
        for i in range(8):
            rad[i] = -(self._hal_to_degrees(hall[i]) + self.ANGLE_OFFSETS[i]) * (math.pi / 180.0)

        # apply sensor inversion
        rad[0] = rad[0] * -1
        rad[1] = rad[1] * -1
        rad[3] = rad[3] * -1
        rad[5] = rad[5] * -1
        rad[7] = rad[7] * -1

        return rad



class Exo_dimensions_RB_v05_Thumb_LEFT(Exo_finger_dimensions_Base):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET= None):
        angle_offsets = angle_offset_0_5_jig.copy()
        angle_offsets[0] = -90 ## thumb offset for start rotation
        
        linkage_lengths = [13.3, 35, 35, 35, 35, 35, 35, 10] # in mm

        self._thimble = Thimble_dimensions_RB_v03()

        super().__init__(FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, self._thimble, angle_offsets, linkage_lengths)

        #self._FINGERTIP_OFFSET =  [7, 7, -15]


    def convert_halls_to_rads(self, hall):
        rad = [0] * 8
        for i in range(8):
            rad[i] = -(self._hal_to_degrees(hall[i]) + self.ANGLE_OFFSETS[i]) * (math.pi / 180.0)

        # apply sensor inversion
        rad[0] = rad[0] * -1
        rad[1] = rad[1] * -1
        rad[3] = rad[3] * -1
        rad[5] = rad[5] * -1
        rad[7] = rad[7] * -1

        return rad


class Exo_dimensions_RB_v05_Thumb_RIGHT(Exo_finger_dimensions_Base):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET= None):
        angle_offsets = angle_offset_0_5_jig.copy()
        angle_offsets[0] = 90 ## thumb offset for start rotation
        
        linkage_lengths = [13.3, 35, 35, 35, 35, 35, 35, 10] # in mm

        self._thimble = Thimble_dimensions_RB_v03()
        super().__init__(FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, self._thimble, angle_offsets, linkage_lengths)
        #self._FINGERTIP_OFFSET = [7, -7, -15]


    def convert_halls_to_rads(self, hall):
        rad = [0] * 8
        for i in range(8):
            rad[i] = -(self._hal_to_degrees(hall[i]) + self.ANGLE_OFFSETS[i]) * (math.pi / 180.0)

        # apply sensor inversion
        rad[0] = rad[0] * -1
        rad[1] = rad[1] * -1
        rad[3] = rad[3] * -1
        rad[5] = rad[5] * -1
        rad[7] = rad[7] * -1

        return rad


#0.4
class Exo_dimensions_RB_v04_Finger(Exo_finger_dimensions_Base):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET= None):
        angle_offsets = angle_offsets_2steps
        #s print("angle_offsets", angle_offsets)
        linkage_lengths = [13.3, 35, 35, 35, 35, 35, 35, 10] # in mm


        self._thimble = Thimble_dimensions_RB_v03()
        super().__init__(FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, self._thimble, angle_offsets, linkage_lengths)

    def convert_halls_to_rads(self, hall):
        rad = [0] * 8
        for i in range(8):
            rad[i] = -(self._hal_to_degrees(hall[i]) + self.ANGLE_OFFSETS[i]) * (math.pi / 180.0)

        # apply sensor inversion
        rad[0] = rad[0] * -1
        rad[1] = rad[1] * -1
        rad[3] = rad[3] * -1
        rad[5] = rad[5] * -1
        rad[7] = rad[7] * -1

        return rad



class Exo_dimensions_RB_v04_Thumb_LEFT(Exo_finger_dimensions_Base):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET= None):
        angle_offsets = angle_offsets_2steps
        
        linkage_lengths = [13.3, 35, 35, 35, 35, 35, 35, 10] # in mm

        self._thimble = Thimble_dimensions_RB_v03()

        super().__init__(FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, self._thimble, angle_offsets, linkage_lengths)

        #self._FINGERTIP_OFFSET =  [7, 7, -15]


    def convert_halls_to_rads(self, hall):
        rad = [0] * 8
        for i in range(8):
            rad[i] = -(self._hal_to_degrees(hall[i]) + self.ANGLE_OFFSETS[i]) * (math.pi / 180.0)

        # apply sensor inversion
        rad[0] = rad[0] * -1
        rad[1] = rad[1] * -1
        rad[3] = rad[3] * -1
        rad[5] = rad[5] * -1
        rad[7] = rad[7] * -1

        return rad


class Exo_dimensions_RB_v04_Thumb_RIGHT(Exo_finger_dimensions_Base):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET= None):
        angle_offsets = angle_offsets_2steps
        
        linkage_lengths = [13.3, 35, 35, 35, 35, 35, 35, 10] # in mm

        self._thimble = Thimble_dimensions_RB_v03()
        super().__init__(FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, self._thimble, angle_offsets, linkage_lengths)
        #self._FINGERTIP_OFFSET = [7, -7, -15]


    def convert_halls_to_rads(self, hall):
        rad = [0] * 8
        for i in range(8):
            rad[i] = -(self._hal_to_degrees(hall[i]) + self.ANGLE_OFFSETS[i]) * (math.pi / 180.0)

        # apply sensor inversion
        rad[0] = rad[0] * -1
        rad[1] = rad[1] * -1
        rad[3] = rad[3] * -1
        rad[5] = rad[5] * -1
        rad[7] = rad[7] * -1

        return rad

#0.3
class Exo_dimensions_RB_v03_Finger(Exo_finger_dimensions_Base):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET= None):
        # angle_offsets = [
        #     0,
        #     95.3 + 180,
        #     25.123 + 180,
        #     25.123 + 180,
        #     25.123 + 180,
        #     25.123 + 180,
        #     25.123 + 180,
        #     -90
        # ]
        angle_offsets = angle_offsets_2steps
        linkage_lengths = [13.3, 35, 35, 35, 35, 35, 35, 10] # in mm

        self._thimble = Thimble_dimensions_RB_v03()
        super().__init__(FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, self._thimble, angle_offsets, linkage_lengths)

    def convert_halls_to_rads(self, hall):
        rad = [0] * 8
        for i in range(8):
            rad[i] = -(self._hal_to_degrees(hall[i]) + self.ANGLE_OFFSETS[i]) * (math.pi / 180.0)

        # apply sensor inversion
        rad[0] = rad[0] * -1
        rad[1] = rad[1] * -1
        rad[3] = rad[3] * -1
        rad[5] = rad[5] * -1
        rad[7] = rad[7] * -1

        return rad



class Exo_dimensions_RB_v03_Thumb(Exo_finger_dimensions_Base):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET= None):
        # angle_offsets = [
        #     0,
        #     95.3 + 180,
        #     25.123 + 180,
        #     25.123 + 180,
        #     25.123 + 180,
        #     25.123 + 180,
        #     25.123 + 180,
        #     -90
        # ]
        angle_offsets = angle_offsets_2steps
        linkage_lengths = [13.3, 35, 35, 35, 35, 35, 35, 10] # in mm

        self._thimble = Thimble_dimensions_RB_v03()

        super().__init__(FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, self._thimble, angle_offsets, linkage_lengths)


    def convert_halls_to_rads(self, hall):
        rad = [0] * 8
        for i in range(8):
            rad[i] = -(self._hal_to_degrees(hall[i]) + self.ANGLE_OFFSETS[i]) * (math.pi / 180.0)

        # apply sensor inversion
        rad[0] = rad[0] * -1
        rad[1] = rad[1] * -1
        rad[3] = rad[3] * -1
        rad[5] = rad[5] * -1
        rad[7] = rad[7] * -1

        return rad



#0.2
class Exo_dimensions_RB_v02_Finger(Exo_finger_dimensions_Base):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET= None):
        angle_offsets = [
            0,
            128.6 + 180,
            66.8 + 180,
            73.8 + 180,
            91.2 + 180,
            80.4 + 180,
            69.7 + 180,
            180 - 145.2
        ]
        linkage_lengths = [11.62, 35, 35, 35, 35, 35, 35, 10]
        self._thimble = Thimble_dimensions_RB_v03()

        super().__init__(FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, self._thimble, angle_offsets, linkage_lengths)



class Exo_dimensions_RB_v02_Thumb(Exo_finger_dimensions_Base):
    def __init__(self, FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET= None):
        angle_offsets = [
            -90,
            128.6 + 180,
            66.8 + 180,
            73.8 + 180,
            91.2 + 180,
            80.4 + 180,
            69.7 + 180,
            180 - 145.2
        ]
        linkage_lengths = [11.62, 35, 35, 35, 35, 35, 35, 10]

        self._thimble = Thimble_dimensions_RB_v03()

        super().__init__(FINGER_TO_WRIST_OFFSET, FINGER_TO_WRIST_ROT_OFFSET, self._thimble, angle_offsets, linkage_lengths)

    def convert_halls_to_rads(self, hall):
        rad = [0] * 8
        for i in range(8):
            rad[i] = -(self._hal_to_degrees(hall[i]) + self.ANGLE_OFFSETS[i]) * (math.pi / 180.0)
        
        # apply sensor inversion
        rad[0] = rad[0]
        rad[1] = rad[1] * -1
        rad[3] = rad[3] * -1
        rad[5] = rad[5] * -1
        rad[7] = rad[7] * -1

        return rad







############### HAND DEFINITIONS ###########################################################################################################################

# List contains exo_dimension type for each separate finger. The vector is the offset from the base of the wrist  
# FINGER STARTING POINT LOCATIONS RELATIVE TO GLOVE 
RB_right_02 = [Exo_dimensions_RB_v02_Thumb((-1.7, 5.2, -29.4), (-90, 0., 50)), 
               Exo_dimensions_RB_v02_Finger((69.7, -10, 2.9)), 
               Exo_dimensions_RB_v02_Finger((71.6, -31.6, 2.9)),
               Exo_dimensions_RB_v02_Finger((67.2, -53.2, 2.9))]

RB_left_02 = [Exo_dimensions_RB_v02_Thumb((-1.7, -5.2, -29.4), (90, 0., -50)), 
              Exo_dimensions_RB_v02_Finger((69.7, 10, 2.9)), 
              Exo_dimensions_RB_v02_Finger((71.6, 31.6, 2.9)),
              Exo_dimensions_RB_v02_Finger((67.2, 53.2, 2.9))]

RB_right_03 = [Exo_dimensions_RB_v03_Thumb((-5.494, 87.43, -45.538), (-85, 0, 50)), 
               Exo_dimensions_RB_v03_Finger((75.908, 72, -0.089)), 
               Exo_dimensions_RB_v03_Finger((84.908, 47.777, -0.089)),
               Exo_dimensions_RB_v03_Finger((75.908, 24.127, -0.089))]

RB_left_03 = [Exo_dimensions_RB_v03_Thumb((-5.494, -87.43, -45.538), (85, 0, -50)), 
               Exo_dimensions_RB_v03_Finger((75.908, -72, -0.089)), 
               Exo_dimensions_RB_v03_Finger((84.908, -47.777, -0.089)),
               Exo_dimensions_RB_v03_Finger((75.908, -24.127, -0.089))]


# Offsets
RB_right_04 = [Exo_dimensions_RB_v04_Thumb_RIGHT((-20.6385, 81.9688, -43.5289), (-85, 0, 50)),
               Exo_dimensions_RB_v04_Finger((62.2365, 72, 1.4391)),
               Exo_dimensions_RB_v04_Finger((71.2365, 49.65, 1.4391)),
               Exo_dimensions_RB_v04_Finger((62.2365, 27.3, 1.4391)),
               Exo_dimensions_RB_v04_Finger((53.2365, 4.95, 0.4391))]
            
RB_left_04 = [Exo_dimensions_RB_v04_Thumb_LEFT((-20.6385, -81.9688, -43.5289), (85, 0, -50)),
               Exo_dimensions_RB_v04_Finger((62.2365, -72, 1.4391)),
               Exo_dimensions_RB_v04_Finger((71.2365, -49.65, 1.4391)),
               Exo_dimensions_RB_v04_Finger((62.2365, -27.3, 1.4391)),
               Exo_dimensions_RB_v04_Finger((53.2365, -4.95, 0.4391))]

# v0.5 offsets
RB_right_05 = [Exo_dimensions_RB_v05_Thumb_RIGHT((-80.0838, 10.6155, -35.5296), (-85, 0, 56)),
               Exo_dimensions_RB_v05_Finger((0, 0, 0)),
               Exo_dimensions_RB_v05_Finger((9, -22.25, 0)),
               Exo_dimensions_RB_v05_Finger((0, -44.70, 0)),
               Exo_dimensions_RB_v05_Finger((-9, -67.05, 0))]
            
RB_left_05 = [Exo_dimensions_RB_v05_Thumb_LEFT((-80.0838, -10.6155, -35.5296), (85, 0, -56)),
               Exo_dimensions_RB_v05_Finger((0, 0, 0)),
               Exo_dimensions_RB_v05_Finger((9, 22.25, 0)),
               Exo_dimensions_RB_v05_Finger((0, 44.70, 0)),
               Exo_dimensions_RB_v05_Finger((-9, 67.05, 0))]



# dicts to lookup the correct exo_dimensions object based on linkage type and the hand.
dict_hand_type_to_exo_obj = []
_dict_exo_dims : Dict[Tuple[SG_T.Exo_linkage_type, SG_T.Hand], List[Exo_dimensions]] = { }
_dict_exo_dims[(SG_T.Exo_linkage_type.REMBRANDT_PROTO_02, SG_T.Hand.LEFT) ] = RB_left_02
_dict_exo_dims[(SG_T.Exo_linkage_type.REMBRANDT_PROTO_02, SG_T.Hand.RIGHT) ] = RB_right_02
_dict_exo_dims[(SG_T.Exo_linkage_type.REMBRANDT_PROTO_03, SG_T.Hand.LEFT) ] = RB_left_03
_dict_exo_dims[(SG_T.Exo_linkage_type.REMBRANDT_PROTO_03, SG_T.Hand.RIGHT) ] = RB_right_03
_dict_exo_dims[(SG_T.Exo_linkage_type.REMBRANDT_PROTO_04, SG_T.Hand.LEFT) ] = RB_left_04
_dict_exo_dims[(SG_T.Exo_linkage_type.REMBRANDT_PROTO_04, SG_T.Hand.RIGHT) ] = RB_right_04
_dict_exo_dims[(SG_T.Exo_linkage_type.REMBRANDT_PROTO_05, SG_T.Hand.LEFT) ] = RB_left_05
_dict_exo_dims[(SG_T.Exo_linkage_type.REMBRANDT_PROTO_05, SG_T.Hand.RIGHT) ] = RB_right_05


################### FUNCTIONS TO RETRIEVE EXOSKELETON AND TRACKING INFO ############################################

    

def get_exo_obj(exo_type : SG_T.Exo_linkage_type, hand : SG_T.Hand ) -> List[Exo_dimensions]:
    if (exo_type, hand) in _dict_exo_dims:
        return _dict_exo_dims[(exo_type, hand)]
    else:
        raise RuntimeError("Exo_type/hand combo " + str((exo_type, hand)) + " to retrieve Exo_dimensions not found as implemented")


def get_fingertips_pos_rot(exo_type : SG_T.Exo_linkage_type, hand : SG_T.Hand, exo_poss_rots :Tuple[SG_T.Sequence[Sequence[SG_T.Vec3_type]], SG_T.Sequence[Sequence[SG_T.Quat_type]]]):
    exo_dims = get_exo_obj(exo_type, hand)
    return _get_fingertips_pos_rot_from_dims(exo_dims, exo_poss_rots)

def get_fingertips_pos_rot_with_local(exo_type : SG_T.Exo_linkage_type, hand : SG_T.Hand, exo_poss_rots : Tuple[SG_T.Sequence[Sequence[SG_T.Vec3_type]], SG_T.Sequence[Sequence[SG_T.Quat_type]]]):
    """
    Calculate fingertip positions and rotations, returning both local (pre-finger_offset) and world-space (post-finger_offset) versions.
    Returns: (fingertips_pos, fingertips_rot_world, fingertips_rot_local)
    """
    exo_dims = get_exo_obj(exo_type, hand)
    return _get_fingertips_pos_rot_with_local_from_dims(exo_dims, exo_poss_rots)



def get_exo_joints_poss_rots(exo_type : SG_T.Exo_linkage_type, hand : SG_T.Hand, exo_angles_rad : SG_T.Sequence[Sequence[Union[int, float]]]):
    exo_dims = get_exo_obj(exo_type, hand)
    return _get_exo_joints_poss_rots_from_dims(exo_dims, exo_angles_rad)

def get_finger_offsets(exo_type : SG_T.Exo_linkage_type, hand :SG_T.Hand) -> Tuple[List[SG_T.Vec3_type], List[SG_math.Quaternion]]:
    """
    Returns positional vec [x,y,z], rotational quat ([w,x,y,z]) offset.
    Position is x, y of the first joint of the exoskeleton (splay), at the z where the next flexion joint is, relative to a base position in the hub."
    """
    exo_dims = get_exo_obj(exo_type, hand)
    return get_finger_offsets_from_dims(exo_dims)



def _get_fingertips_pos_rot_from_dims(exo_dims : List[Exo_dimensions], exo_poss_rot : Tuple[SG_T.Sequence[Sequence[SG_T.Vec3_type]], SG_T.Sequence[Sequence[SG_T.Quat_type]]]):
    fingertips_pos = []
    fingertips_rot = []

    for i, finger_dim in enumerate(exo_dims):
        pos, rot = finger_dim.get_fingertip_pos_rot((exo_poss_rot[0][i], exo_poss_rot[1][i]))
        fingertips_pos.append(pos)
        fingertips_rot.append(rot)
        # add finger offset with respect to wrist
    return fingertips_pos, fingertips_rot

def _get_fingertips_pos_rot_with_local_from_dims(exo_dims : List[Exo_dimensions], exo_poss_rots : Tuple[SG_T.Sequence[Sequence[SG_T.Vec3_type]], SG_T.Sequence[Sequence[SG_T.Quat_type]]]):
    """
    Calculate fingertip positions and rotations, returning both local (pre-offset) and world-space (post-offset) versions.
    Returns: (fingertips_pos, fingertips_rot_world, fingertips_rot_local)
    
    For now, we'll use a simpler approach: calculate both with and without finger offset transformations.
    """
    fingertips_pos = []
    fingertips_rot_world = []  # With finger offset applied (current behavior)
    fingertips_rot_local = []  # Without finger offset applied (for percentage bent)
    
    # Get finger offsets
    finger_offsets = get_finger_offsets_from_dims(exo_dims)
    finger_offset_poss, finger_offset_quats = finger_offsets
    
    for i, finger_dim in enumerate(exo_dims):
        # Calculate forward kinematics WITH finger offset (current behavior)
        exo_pos_rot_world = (exo_poss_rots[0][i], exo_poss_rots[1][i])
        pos_world, rot_world = finger_dim.get_fingertip_pos_rot(exo_pos_rot_world)
        
        # For the local version, we'll use the world rotation but undo the finger offset transformation
        # This is mathematically equivalent to calculating without finger offset but more reliable
        #TODO: instead make the inverse kinematics calculate without it in the first place, adding the rotation back only for world space. That requires editing the CPP.
        if finger_offset_quats[i] is not None:
            # Undo the finger offset rotation: local_rot = finger_offset^-1 * world_rot
            world_quat = SG_math.Quaternion(*rot_world)
            finger_offset_inv = finger_offset_quats[i].inverse()
            local_quat = finger_offset_inv.multiply(world_quat)
            fingertip_rot_local = local_quat.q
        else:
            # No finger offset, so world and local are the same
            fingertip_rot_local = rot_world
        
        fingertips_pos.append(pos_world)
        fingertips_rot_world.append(rot_world)
        fingertips_rot_local.append(fingertip_rot_local)
        
    return fingertips_pos, fingertips_rot_world, fingertips_rot_local



def _get_exo_joints_poss_rots_from_dims(exo_dims : List[Exo_dimensions], exo_angles_rad : SG_T.Sequence[Sequence[Union[int, float]]]):
    exo_joints_pos = []
    exo_joints_rot = []
    for i, finger_dim in enumerate(exo_dims):
        pos, rot = finger_dim.get_exo_joints_poss_rots(exo_angles_rad[i])
        exo_joints_pos.append(pos)
        exo_joints_rot.append(rot)

    return exo_joints_pos, exo_joints_rot

def get_finger_offsets_from_dims(exo_dims : List[Exo_dimensions]) -> Tuple[List[SG_T.Vec3_type], List[SG_math.Quaternion]]:
    base_pos = []
    base_rot = []
    for i, finger_dim in enumerate(exo_dims):
        pos, rot = finger_dim.get_fingers_offset_pos_rot()
        base_pos.append(pos)
        base_rot.append(rot)
    
    return base_pos, base_rot
        
def get_fingertip_thimble_dims(exo_type : SG_T.Exo_linkage_type, hand : SG_T.Hand, exo_poss : SG_T.Sequence[Sequence[SG_T.Vec3_type]], fingertips_pos_rot : Tuple[List[SG_T.Vec3_type], List[SG_T.Quat_type]]) -> List[SG_T.Thimble_dims]:
    exo_dims = get_exo_obj(exo_type, hand)
    thimble_dims = []
    for i, finger_dim in enumerate(exo_dims):
        # Get the last exo position for this finger (index -1)
        last_exo_pos = exo_poss[i][-1]
        thimble_dims.append(finger_dim.get_fingertip_thimble_dims(last_exo_pos, fingertip_pos_rot=(fingertips_pos_rot[0][i], fingertips_pos_rot[1][i])))
    return thimble_dims

def get_linkage_lengths(device_info : SG_T.Device_Info) -> SG_T.Sequence[Sequence[Union[int, float]]]:
    """
    per finger, gets the linkage lengths in mm (nr of physical linkages determines length of list)
    """
    exo_dimensions_each_finger = get_exo_obj(device_info.exo_linkage_type, device_info.hand)
    linkage_lengths_all_fingers = []
    for finger in range(device_info.nr_fingers_tracking):
        linkage_lengths_all_fingers.append(exo_dimensions_each_finger[int(finger)].get_linkage_lengths())
    return linkage_lengths_all_fingers
    


#TODO: currently returns all links in completely straight line. Make it a different starting orientation.
def get_default_exo_poss(device_info : SG_T.Device_Info) -> SG_T.Sequence[Sequence[SG_T.Vec3_type]]:
    exo_dimensions_each_finger = get_exo_obj(device_info.exo_linkage_type, device_info.hand)
    exo_poss_default = []
    for finger in range(device_info.nr_fingers_tracking):
        exo_poss_default.append(exo_dimensions_each_finger[int(finger)].get_starting_exo_poss())
    return exo_poss_default



# def set_fingertip_offset(fingertip_pos_offset: List[float], fingertip_rot_offset : List[float], hand : SG_T.Hand, finger : SG_T.Finger, exo_version : SG_T.Exo_linkage_type):
#     """
#     Sets fingertip offsets to be used to calculate fingertip position on top of exoskeleton endpoint rotation.
#     fingertip_pos_offset =  offset in mm, 
#     """

#     exo_obj = get_exo_obj(exo_version, hand)
#     exo_obj
#     if exo_version == SG_T.Exo_linkage_type.REMBRANDT_lv01:
#         if hand == SG_T.Hand.LEFT:
#             RB_left_lv01[int(finger)] = fingertip_offset
#         elif hand == SG_T.Hand.RIGHT:
#             RB_right_lv01[int(finger)] = fingertip_offset
#         else:
#             warnings.warn("hand type not implemented in set_fingertip_offset", RuntimeWarning)
#     else:
#         warnings.warn("exoskeleton type not implemented in set_fingertip_offset", RuntimeWarning)

"""
Contains all data calculated and stored for the R1 glove. Is used in the buffer and SG_devices to store the data.

Questions? Written by:
- Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api/
Support: https://www.senseglove.com/support/
"""

from dataclasses import dataclass, field


from . import SG_types as SG_T
from typing import Any, List, Sequence, Union
from SG_API.SG_logger import sg_logger

# dataclasses should be implemented as struct in C

@dataclass 
class PID_settings:
    kp: float
    ki: float
    kd: float

@dataclass
class Force_settings:
    PID_gains : PID_settings
    #todo: define the others.


@dataclass
class Rembrandt_v1_data:
    device_id: int
    device_info: SG_T.Device_Info
    
    # force_settings : Force_settings                # all force control related settings. Commented for now, but initial values should be obtained from initial settings message.

    #currently init with factory, but I also call init_data_values after in Rembrandt_Device which should do a similar thing in C++

    # outer array: fingers thumb to pinky, inner array proximal to distal angles in radians
    exo_angles_rad : SG_T.Sequence[Sequence[Union[int, float]]]  = field(default_factory=lambda:    [[0,0,0,0,0,0,0,0], [0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0]] )
    exo_angles_rad_filtered : SG_T.Sequence[Sequence[Union[int, float]]]  = field(default_factory=lambda:    [[0,0,0,0,0,0,0,0], [0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0]] )
    exo_joints_poss : SG_T.Sequence[Sequence[SG_T.Vec3_type]] =   field(default_factory=lambda:    [[(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)], 
                                                                                    [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)],
                                                                                    [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)],
                                                                                    [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)],
                                                                                    [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)]])
    
    exo_joint_rots : SG_T.Sequence[Sequence[SG_T.Quat_type]] =   field(default_factory=lambda:     [[(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0)], 
                                                                                    [(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0)], 
                                                                                    [(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0)],  
                                                                                    [(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0)],  
                                                                                    [(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0)]]) 

    # fingers thumb to pinky containing the measured force for each finger
    forces_sensed : SG_T.Sequence[Union[int, float]] =   field(default_factory=lambda:     [0,0,0,0,0])  

    fingertips_pos : SG_T.Sequence[SG_T.Vec3_type] = field(default_factory=lambda:    [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)])
    fingertips_rot : SG_T.Sequence[SG_T.Quat_type] = field(default_factory=lambda:    [(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0)])
    
    # Pre-offset fingertip rotations (finger-local space, before finger offset transformation)
    # Used for percentage bent calculations to avoid undoing transformations
    fingertips_rot_local : SG_T.Sequence[SG_T.Quat_type] = field(default_factory=lambda:    [(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0),(1,0,0,0)])

    abd_perc_bents : List[int]          = field(default_factory=lambda:    [0,0,0,0,0]) # 0 to 10000, see tracking docs for more info
    perc_bents_flexion : List[int]      = field(default_factory=lambda:    [0,0,0,0,0]) # 0 (open) to 10000 (closed), see tracking docs for more info

    perc_bents_flexion_firmware : List[int] = field(default_factory=lambda:    [0,0,0,0,0]) # 0 (open) to 65535 (closed)


    # Outgoing data:
    # fingers thumb to pinky containing force goals set on the glove in the controller
    force_goals   : List[int]           = field(default_factory=lambda:    [0,0,0,0,0]) # in milli-newton
    control_modes : List[int]           = field(default_factory=lambda:    [SG_T.Control_Mode.FORCE_GOAL_DEFAULT] * 5 )
   

    raw_vibro_data :List[List[Any]]                 = field(default_factory=lambda: [               # Prepare vibration data: per vibration actuator (each finger + 3 palm)
                                                                                    # Format: [command | Amplitude | total waveforms | waveform1_index, waveform1_phase, waveform1_amplitude | waveform2_index, waveform2_phase, waveform2_amplitude]
                                                                                    
                                                                                        [0, 0, 0], # example: [0b10, 127, 2, 1, 0, 127, 2, 0, 127],  # Finger 1 (thumb) - active with 2 waveforms
                                                                                        [0, 0, 0],                              # Finger 2 (index) - inactive
                                                                                        [0, 0, 0],                              # Finger 3 (middle) - inactive  
                                                                                        [0, 0, 0],                              # Finger 4 (ring) - inactive
                                                                                        [0, 0, 0],                              # Finger 5 (pinky) - inactive
                                                                                        [0, 0, 0],                              # Palm actuator 1 - inactive
                                                                                        [0, 0, 0],                              # Palm actuator 2 - inactive
                                                                                        [0, 0, 0]                               # Palm actuator 3 - inactive
                                                                                    ])


    # todo: define force goals here and such

# in C++ instead of factory, use this. This is called in the init of rembrandt_internal_device to be sure.
def init_data_values(rb_v1_data : Rembrandt_v1_data):
    # outer array: fingers thumb to pinky, inner array proximal to distal angles in radians
    rb_v1_data.exo_angles_rad = [[0,0,0,0,0,0,0,0], [0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0]] 
    rb_v1_data.forces_sensed  = [0,0,0,0,0]   # fingers thumb to pinky containing the measured force for each finger
    rb_v1_data.force_goals = [0,0,0,0,0]   # fingers thumb to pinky containing force goals set on the glove in the controller
    rb_v1_data.control_modes = [int(SG_T.Control_Mode.FORCE_GOAL_DEFAULT)] * 5
    rb_v1_data.perc_bents_flexion = [0,0,0,0,0]
    rb_v1_data.abd_perc_bents = [0,0,0,0,0]

    # Prepare vibration data: per vibration actuator (each finger + 3 palm)
    # Format: [command | Amplitude | total waveforms | waveform1_index, waveform1_phase, waveform1_amplitude | waveform2_index, waveform2_phase, waveform2_amplitude]
    # Using dummy/test data for now
    rb_v1_data.raw_vibro_data =  [
                [0, 0, 0], #example:[0b10, 127, 2, 1, 0, 127, 2, 0, 127],  # Finger 1 (thumb) - active with 2 waveforms
                [0, 0, 0],                              # Finger 2 (index) - inactive
                [0, 0, 0],                              # Finger 3 (middle) - inactive  
                [0, 0, 0],                              # Finger 4 (ring) - inactive
                [0, 0, 0],                              # Finger 5 (pinky) - inactive
                [0, 0, 0],                              # Palm actuator 1 - inactive
                [0, 0, 0],                              # Palm actuator 2 - inactive
                [0, 0, 0]                               # Palm actuator 3 - inactive
            ]

    rb_v1_data.fingertips_pos = [(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)]


"""
This can switch which endpoint the data is being read from or written to. Either from the C++ SDK or from the simulated glove.

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""


from enum import Enum
from .SG_logger import sg_logger

from . import SG_callback_manager as SG_cb
from . import SG_RB_buffer
from . import transcode as SG_transcode
from . import SG_types as SG_T
from . import SG_simulator

from typing import Sequence, Union

from typing import Dict, List, Optional

_dict_device_id_data_origin : Dict[int, SG_T.Data_Origin] = { }



def get_exo_angles_rad(device_info : SG_T.Device_Info) -> SG_T.Sequence[Sequence[Union[int, float]]]:
    data_origin = _dict_device_id_data_origin[device_info.device_id]

    if data_origin == SG_T.Data_Origin.CPP_SDK or data_origin == SG_T.Data_Origin.LIVE_TEST_SIM:
        buffer = SG_RB_buffer.get_buffer(device_info.device_id)
        return buffer.get_exo_angles_rad()

    # elif data_origin == SG_T.Data_Origin.LIVE_TEST_SIM:
    #     exo_angles = SG_simulator.get_sim(device_info.device_id).get_exo_rad_hand()
    #     return exo_angles
    else:
        raise RuntimeError("DATA_ORIGIN" + str(data_origin) + " not implemented!")
        


def get_force_sensors(device_info : SG_T.Device_Info) -> SG_T.Sequence[Union[int, float]]:
    data_origin = _dict_device_id_data_origin[device_info.device_id]

    if data_origin == SG_T.Data_Origin.CPP_SDK:
        buffer = SG_RB_buffer.get_buffer(device_info.device_id)    
        return buffer.get_forces_sensed()
    else:
        # sg_logger.warn("Get_force_sensors DATA_ORIGIN" + str(data_origin) + " not implemented!")
        pass
    return [-1,-1,-1,-1,-1]


def send_haptic_data(device_info : SG_T.Device_Info):
    """ Sends the haptic data stored in the corresponding buffer to the glove."""
    buffer = SG_RB_buffer.get_buffer(device_info.device_id)
    

    force_data = list(map(list, zip(buffer.data.force_goals, buffer.data.perc_bents_flexion_firmware, buffer.data.control_modes))) 
    vibro_data = buffer.data.raw_vibro_data

    # print("send_haptic_data", "force ", force_data, "vibro ", vibro_data)

    if device_info.data_origin == SG_T.Data_Origin.CPP_SDK:
        SG_cb.send_haptic_data(device_info, force_data, vibro_data)
        
        

def setup_data_origin(device_id : int, data_origin : SG_T.Data_Origin):
    _dict_device_id_data_origin[device_id] = data_origin



def get_data_origin(device_id):
    return _dict_device_id_data_origin[device_id]
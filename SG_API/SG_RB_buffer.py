"""
The goal of this class is to purely temporarily store 1 frame of raw data.
It is purely made to contain or exchange data. The data can be set/retreived from anywhere.
It stores the raw angles and force sensor data coming in.

From there they can be used to calculate the other SG_rembrandt_data data.

Questions? Written by:
- Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api/
Support: https://www.senseglove.com/support/

"""

from .SG_logger import sg_logger
from . import SG_types as SG_T
from SG_API import SG_rembrandt_data as SG_rd
from SG_API import transcode

from typing import Dict


class RB_buffer:
    def __init__(self, device_info):
        """ DO NOT USE CREATE THIS CLASS DIRECTLY. USE create_raw_buffer() INSTEAD. """
        self.device_info = device_info
        self.data = SG_rd.Rembrandt_v1_data(device_id=device_info.device_id, device_info=device_info)


    def update_incoming_data_raw(self, new_raw_data):
        """
        For calls directly from the glove (C++). This data is force and angles packaged together and in raw hall values.
        new_data: expects incoming message [[tracking0,tracking1,tracking2,tracking3,tracking4,tracking5,tracking6,tracking7, force_sensor] for each finger]
        """ 
        if new_raw_data.shape != (5, 9) and self.device_info.nr_fingers_tracking == 5:
            sg_logger.log(f"5 fingers buffer, so angles + force array must have shape (5, 9) (8 angles + 1 force sensor), got {new_raw_data.shape}", level=sg_logger.ERROR)
            return False
        if new_raw_data.shape != (4, 9) and self.device_info.nr_fingers_tracking == 4:
            sg_logger.log(f"4 fingers buffer, so angles + force array must have shape (4, 9) (8 angles + 1 force sensor), got {new_raw_data.shape}", level=sg_logger.ERROR)
            return False
    
        self.update_incoming_exo_angles_rad(transcode.rembrandt_v02.raw_hall_to_rads(new_raw_data[:, :8], self.device_info.exo_linkage_type, self.device_info.hand))
        self.data.forces_sensed = new_raw_data[:, 8].tolist()

    def update_incoming_exo_angles_rad(self, new_exo_angles_rad):
        self.data.exo_angles_rad = new_exo_angles_rad

    def get_exo_angles_rad(self):
        return self.data.exo_angles_rad
    
    def get_forces_sensed(self):
        return self.data.forces_sensed

    def set_raw_vibro_to_send(self, raw_vibro_data):
        self.data.raw_vibro_data = raw_vibro_data

    def get_vibro_to_send(self):
        return self.data.raw_vibro_data






_dict_device_id_raw_devices : Dict[int, RB_buffer] = { }

def create_buffer(device_info : SG_T.Device_Info):
    
    if device_info.device_id not in _dict_device_id_raw_devices:
        buffer = RB_buffer(device_info)
        _dict_device_id_raw_devices[device_info.device_id] = buffer
        return buffer
    else:
        raise RuntimeError(f"Device ID {device_info.device_id} already exists in _dict_device_id_raw_devices {list(_dict_device_id_raw_devices.keys())}")


def get_buffer(device_id : int):
    if device_id in _dict_device_id_raw_devices:
        return _dict_device_id_raw_devices[device_id]
    else:
        raise RuntimeError("Device ID not found in _dict_device_id_raw_devices")


def clear_buffers():
    _dict_device_id_raw_devices.clear()
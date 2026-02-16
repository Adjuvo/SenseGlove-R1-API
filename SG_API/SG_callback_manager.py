"""
Responsible for subscribers for all callbacks such as device connected, data received, etc.

Questions? Written by:
- Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api
Support: https://www.senseglove.com/support/
"""


#!/usr/bin/env python3
import sys

# Configure warnings to always show RuntimeWarnings
#warnings.filterwarnings('always', category=RuntimeWarning)

import threading
device_connected_event = threading.Event()

from typing import Callable, List, Dict, Callable, Generic, TypeVar, List, Tuple


import time
import sys
from . import SG_types as SG_T
import SG_API.transcode.rembrandt_v02 as v02_transcode
import SG_API.SG_data_exchange as SG_data_exch
from .SG_logger import sg_logger
from . import SG_FPS
from . import SG_timer


# needed to make callbacks not fire just on exit while other things already have partially closed down
running = False


# With this you can easily add multiple functions to call on a callback.
Call_T = TypeVar("Call_T", bound=Callable[..., None])

class CallbackManager(Generic[Call_T]):
    def __init__(self):
        global running
        running = True
        self.callbacks: List[Call_T] = []

    def add(self, cb: Call_T):
        if cb not in self.callbacks:
            self.callbacks.append(cb)

    def remove(self, cb: Call_T):
        if cb in self.callbacks:
            self.callbacks.remove(cb)
    
    
    def clear(self):
        self.callbacks.clear()

    def call_all(self, *args, **kwargs):
        for cb in self.callbacks:
            cb(*args, **kwargs)

class CallbackManagerDataOrigin(CallbackManager[Call_T], Generic[Call_T]):

    def call_all(self, device_id, data_origin):
        global running
        if running:
            for cb in self.callbacks:
                if (SG_data_exch.get_data_origin(device_id) == data_origin): # if the device data origin setting matches the origin where the event fired from, the event should fire.
                    cb(device_id)



# How to add to these: 
#on_connected_callback_manager.add(_my_function)

_on_connected_type = Callable[[SG_T.Device_Info], None]
on_connected_callback_manager = CallbackManager[_on_connected_type]()   

_on_disconnected_type = Callable[[int], None]
on_disconnected_callback_manager = CallbackManager[_on_disconnected_type]()     

_on_high_freq_loop = Callable[[], None]
on_high_freq_loop_callback_manager = CallbackManager[_on_high_freq_loop]()



on_data_source_updated = CallbackManagerDataOrigin[Callable[[int], None]]()
"""
Expects a function accepting a device_id. Fires when new data is available in the buffer or other data origin, and only gets called if the device_info.data_origin matches where this event fired from!
(Among others), calls update_data in the rembrandt device
"""

on_new_rembrandt_data = CallbackManager[Callable[[int], None]]()
"""
Gets called once the data in the internal_devices rembrandt is updated. Data can then be retrieved with the SG_main get functions.
"""


# print(dir(RembrandtPySDK)) #prints what is available inside the CPP lib


# This in CPP would be a singleton implementation. Since that is weird in python, I kept everything global.


# These lists contain all callbacks that should be fired when the corresponding event gets fired. 
# You can add or remove callbacks from these lists using the corresponding functions.

# expects function accepting a device_id that is disconnected





#------------------------------------ Loop functionality: Triggering a >1khz internal loop -----------------------------------




_high_freq_timer_id = SG_timer.create_timer(frequency_hz=2000)

# Define timer callback - this replaces all the platform-specific code!
def _on_high_freq_timer(timer_id, missed_events):
    global on_high_freq_loop_callback_manager
    on_high_freq_loop_callback_manager.call_all()
    if missed_events > 0:
        sg_logger.warn(f"Missed {missed_events} high frequency timer events")
        

# Subscribe to timer events
SG_timer.subscribe_timer_callback(_high_freq_timer_id, _on_high_freq_timer)

def init_high_freq_timer():
    SG_timer.start_timer(_high_freq_timer_id)

# ------------------------------------------------------------------------------------------------------

def clear_callbacks():
    global on_connected_callback_manager
    global on_disconnected_callback_manager
    global on_new_rembrandt_data
    global on_data_source_updated
    global on_high_freq_loop_callback_manager
    on_connected_callback_manager.clear()
    on_disconnected_callback_manager.clear()
    on_new_rembrandt_data.clear()
    on_data_source_updated.clear()
    on_high_freq_loop_callback_manager.clear()



def device_com_connected_callback(device_info : SG_T.Device_Info):

    # Call user-defined callback if set
    for cb in on_connected_callback_manager.callbacks:
        try:
            cb(device_info)
        except Exception as e:
            sg_logger.warn("Error in user-defined callback:" + repr(e))
            raise  # Re-raise for debugging

    device_connected_event.set()


def send_haptic_data(device_info : SG_T.Device_Info, force_data : List[List[int]], vibro_data : List[List[int]]):
    from . import SG_CPP_SDK
    if device_info.data_origin == SG_T.Data_Origin.CPP_SDK and SG_CPP_SDK.USE_CPP_SDK:
        SG_CPP_SDK.send_haptic_data_cpp(device_info.device_id, force_data, vibro_data)


#--------------------------------------------- Called from CPP Library -------------------------------------



   
CPP_active = False


def init():
    global CPP_active
    from . import SG_CPP_SDK
    if SG_CPP_SDK.USE_CPP_SDK:
        SG_CPP_SDK.init()
        CPP_active = True


def close():
    global CPP_active
    global running
    running = False
    clear_callbacks()

    if CPP_active:
        from . import SG_CPP_SDK
        if SG_CPP_SDK.USE_CPP_SDK:
            return SG_CPP_SDK.close()


if __name__ == '__main__':
    init()

    sleep_duration = 60
    sg_logger.log("Rembrandt Client - Sleeping for", sleep_duration, "seconds...", level=sg_logger.USER_INFO)
    time.sleep(sleep_duration)

    sys.exit(close())
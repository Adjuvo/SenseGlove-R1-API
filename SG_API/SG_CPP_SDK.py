"""
This is the first arrival point of the data coming from the USB connection of the R1, from the C++ SDK.
This script is responsible for the C++ SDK of the Rembrandt glove. It receives/sends the USB data from C++, and calls the connection and on_data_received callbacks, and all subscribers of those.
These subscribers such as the SG_devices.py then populates the SG_data_exchange.py with the data, which is then used to update the internal data of SG_devices buffer via SG_devices.update_data, so it is retrievable by the user.

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

USE_CPP_SDK = True


from typing import Any, Callable, List, Dict, Callable, Generic, TypeVar, List, Tuple
from .SG_logger import sg_logger
from . import SG_RB_buffer
from . import SG_types as SG_T
from . import SG_callback_manager as SG_cb
from typing import Sequence

import os
import warnings
import platform
import traceback
import sys
import numpy as np
import threading
import time


if USE_CPP_SDK:
    from . import CPPlibs as _cpp_libs

    RembrandtPySDK = getattr(_cpp_libs, "RembrandtPySDK", None)  # type: ignore
    if RembrandtPySDK is None or not _cpp_libs.is_rembrandt_sdk_loaded():
        load_error = _cpp_libs.get_rembrandt_sdk_load_error() or "Unknown error while importing RembrandtPySDK."
        sg_logger.log("Failed to import RembrandtPySDK. " + load_error, level=sg_logger.ERROR)
        raise RuntimeError(load_error)

    
    # Get CPPlibs directory (relative to this file)
    CPPLIBS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CPPlibs")

    # Add to sys.path for Python module import
    if CPPLIBS_DIR not in sys.path:
        sys.path.insert(0, CPPLIBS_DIR)

    # Add DLL directory on Windows
    if platform.system() == "Windows":
        os.add_dll_directory(CPPLIBS_DIR)


    _CPP_device_dict : Dict[int, Any] = {}

    lib = None
    device_connected_handle = None
    device_disconnected_handle = None
    dm = None # device manager
    

    # (Optionally, you can store these handles for later unsubscription, but this should already be handled within the C++ lib.)

    # Callback for device-disconnected events.
    def device_disconnected_callback_CPP(device_info):
        
        sg_logger.log("Rembrandt Client - Device Disconnected!", level=sg_logger.INFO)
        sg_logger.log("Device Info: Vendor ID:", device_info.GetVendorId(), "Device ID:", device_info.GetDeviceId(), level=sg_logger.INFO)      
        _remove_CPP_device(device_info.GetDeviceId())

        try:
            SG_cb.on_disconnected_callback_manager.call_all(device_info.GetDeviceId())
            # Buffer cleanup handled by Python garbage collection
        except Exception as e:
            raise RuntimeError(f"Error in user-defined callback: {e}") from e




    # buff = SG_buff.get_buffers(device.GetDeviceInfo().GetDeviceId())
    # if buff is not None:
    #     buff.set_receive_data(data) 
        #on_data_source_updated.call_all(device.GetDeviceInfo().GetDeviceId(), SG_T.Data_Origin.CPP_SDK) (is called from inside the buffer)


        # this triggers on_data_source_updated. And when that triggers, SG_devices rembrandt update_data() triggers, doing kinematics and populating rembrandt data the user can retrieve.
        # then in that function, it calls: on_new_rembrandt_data.call_all(self._device_id) 
        # so it arrives back here after all users operations in on_new_rembrandt_data subscription have been completed.

    #device.SendHapticData(buff.)
    
    # Callback for data received events.
    def on_data_received_callback_CPP(device, data : Sequence[Sequence[int]]):
        """
        outputs nested list [fingerNr][data_nr]. First 8 data points are raw hall data of splay until fingertip exo rots.  The one after is the force sensor.
        """
        # Convert List[List[int]] from C++ to numpy array
        if isinstance(data, list):
            data = np.array(data, dtype=np.int32)

        device_id = device.GetDeviceInfo().GetDeviceId()
        
        raw_buffer = SG_RB_buffer.get_buffer(device_id)
        if raw_buffer is not None:
            if raw_buffer.device_info.data_origin == SG_T.Data_Origin.CPP_SDK: 
                raw_buffer.update_incoming_data_raw(data)
                SG_cb.on_data_source_updated.call_all(device_id, SG_T.Data_Origin.CPP_SDK)


        
    # Callback for force data received events.
    def on_force_data_received_callback_CPP(device, data : List[int]):
        pass

        

    # Callback for tracking data received events directly from cpp
    def on_tracking_data_received_callback_CPP(device : int, data : List[List[int]]):
        # Convert List[List[int]] from C++ to numpy array
        if isinstance(data, list):
            data = np.array(data, dtype=np.int32).tolist()
        # TODO: Process tracking data as numpy array
        pass


    def send_force_control(device_id : int, data : List[List[int]]):
        device = _get_CPP_device(device_id)
        # sg_logger.log("force data sent to glove", data, level=sg_logger.USER_INFO)
        if device is not None:
            # Convert numpy array to List[List[int]] for C++ layer
            if isinstance(data, np.ndarray):
                data = data.tolist()
            
            #data = [[20, 65535, 0], [20, 65535, 0], [20, 65535, 0], [20, 0, 0], [20, 0, 0]]
            if len(data) == 4:
                data_np = np.array(data)
                data_np = data_np + [[123, 123, 123]] # sdk expects 5 fingers, so we add a dummy finger to support 4 fingered prototypes.
            result = device.SendForceData(data_np)
        else:
            sg_logger.warn("No physical device connected, so not sending forces for device_id: " + str(device_id))


    def send_haptic_data_cpp(device_id : int, force_data : SG_T.List[List[int]], vibration_data : SG_T.List[List[int]]):
        """
        Send combined haptic data (force + vibration) to CPP device.
        
        Args:
            device_id: Device identifier
            force_data: List of 5 force goals per finger (thumb to pinky)
            vibration_data: List of 8 vibration goals
        """
        device = _get_CPP_device(device_id)
        if device is not None:
            # Prepare force data: [[force_goal, mode, velocity_wire], ...]
            # Using dummy/test data for now - replace with actual conversion logic
            # outForceData = [
            #     [0, 8, 16],      # Thumb
            #     [32, 64, 128],   # Index
            #     [256, 512, 1024], # Middle
            #     [2048, 4096, 8192], # Ring
            #     [2048, 4096, 8192]  # Pinky
            # ]
            
            # # Prepare vibration data: per vibration actuator (each finger + 3 palm)
            # # Format: [command | Amplitude | total waveforms | waveform1_index, waveform1_phase, waveform1_amplitude | waveform2_index, waveform2_phase, waveform2_amplitude]
            # # Using dummy/test data for now
            # outVibroData = [
            #     [0b10, 127, 2, 1, 0, 127, 2, 0, 127],  # Finger 1 (thumb) - active with 2 waveforms
            #     [0, 0, 0],                              # Finger 2 (index) - inactive
            #     [0, 0, 0],                              # Finger 3 (middle) - inactive  
            #     [0, 0, 0],                              # Finger 4 (ring) - inactive
            #     [0, 0, 0],                              # Finger 5 (pinky) - inactive
            #     [0, 0, 0],                              # Palm actuator 1 - inactive
            #     [0, 0, 0],                              # Palm actuator 2 - inactive
            #     [0, 0, 0]                               # Palm actuator 3 - inactive
            # ]
            
            
            # Handle 4-finger devices (add dummy finger)
            if len(force_data) == 4:
                force_data = force_data[:4] + [[0, 0, 0]]  # Add dummy 5th finger
                
            try:
                # Log the data format for debugging
                sg_logger.log(f"Sending force data: {force_data}", level=sg_logger.DEBUG)
                sg_logger.log(f"Sending vibration data: {vibration_data}", level=sg_logger.DEBUG)
                
                result = device.SendHapticsData(force_data, vibration_data)
                sg_logger.log(f"SendHapticsData result: {result}", level=sg_logger.DEBUG)
            except Exception as e:
                sg_logger.log(f"Failed to send haptic data: {e}", level=sg_logger.ERROR)
                
        else:
            sg_logger.warn("No physical device connected, so not sending haptic data for device_id: " + str(device_id))



    def _ensure_cpp_logging_enabled():
        if os.environ.get("REMBRANDT_CPP_LOGS", "").strip().lower() in {"0", "false", "no", "off"}:
            return
        if any(
            arg == "-v"
            or arg.startswith("-v")
            or arg.startswith("-verbosity")
            or arg.startswith("--verbosity")
            for arg in sys.argv
        ):
            return
        # loguru expects a verbosity value after -v (e.g. INFO or 0)
        sys.argv.extend(["-v", "INFO"])

    def _write_cpp_init_watchdog_notice(message: str) -> None:
        try:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "cpp_init_watchdog.log")
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(f"[{timestamp}] {message}\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            pass

    def init():
        global lib
        global device_connected_handle
        global device_disconnected_handle
        global dm

        if lib == None:
            sg_logger.info("Initializing Rembrandt C++ SDK")
            _ensure_cpp_logging_enabled()
            # Get the singleton Library instance.
            lib = RembrandtPySDK.Library.GetInstance()

            # Initialize the library.
            try:
                init_done = threading.Event()
                watchdog_seconds = float(os.environ.get("REMBRANDT_CPP_INIT_WATCHDOG_SEC", "1"))
                def _init_watchdog():
                    if not init_done.is_set():
                        message = (
                            "Rembrandt C++ SDK init appears stuck. "
                            "Check SG_API/logs/cpp_boot.log for progress."
                        )
                        sg_logger.log(message, level=sg_logger.ERROR)
                        _write_cpp_init_watchdog_notice(message)
                watchdog = threading.Timer(watchdog_seconds, _init_watchdog)
                watchdog.daemon = True
                watchdog.start()
                start_message = (
                    "Starting R1 C++ SDK. "
                    "If it hangs or crashes directly after this message, send SG_API/logs/cpp_boot.log and the newest examples/logs/ file to SenseGlove support."
                )
                sg_logger.info(start_message, level=sg_logger.USER_INFO)
                _write_cpp_init_watchdog_notice(start_message)
                init_success = lib.Initialize()
                init_done.set()
                watchdog.cancel()
                sg_logger.info("R1 C++ SDK initialized successfully.", level=sg_logger.USER_INFO)
                if not init_success:
                    raise RuntimeError("Failed to initialize the SGRembrandt Library.")
            except Exception as e:
                sg_logger.log(f"Initialization error: {e}", level=sg_logger.ERROR)
                raise RuntimeError(f"Initialization error: {e}") from e

            sg_logger.info(f"Library version: {RembrandtPySDK.Library.Version()}")

            # Get the singleton DeviceManager instance.
            dm = RembrandtPySDK.DeviceManager.GetInstance()

            # Subscribe to device-connected events.
            try:
                device_connected_handle = dm.SubscribeOnDeviceConnected(device_connected_callback_CPP)
            #    warnings.warn("Subscribed to device connected events.")
            except Exception as e:
                sg_logger.log(f"Failed to subscribe to OnDeviceConnected: {e}", level=sg_logger.ERROR)
                raise RuntimeError(f"Failed to subscribe to OnDeviceConnected: {e}") from e

            # Subscribe to device-disconnected events.
            try:
                device_disconnected_handle = dm.SubscribeOnDeviceDisconnected(device_disconnected_callback_CPP)
            #    warnings.warn("Subscribed to device disconnected events.")
            except Exception as e:
                sg_logger.log(f"Failed to subscribe to OnDeviceDisconnected: {e}", level=sg_logger.ERROR)
                raise RuntimeError(f"Failed to subscribe to OnDeviceDisconnected: {e}") from e
        else:
            sg_logger.warn("Lib already initialized, so skipping initialization")



    def close():
        # Unsubscribe from device-connected events.
        if dm:
            try:
                unsub_dc = dm.UnsubscribeOnDeviceConnected(device_connected_handle)
            #    warnings.warn("Unsubscribed from device connected events.")
            except Exception as e:
                sg_logger.log(f"Failed to unsubscribe from OnDeviceConnected: {e}", level=sg_logger.ERROR)
                raise RuntimeError(f"Failed to unsubscribe from OnDeviceConnected: {e}") from e

            # Unsubscribe from device-disconnected events.
            try:
                unsub_dd = dm.UnsubscribeOnDeviceDisconnected(device_disconnected_handle)
            #    warnings.warn("Unsubscribed from device disconnected events.")
            except Exception as e:
                sg_logger.log(f"Failed to unsubscribe from OnDeviceDisconnected: {e}", level=sg_logger.ERROR)
                raise RuntimeError(f"Failed to unsubscribe from OnDeviceDisconnected: {e}") from e
        


        # Terminate the library.
        if lib:
            try:
                term_success = lib.Terminate()
                if not term_success:
                    raise RuntimeError("Failed to terminate the SGRembrandt Library.")
            except Exception as e:
                sg_logger.log(f"Termination error: {e}", level=sg_logger.ERROR)
                raise RuntimeError(f"Termination error: {e}") from e

            # warnings.warn("SGRembrandt Library terminated successfully.")
        return 0




    def _add_CPP_device(id, CPP_device):
        global _CPP_device_dict
        if id not in _CPP_device_dict:
                _CPP_device_dict[id] = CPP_device

    def _remove_CPP_device(id):
        global _CPP_device_dict
        _CPP_device_dict.pop(id, None)

    def _get_CPP_device(device_id : int):
        global _CPP_device_dict
        device = None
        if device_id in _CPP_device_dict:
            device = _CPP_device_dict[device_id]
            return device
        else:
            sg_logger.warn("deviceId " + str(device_id) + " not found in active CPP devices")
            return None





def get_exo_type_from_device_connect(device_id : int):
    if device_id < 10:
        return SG_T.Exo_linkage_type.REMBRANDT_PROTO_02
    elif device_id >= 30 and device_id < 40:
        return SG_T.Exo_linkage_type.REMBRANDT_PROTO_03
    elif device_id >= 40 and device_id < 50:
        return SG_T.Exo_linkage_type.REMBRANDT_PROTO_04
    elif device_id >= 50 and device_id < 60:
        return SG_T.Exo_linkage_type.REMBRANDT_PROTO_05
    else:
        raise RuntimeError("Device ID not in the range defining exoskeletons")


def get_handedness_from_CPP(CPP_device_info):

    if CPP_device_info.GetHandedness() == "L":
        return SG_T.Hand.LEFT
    elif CPP_device_info.GetHandedness() == "R":
        return SG_T.Hand.RIGHT
    else:
        raise RuntimeError("Invalid handedness")

def get_firmware_version_from_CPP(CPP_device_info):
    firmware_version = CPP_device_info.GetFirmwareVersion()
    # if(firmware_version == "?.?.?"):
    #     return python_firmware_version
    # else:
    #     split_firmware_version = firmware_version.split(".")
    #     python_firmware_version = SG_T.Firmware_version(int(split_firmware_version[0]), int(split_firmware_version[1]), int(split_firmware_version[2]))
    return firmware_version



# Callback for device-connected events.
def device_connected_callback_CPP(device):
     # device is a RembrandtDevice instance.
    CPP_device_info = device.GetDeviceInfo()

    sg_logger.log("Connected: Device Info: Vendor ID:", "Device ID:", CPP_device_info.GetDeviceId(), CPP_device_info.GetVendorId(), "Product ID:", CPP_device_info.GetProductId(), level=sg_logger.INFO)
    
    _add_CPP_device(CPP_device_info.GetDeviceId(), device)
    #sg_logger.log("Device created and connected:", device.IsConnected(), level=sg_logger.USER_INFO)



    device_info = SG_T.Device_Info(
        device_id=CPP_device_info.GetDeviceId(),
        hand=get_handedness_from_CPP(CPP_device_info),
        nr_fingers_tracking=int(CPP_device_info.GetFingers()),
        nr_fingers_force=4,
        firmware_version=get_firmware_version_from_CPP(CPP_device_info),
        device_type=SG_T.DeviceType.REMBRANDT,
        communication_type=SG_T.Com_type.REAL_GLOVE_USB,
        exo_linkage_type=get_exo_type_from_device_connect(CPP_device_info.GetDeviceId()),
        encoding_type=SG_T.Encoding_type.REMBRANDT_v01,
        data_origin=SG_T.Data_Origin.CPP_SDK
    ) # switch to CPP and remove everything with buff in this script to get pure callbacks.
    
    SG_cb.device_com_connected_callback(device_info)
    
    # Subscribe to data events on the device.
    try:
        # Subscribe to OnDataReceived
        data_handle = device.SubscribeOnDataReceived(on_data_received_callback_CPP) 
        sg_logger.log("Successfully subscribed to OnDataReceived!", level=sg_logger.INFO)
    except Exception as e:
        sg_logger.log("Failed to subscribe to OnDataReceived:", e, level=sg_logger.ERROR)
        raise RuntimeError(f"Failed to subscribe to OnDataReceived: {e}") from e

    try:
        force_handle = device.SubscribeOnForceDataReceived(on_force_data_received_callback_CPP)
        sg_logger.log("Successfully subscribed to OnForceDataReceived!", level=sg_logger.INFO)
    except Exception as e:
        sg_logger.log("Failed to subscribe to OnForceDataReceived:", e, level=sg_logger.ERROR)
        raise RuntimeError(f"Failed to subscribe to OnForceDataReceived: {e}") from e

    try:
        tracking_handle = device.SubscribeOnTrackingDataReceived(on_tracking_data_received_callback_CPP)
        sg_logger.log("Successfully subscribed to OnTrackingDataReceived!", level=sg_logger.INFO)
    except Exception as e:
        sg_logger.log("Failed to subscribe to OnTrackingDataReceived:", e, level=sg_logger.ERROR)
        raise RuntimeError(f"Failed to subscribe to OnTrackingDataReceived: {e}") from e
    
    






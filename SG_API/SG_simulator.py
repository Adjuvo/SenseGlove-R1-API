"""
SenseGlove Rembrandt Simulator Module

This module provides glove simulation functionality for testing and development when no physical 
device is connected. It simulates finger tracking data with various animation modes.

The simulator can generate realistic finger movements for:
- Static poses (STEADY_MODE)
- Sine wave animations (SINE_MODE) 
- Finger open/close cycles (FINGERS_OPEN_CLOSE)

**Basic Usage:**
```python
import SG_API.SG_simulator as SG_sim

# Create a simulated left hand with finger animation
device_info = SG_T.Device_Info(device_id=123, handedness=SG_T.Hand.LEFT)
sim = SG_sim.create_glove_sim_device(device_info, SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)

# Update simulation in your main loop
while True:
    SG_sim.update_all_glove_sims()
    time.sleep(0.001)


# You can then read data from SG_main like usual, but the output will be coming from the simulated glove.
```

Questions? Written by:
- Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api/
Support: https://www.senseglove.com/support/
"""


from SG_API import SG_main, SG_types as SG_T

import threading
import numpy as np
from enum import Enum
import math
import time
from typing import Dict, List, Optional, Callable, Sequence, Union
import inspect

from SG_API import SG_math
from SG_API import SG_callback_manager as SG_cb
from SG_API import SG_RB_buffer
from SG_API.SG_logger import sg_logger



def _validate_angles_array(angles : SG_T.Sequence[Sequence[Union[int, float]]], device_info : SG_T.Device_Info, function_name : str):
    """Validate angle array dimensions and type"""
    if angles is None:
        sg_logger.log(f"{function_name}: angles array cannot be None", level=sg_logger.ERROR)
        return False
    
    try:
        angles_array = np.asarray(angles)
        if (angles_array.shape != (5, 8) and device_info.nr_fingers_tracking == 5):
            sg_logger.log(f"{function_name}: 5 fingers simulator, so angles array must have shape (5, 8), got {angles_array.shape}", level=sg_logger.ERROR)
            return False
        if (angles_array.shape != (4,8) and device_info.nr_fingers_tracking == 4):
            sg_logger.log(f"{function_name}: 4 fingers simulator, so angles array must have shape (4, 8), got {angles_array.shape}", level=sg_logger.ERROR)
            return False
        
           
    except Exception as e:
        sg_logger.log(f"{function_name}: invalid angles array - {str(e)}", level=sg_logger.ERROR)
        return False
    
    return True

class Simulation_Mode(Enum):
    """
    Enumeration of available simulation modes for the glove simulator.
    
    **Modes:**
    - **STEADY_MODE**: Static finger pose, no animation
    - **SINE_MODE**: Sine wave oscillations across all finger joints
    - **FINGERS_OPEN_CLOSE**: Smooth finger opening and closing cycles
    
    **Examples:**
    ```python
    # Set different animation modes
    SG_sim.set_mode(device_id, SG_sim.Simulation_Mode.STEADY_MODE)
    SG_sim.set_mode(device_id, SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
    ```
    """
    STEADY_MODE = "steady"
    SINE_MODE = "sine"
    FINGERS_OPEN_CLOSE = "fingers_open_close"
    CUSTOM_FUNCTION = "custom_function"

def smoothstep(t):
    """
    Smooth interpolation function for easing animations.
    
    **Args:**
        t (float): Input value between 0 and 1
        
    **Returns:**
        float: Smoothed output value between 0 and 1
        
    Uses the smoothstep formula: t² × (3 - 2t) for smooth acceleration/deceleration.
    """
    return t * t * (3 - 2 * t)  # Custom easing function

class Glove_Simulator:
    """
    Simulates a SenseGlove Rembrandt device for testing and development.
    
    Provides realistic finger tracking data without requiring physical hardware.
    Supports multiple animation modes and allows manual control of finger positions.
    
    **Attributes:**
        device_id (int): Unique identifier for this simulated device
        mode (Simulation_Mode): Current animation mode
        running (bool): Whether simulation is active
        
    **Examples:**
    ```python
    # Create simulator with finger animation
    sim = Glove_Simulator(device_id=123, mode=Simulation_Mode.FINGERS_OPEN_CLOSE)
    
    # Update simulation in loop
    while sim.running:
        sim.update()
        time.sleep(0.001)
    ```
    """



    def __init__(self, device_info : SG_T.Device_Info, mode):
        """
        Initialize a new glove simulator instance.
        
        **Args:**
            device_id (int): Unique device identifier for this simulator
            mode (Simulation_Mode): Animation mode to use
            
        **Examples:**
        ```python
        sim = Glove_Simulator(123, Simulation_Mode.SINE_MODE)
        ```
        """
        self.device_id = device_info.device_id
        self.device_info = device_info
        self.mode = mode
        #self.buffers = SG_buff.create_buffers(device_id, SG_T.Encoding_type.REMBRANDT_v01)
        self.running = True

        _angles_deg_single_finger = np.array([0, -15, 45, -90, 120, -100, 90, 90]) 
        angles_rad_single_finger = np.radians(_angles_deg_single_finger)
        self.starting_angles_rad_hand = np.tile(angles_rad_single_finger, (5, 1))
        self.set_exo_rad_hand(self.starting_angles_rad_hand.copy())  # Initialize current angles

        self.i = 0
        self.prev_time = time.perf_counter()
        self.t = 0

        self.custom_sim_fn = None  #Custom Update function for when CUSTOM_FUNCTION is chosen.

    def restart(self):
        """
        Restart the simulator with current settings.
        
        Resets all animation timers and returns to initial finger positions.
        
        **Examples:**
        ```python
        sim.restart()  # Reset animation to beginning
        ```
        """
        self.__init__(self.device_info, self.mode)


    def stop(self):
        """
        Stop the simulator from updating.
        
        Sets running flag to False, preventing further animation updates.
        
        **Examples:**
        ```python
        sim.stop()  # Stop animation
        ```
        """
        self.running = False

    def update_exo_hand_angles_rad(self, exo_angles_rad : SG_T.Sequence[Sequence[Union[int, float]]]):
        """
        Update the exoskeleton joint angles in radians without changing the starting angles (which are used for base of open/close etc).
        So this is for calls from the update, and set_exo_rad_hand is for the user.
        
        **Args:**
            exo_angles_rad (SG_T.Sequence[Sequence[Union[int, float]]]): Joint angles in radians
        """
        if not _validate_angles_array(exo_angles_rad, self.device_info, "set_exo_rad_hand"):
            return

        # Check for reasonable angle ranges (in radians: -π to π, in degrees: -180 to 180)
        if np.any(np.abs(exo_angles_rad) > 10):  # 10 radians ≈ 573 degrees, catches obvious degree/radian mixups
            sg_logger.log(f"set_exo_rad_hand: angles seem unusually large (>10 radians). Check if you meant to use degrees instead of radians", level=sg_logger.WARNING)
            return

        SG_RB_buffer.get_buffer(self.device_id).update_incoming_exo_angles_rad(exo_angles_rad)
        SG_cb.on_data_source_updated.call_all(self.device_id, SG_T.Data_Origin.LIVE_TEST_SIM)
        #print("exo_angles_simulation_buffer after setting: " + sg_logger.nested_array_to_str(SG_RB_buffer.get_buffer(self.device_id).get_exo_angles_rad()))


    def update(self):
        """
        Update the simulation for one frame. This is called automatically by update_all_glove_sims (called by SG_main.update)
        
        Calculates new finger positions based on the current simulation mode:
        - SINE_MODE: Applies sine wave oscillations to all joints
        - FINGERS_OPEN_CLOSE: Smooth finger opening/closing cycles
        - STEADY_MODE: Maintains static finger positions
        """
        self.dt = time.perf_counter() - self.prev_time

        if self.mode == Simulation_Mode.SINE_MODE:
            self.i += 2 * self.dt
            self.update_exo_hand_angles_rad(self.starting_angles_rad_hand + np.sin(self.i))
        
        if self.mode == Simulation_Mode.FINGERS_OPEN_CLOSE:
            self.t += self.dt * 20  # Keep time increasing normally

            MIN_ANGLE_RAD = math.radians(55)  # Set your minimum angle (e.g., 10°)
            MAX_ANGLE_RAD = math.radians(90)  # Set your maximum angle (e.g., 60°)

            # Smooth oscillation between 0 and 1
            t_normalized = 0.5 * (1 - math.cos(2 * math.pi * self.t))  

            # Scale the angle to fit between MIN and MAX
            angle = MIN_ANGLE_RAD + smoothstep(t_normalized) * (MAX_ANGLE_RAD - MIN_ANGLE_RAD)
            self.update_exo_hand_angles_rad(self.starting_angles_rad_hand + np.cos(angle))

        if self.mode == Simulation_Mode.STEADY_MODE:
            # don't change the data, do call the callback update
            SG_cb.on_data_source_updated.call_all(self.device_id, SG_T.Data_Origin.LIVE_TEST_SIM)
            pass

        if self.mode == Simulation_Mode.CUSTOM_FUNCTION:
            
            if self.custom_sim_fn is None:
                print(f"WARNING: Mode is CUSTOM_FUNCTION, but no update function was set! Use SG_main.SG_sim.set_simulation_fn(hand_id, test_custom_fn) to do so!")
                print(f"If you only see this warning once, you're likely switching to CUSTOM_FUNCTION mode before setting your function. In that case, you can ignore this.")
                pass

            self.t += self.dt
            new_exo_angles_rad = self.custom_sim_fn(self.t) #new_exo_angles_rad is passed into custom_sim_fn, and can be edited at any time inside it. Todo: Add dT?
            
            #validate that it's actually valid!
            #if not self.is_exo_angles_type(new_exo_angles_rad):
            #    raise TypeError(
            #        f"update_fn returned invalid type: {type(new_exo_angles_rad)}. "
            #        f"Expected Sequence[Sequence[Union[int, float]]] structure."
            #    )
            self.update_exo_hand_angles_rad(new_exo_angles_rad)  # type: ignore (Since we check beforehand that this is indeed the correct type)
        
        self.prev_time = time.perf_counter()
        





    def set_simulation_mode(self, mode : Simulation_Mode):
        """
        Change the simulation animation mode.
        
        **Args:**
            mode (Simulation_Mode): New animation mode to use
            
        **Examples:**
        ```python
        sim.set_simulation_mode(Simulation_Mode.SINE_MODE)     # Switch to sine waves
        sim.set_simulation_mode(Simulation_Mode.STEADY_MODE)   # Switch to static pose
        ```
        """
        if not _validate_simulation_mode(mode):
            return
        self.mode = mode


    def set_simulation_fn(self, update_fn : Callable[[float], SG_T.Sequence[Sequence[Union[int, float]]]]): 
        
        sig = inspect.signature(update_fn)
        params = sig.parameters

        # Does it have the correct amount of parameters?
        if len(params) != 1:
            raise TypeError(f"{update_fn.__name__} must take exactly one argument (t: float), got {len(params)}")
        
        # Check type annotation (recommended but not required as long as you know what you're doing.)
        param_name = next(iter(params))
        param = params[param_name]
        if param.annotation != float:
            print(f"WARNING: {update_fn.__name__} parameter '{param_name}' is meant to represent simulation time. We recommend annotating it as float, got {param.annotation}")

        # Check if it has a return type defined
        if sig.return_annotation == inspect.Signature.empty:
            print(f"WARNING: {update_fn.__name__} has no return annotation! We expect a return type -> SG_T.Sequence[Sequence[Union[int, float]]], so make sure you do return this type.")

        # does the output make sense?
        test_output = update_fn(0)
        if not is_exo_angles_type(test_output):
            raise TypeError(
                f"update_fn returned invalid type: {type(test_output)}. "
                f"Expected Sequence[Sequence[Union[int, float]]] structure."
            )
        
        self.custom_sim_fn = update_fn


    def get_exo_rad_hand(self) -> SG_T.Sequence[Sequence[Union[int, float]]]:
        # Get current exoskeleton joint angles in radians.
        
        # **Returns:**
        #     SG_T.Sequence[Sequence[Union[int, float]]]: Current finger joint angles in radians
            
        # Can be indexed as `angles[finger_nr][joint_nr]` where:
        # - finger_nr: 0=thumb, 1=index, 2=middle, 3=ring, 4=pinky
        # - joint_nr: 0=splay, 1+=flexion joints
        
        # **Examples:**
        # ```python
        # angles = sim.get_exo_rad_hand()
        # thumb_splay = angles[0][0]      # Thumb splay angle
        # index_flex1 = angles[1][1]      # Index first flexion
        # ```
        return SG_RB_buffer.get_buffer(self.device_id).get_exo_angles_rad()
    

    def set_exo_rad_hand(self, exo_rad_hand_angles : SG_T.Sequence[Sequence[Union[int, float]]]):
        """
        Set exoskeleton joint angles in radians. Also saves it to the simulation starting angles, so all simulation functions (such as open close) will be done around these initial angles.
        
        **Args:**
            exo_rad_hand_angles (SG_T.Sequence[Sequence[Union[int, float]]]): Joint angles in radians
            
        Updates both current and starting angles for the simulation.
        
        **Examples:**
        ```python
        # Set custom finger pose
        import numpy as np

        zero_angles = np.zeros((5, 8))  # 5 fingers, 8 joints each, this would be setting all exo linkages in a straight long line (not a natural pose)

        
        angles_rad_single_finger = np.radians(_angles_deg_single_finger) # convert to radians
        angles = np.tile(angles_rad_single_finger, (5, 1))               # create array using the the single finger angles for all fingers

        angles[1][2] = 0.5        # Bend index finger second joint
        sim.set_exo_rad_hand(angles)
        ```
        """

        self.update_exo_hand_angles_rad(exo_rad_hand_angles)

        self.starting_angles_rad_hand = exo_rad_hand_angles


       
    def set_exo_deg_hand(self, exo_deg_hand_angles : SG_T.Sequence[Sequence[Union[int, float]]]):
        """
        Set exoskeleton joint angles in degrees.
        
        **Args:**
            exo_deg_hand_angles (SG_T.Sequence[Sequence[Union[int, float]]]): Joint angles in degrees
            
        Convenience method that converts degrees to radians internally.
        
        **Examples:**
        ```python
        # Set finger pose in degrees (easier to visualize)
        import numpy as np
        angles = np.zeros((5, 8))  # 5 fingers, 8 joints each, this would be setting all exo linkages in a straight long line (not a natural pose)

        angles_deg_single_finger = np.array([0, -15, 45, -90, 120, -100, 90, -50]) # this is a more natural starting pose for a single finger
        angles = np.tile(angles_deg_single_finger, (5, 1))               # create array using the the single finger angles for all fingers
        angles[1][2] = 30         # Bend index exo joint 2 30 degrees

        sim.set_exo_deg_hand(angles)
        ```
        """
       
        if not _validate_angles_array(exo_deg_hand_angles, self.device_info, "set_exo_deg_hand"):
            return
            
        if np.any(np.abs(exo_deg_hand_angles) > 360):
            sg_logger.log(f"set_exo_deg_hand: angles seem unusually large (>360 degrees). Check your input values", level=sg_logger.WARNING)

        
        self.starting_angles_rad_hand = SG_math.radians(exo_deg_hand_angles)
        self.set_exo_rad_hand(self.starting_angles_rad_hand)




_dict_device_id_Live_Test: Dict[int, Glove_Simulator] = { }





def _validate_simulation_mode(mode):
    """Validate simulation mode"""
    if not isinstance(mode, Simulation_Mode):
        sg_logger.log(f"mode must be a SG_simulator.Simulation_Mode enum, got {type(mode)}. Valid modes: {[m.value for m in Simulation_Mode]}", level=sg_logger.ERROR)
        return False
    return True


def set_angles_rad(device_info : SG_T.Device_Info, exo_angles_rad_hand : SG_T.Sequence[Sequence[Union[int, float]]]):
    """
    Set finger joint angles for a simulated device (radians).
    
    **Args:**
        device_id (int): Device ID of the simulator
        exo_angles_rad_hand (SG_T.Sequence[Sequence[Union[int, float]]]): Joint angles in radians
        
    **Examples:**
    ```python
    zero_angles = np.zeros((5, 8))  # 5 fingers, 8 joints each, this would be setting all exo linkages in a straight long line (not a natural pose)

    
    angles_rad_single_finger = np.radians(_angles_deg_single_finger) # convert to radians
    angles = np.tile(angles_rad_single_finger, (5, 1))               # create array using the the single finger angles for all fingers

    angles[1][2] = 0.5        # Bend index finger second joint

    SG_sim.set_angles_rad(123, angles)
    ```
    """
    if not _validate_angles_array(exo_angles_rad_hand, device_info, "set_angles_rad"):
        return
        
    get_sim(device_info.device_id).set_exo_rad_hand(exo_angles_rad_hand)

def set_angles_deg(device_info : SG_T.Device_Info, exo_angles_deg_hand : SG_T.Sequence[Sequence[Union[int, float]]]):
    """
    Set finger joint angles for a simulated device (degrees).
    
    **Args:**
        device_info: DeviceInfo of the simulator
        exo_angles_deg_hand (SG_T.Sequence[Sequence[Union[int, float]]]): Joint angles in degrees
        
    **Examples:**
    ```python
    # Set finger pose in degrees (easier to visualize)
    import numpy as np
    angles = np.zeros((5, 8))  # 5 fingers, 8 joints each, this would be setting all exo linkages in a straight long line (not a natural pose)

    angles_deg_single_finger = np.array([0, -15, 45, -90, 120, -100, 90, -50]) # this is a more natural starting pose for a single finger
    angles = [angles_deg_single_finger.copy() for _ in range(5)]  # Create list of arrays, one per finger
    angles[1][2] = 30         # Bend index exo joint 2 30 degrees
    
    SG_main.SG_sim.set_angles_deg(SG_main.get_device_info(hand_id), angles)
    SG_sim.set_angles_deg(device_info, angles)
    ```
    """
    # For degrees, check reasonable range (-180 to 180)
    try:
        _validate_angles_array(exo_angles_deg_hand, device_info, "set_angles_deg")
        angles_array = np.asarray(exo_angles_deg_hand)
        
        if np.any(np.abs(angles_array) > 360):
            sg_logger.log(f"set_angles_deg: angles seem unusually large (>360 degrees). Check your input values", level=sg_logger.WARNING)
    except Exception as e:
        sg_logger.log(f"set_angles_deg: invalid angles array - {str(e)}", level=sg_logger.ERROR)
        return
    
    get_sim(device_info.device_id).set_exo_deg_hand(exo_angles_deg_hand)



def _create_glove_sim(device_info : SG_T.Device_Info, mode : Simulation_Mode) -> Glove_Simulator:
    """
    Create or restart a glove simulator with the specified device ID. Not integrated with API!!!
    
    **Args:**
        device_id (int): Unique device identifier for the simulator
        mode (Simulation_Mode): Animation mode to use
        
    **Returns:**
        Glove_Simulator: The created or restarted simulator instance
        
    If a simulator with this device_id already exists, it will be restarted 
    with the new mode instead of creating a duplicate.
    
    **Examples:**
    ```python
    # Create animated simulator
    sim = SG_sim.create_glove_sim(123, SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
    
    # Create static simulator
    sim = SG_sim.create_glove_sim(456, SG_sim.Simulation_Mode.STEADY_MODE)
    ```
    """
    sg_logger.log(f"create_glove_sim: Creating new glove simulator with device_id {device_info.device_id } in mode {mode.value}", level=sg_logger.INFO)
    _validate_simulation_mode(mode)

    
    if device_info.device_id not in _dict_device_id_Live_Test:
        glove_sim = Glove_Simulator(device_info, mode)
        _dict_device_id_Live_Test[device_info.device_id ] = glove_sim
        sg_logger.log(f"Created new glove simulator with device_id {device_info.device_id } in mode {mode.value}", level=sg_logger.INFO)
    else:
        glove_sim = _dict_device_id_Live_Test[device_info.device_id ]
        glove_sim.mode = mode
        glove_sim.restart()
        sg_logger.log(f"Restarted existing glove simulator {device_info.device_id } with new mode {mode.value}", level=sg_logger.INFO)
    return glove_sim

def create_glove_sim_device(device_info :SG_T.Device_Info, mode : Simulation_Mode) -> Glove_Simulator:
    """
    Create a glove simulator that integrates with the main API system.
    
    **Args:**
        device_info (SG_T.Device_Info): Device information (device_id, handedness, etc.)
        mode (Simulation_Mode): Animation mode to use
        
    **Returns:**
        Optional[Glove_Simulator]: The created simulator instance, or None if validation fails
        
    This function creates a simulator and properly registers it with the callback 
    system so it appears as a connected device to the main API.
    
    **Examples:**
    ```python
    # Create left hand simulator that integrates with SG_main functions
    device_info = SG_T.Device_Info(device_id=123, handedness=SG_T.Hand.LEFT)
    sim = SG_sim.create_glove_sim_device(device_info, SG_sim.Simulation_Mode.SINE_MODE)
    
    # Now you can use normal API functions
    angles = SG_main.get_exo_angles_rad(123)
    ```
    """
    if not isinstance(device_info, SG_T.Device_Info):
        sg_logger.log(f"create_glove_sim_device: device_info must be a SG_T.Device_Info, got {type(device_info)}. Valid types: [SG_T.Device_Info]", level=sg_logger.ERROR)
        return None
    _validate_simulation_mode(mode)

        
    SG_cb.device_com_connected_callback(device_info)

    glove_sim = _create_glove_sim(device_info, mode)

    return glove_sim
        

def stop_all_glove_sims():
    """
    Stop all active glove simulators.
    
    Calls stop() on every simulator, preventing further updates.
    Useful for clean shutdown of all simulations.
    
    **Examples:**
    ```python
    # Stop all simulators when exiting application
    SG_sim.stop_all_glove_sims()
    ```
    """
    for device_id in _dict_device_id_Live_Test:
        _dict_device_id_Live_Test[device_id].stop()

def get_sim(device_id : int):
    """
    Get the simulator instance for a specific device ID.
    
    **Args:**
        device_id (int): Device ID of the simulator to retrieve
        
    **Returns:**
        Glove_Simulator: The simulator instance
        
    **Examples:**
    ```python
    sim = SG_sim.get_sim(123)
    sim.set_simulation_mode(SG_sim.Simulation_Mode.STEADY_MODE)
    ```
    """
    # Lightweight validation for this potentially frequent function
    if not _dict_device_id_Live_Test.__contains__(device_id):
        raise ValueError(f"Simulator with device_id {device_id} not found")
    return _dict_device_id_Live_Test[device_id]

def update_all_glove_sims():
    """
    Update all active glove simulators for one frame.
    
    Call this continuously in your main loop to keep all simulations running.
    Should be called at ~1kHz for smooth animation.
    
    **Examples:**
    ```python
    # Main simulation loop
    while True:
        SG_sim.update_all_glove_sims()
        time.sleep(0.001)  # ~1kHz
    ```
    """
    # Very lightweight check - only validate if simulators exist (performance critical function)
    if not _dict_device_id_Live_Test:
        return  # No simulators to update
        
    # Create a copy of keys to avoid dict size change during iteration
    device_ids = list(_dict_device_id_Live_Test.keys())
    
    for device_id in device_ids:
        simulator = _dict_device_id_Live_Test.get(device_id)
        if simulator and simulator.running:
            simulator.update()

def set_mode(device_id : int, mode : Simulation_Mode ):
    """
    Change the animation mode for a specific simulator.
    
    **Args:**
        device_id (int): Device ID of the simulator
        mode (Simulation_Mode): New animation mode to use
        
    **Examples:**
    ```python
    # Switch to different animation modes
    SG_sim.set_mode(123, SG_sim.Simulation_Mode.SINE_MODE)
    SG_sim.set_mode(123, SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
    ```
    """
    if not _validate_simulation_mode(mode):
        return
  
    get_sim(device_id).set_simulation_mode(mode)


def is_exo_angles_type(obj) -> bool:
    """
    Check if an object is of type Sequence[Sequence[Union[int, float]]] AKA Union[List[List[float]], List[List[int]], List[np_array_type]]
    """
    # Case 1: List[List[int]] or List[List[float]]
    if isinstance(obj, list):
        if all(isinstance(row, list) for row in obj):
            return all(
                all(isinstance(v, (int, float)) for v in row)
                for row in obj
            )
        # Case 2: List of np.ndarray
        if all(isinstance(row, np.ndarray) for row in obj):
            return True
    # Case 3: Single np.ndarray
    if isinstance(obj, np.ndarray):
        return True

    return False


def set_simulation_fn(device_id : int, update_fn : Callable[[float], SG_T.Sequence[Sequence[Union[int, float]]]]):
    """
    Set the custom update function for angles for a specific simulator, when CUSTOM_FUNCTION mode is enabled.
    
    **Args:**
        device_id (int): Device ID of the simulator
        update_fn (Simulation_Mode): Function to call. Should have signature myFunction(t: float) and must return Sequence[Sequence[Union[int, float]]] containing 8 angles per finger.
        
    **Examples:**
    ```python
    _angles_deg_single_finger = np.array([0, -15, 45, -90, 120, -100, 90, 90]) 
    _angles_rad_single_finger = np.radians(_angles_deg_single_finger)
    _starting_angles_rad_hand = np.tile(_angles_rad_single_finger, (5, 1))

    def test_custom_fn(t : float) -> SG_T.Sequence[Sequence[Union[int, float]]]:
        realT = t * 50
        MIN_ANGLE_RAD = math.radians(75)  # Set your minimum angle (e.g., 10°)
        MAX_ANGLE_RAD = math.radians(90)  # Set your maximum angle (e.g., 60°)
        t_normalized = 0.5 * (1 - math.cos(2 * math.pi * realT))  
        angle = MIN_ANGLE_RAD + SG_simulator.smoothstep(t_normalized) * (MAX_ANGLE_RAD - MIN_ANGLE_RAD)
        return _starting_angles_rad_hand + np.cos(angle)
    
    SG_main.SG_sim.set_simulation_fn(hand_id, test_custom_fn)
    ```
    """
    get_sim(device_id).set_simulation_fn(update_fn)
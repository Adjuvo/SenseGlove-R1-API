# Simulated glove

## Creating a simulated glove

A left and right simulated glove can automatically be created if init is set to 
```python
    device_ids = SG_main.init(1, SG_T.Com_type.SIMULATED_GLOVE) 
```
If SG_main.init(2, ...) is called, a left simulated glove will be created additionally automatically.

If a simulated glove is desired next to a real one, (or simulating a third glove), you can also create one manually with:
```python
    SG_main.init_rembrandt_sim(SG_T.Hand.RIGHT, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
```

After creation, more specialized simulated glove functions can be accessed by getting the simulator.
```
    simulator = SG_main.SG_sim.get_sim(device_id)
```



## Simulate Tracking

### Simulation modes

Set via the `SIMULATION_MODE` argument to `init` / `init_rembrandt_sim`, or afterwards with `SG_main.SG_sim.set_mode()`.

**STEADY_MODE** — non-moving exoskeleton; the sim still fires the data callback each update.
```python
    device_ids = SG_main.init(1, SG_T.Com_type.SIMULATED_GLOVE, SG_main.SG_sim.Simulation_Mode.STEADY_MODE) 
```

**PLAYBACK_MODE** — passive mode for `SG_recorder.play_recording` or manual `set_angles_*`. Prefer this over STEADY_MODE when you drive angles yourself, so `on_new_data` is not fired twice per sample.
```python
    device_ids = SG_main.init(1, SG_T.Com_type.SIMULATED_GLOVE, SG_main.SG_sim.Simulation_Mode.PLAYBACK_MODE) 
```

**FINGERS_OPEN_CLOSE** — auto-plays the bundled `finger_close_open.csv` recording (full open/close). One playback stream per simulated glove (`device_id`).
```python
    device_ids = SG_main.init(1, SG_T.Com_type.SIMULATED_GLOVE, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE) 
```

**FINGERS_OPEN_CLOSE_SINE** — sine-based open/close around the starting pose (not full range of motion). For full ROM, use FINGERS_OPEN_CLOSE or play a recording in PLAYBACK_MODE.
```python
    device_ids = SG_main.init(1, SG_T.Com_type.SIMULATED_GLOVE, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE_SINE) 
```

**CUSTOM_FUNCTION** — angles from a user function (set with `set_simulation_fn`, then switch mode):
```python
    SG_main.SG_sim.set_mode(hand_id, SG_main.SG_sim.Simulation_Mode.CUSTOM_FUNCTION)
```

### Custom angles
To change the starting angles, you can use:
```python
         # sets splay to 1 degree, and 2nd and last flexion joint to 90 degrees for all fingers.

        angles_deg_single_finger = np.array([1, 0, 90, 0, 0, 0, 0, 90])
        angles = [angles_deg_single_finger.copy() for _ in range(5)] 
        SG_main.SG_sim.set_angles_deg(SG_main.get_device_info(hand_id), angles)
```
Or alternatively:
```python
   # sets the last flexion angle to 90, meaning the exoskeleton is completely straight with fingertips pointing forwards.

   angles_rad =                       [
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.5707963267948966],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.5707963267948966],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.5707963267948966],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.5707963267948966],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.5707963267948966]
        ]
        SG_main.SG_sim.set_angles_rad(SG_main.get_device_info(hand_id), angles_rad)
```

### Play glove recording
See `examples/play_recording.py` for an example. Use **PLAYBACK_MODE**. We have pre-existing recordings of opening and closing each finger and pinching. You can also record your own with `examples/record_glove.py`.

```python
    SG_main.init(0, SG_T.Com_type.SIMULATED_GLOVE)
    
    recording_filename = "close_each_finger.json"

    recording_device_info = SG_recorder.get_device_info(recording_filename)
    recording_device_info.device_id = (
        9999 if recording_device_info.hand == SG_T.Hand.RIGHT else 9998
    )
    simulator = SG_main.SG_sim.create_glove_sim_device(
        recording_device_info,
        SG_main.SG_sim.Simulation_Mode.PLAYBACK_MODE,
    )
    
    hand_id = simulator.device_id
    

    exo_poss, rots = SG_main.get_exo_joints_poss_rots(hand_id)
    gui.create_hand_exo(exo_poss)


    SG_recorder.play_recording(simulator.device_info, recording_filename, loop=True)
```
The recorder updates angles per `device_id` in the high-freq loop; fingertips etc. can be obtained in the loop or `on_new_data` as usual.


### Custom function to adjust the angles

To move the exoskeleton in a way you like, you can set a custom function for it to execute to change the angles.

```python
_angles_deg_single_finger = np.array([0, -15, 45, -90, 120, -100, 90, 90]) 
_angles_rad_single_finger = np.radians(_angles_deg_single_finger)
_starting_angles_rad_hand = np.tile(_angles_rad_single_finger, (5, 1))

## allows you to set custom angles for the simulation
def test_custom_fn(time : float) -> SG_T.Sequence[Sequence[Union[int, float]]]:
   
   # your function to adjust the exo angles
   realT = time * 50
   MIN_ANGLE_RAD = math.radians(75)  # Set your minimum angle (e.g., 10°)
   MAX_ANGLE_RAD = math.radians(90)  # Set your maximum angle (e.g., 60°)
   t_normalized = 0.5 * (1 - math.cos(2 * math.pi * realT))  
   angle = MIN_ANGLE_RAD + SG_simulator.smoothstep(t_normalized) * (MAX_ANGLE_RAD - MIN_ANGLE_RAD)
   
   
   return _starting_angles_rad_hand + np.cos(angle)

    

try: 
    device_ids = SG_main.init(1, SG_T.Com_type.SIMULATED_GLOVE, SG_main.SG_sim.Simulation_Mode.STEADY_MODE) 
    hand_id = device_ids[0]

    SG_main.SG_sim.set_simulation_fn(hand_id,  test_custom_fn)
    SG_main.SG_sim.set_mode(hand_id, SG_main.SG_sim.Simulation_Mode.CUSTOM_FUNCTION)


# below go your default on_new_data or loops similar to main_example.py. 
```
You can find a working example in `examples/simulation_custom_example.py`.


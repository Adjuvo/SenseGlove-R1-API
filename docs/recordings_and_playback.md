# Recordings / Machine learning functionality
We provide basic recording and replay functionality to develop without real glove present. For further instructions on machine learning recordings we also provide some recommendations down below.

Install the [Rx python API](https://github.com/Adjuvo/SenseGlove-R1-API), see [Python Getting started](python_getting_started.md).

## Examples

- example recording of most commonly used glove data (fingertips, exo_angles, percentage_bent), see `SG_API/recordings/fingers_close_open_all_data.csv`.
- To replay/use a recording live, as if a real glove was attached: `examples/recording_and_playback/play_recording.py` 
- To use a recording instead of a real glove in your custom integration: set `SG_main.init()` to `SIMULATED_GLOVE`, or replace the startup in your project similar to `play_recording.py` to play custom files.
- To record your own file ready for replay: `record_glove_no_gui.py`
- To record your own file while seeing the GUI (lower FPS): `record_glove.py`
- To post process a .csv to also save fingertips, and percentage bent data for analysis: `recording_to_all_data_csv`

While playing back a recording, it can literally be used as if a real glove was attached, to obtain for example fingertips, percentage bent, use it with robot hand mapper, ROS, etc. No real glove is necessary. 

For info + images of what data can be obtained from the glove, see [Tracking](tracking.md), [Forces](forces.md), [Robot_hand_mapper](robot_hand_mapper.md), and [API-reference](api-reference.md) for a full overview.

These recordings are recommended for shorter durations, developing without the glove, and data analysis. For recording machine learning data, continue reading.

## Planned features:

- In 2027, we will support OpenXR handtracking format data, for all hand joints.
- This will also be integrated in Isaac sim for teleoperation from VR, and hand data recording. 

Above will require a paid license. Contact sales for more information.

- Early 2027, Rx data will be time stamped data in Unix time (absolute microseconds), to sync your data with other sensors (free)



## For imitation learning

- We recommend recording/learning on the `commanded robothand positions/torques` (and *not* the glove data). Record the data while the robothand is being teleoperated with R1, with force feedback.
- By recording with robot hand commands, it's directly in the format the machine learning model needs. Additionally it can use our pinch perfect robot hand mapper for extra tracking accuracy.
- Even when only learning based on robot hand positions, the imitation learning will benefit from force feedback. If the users hand is stopped due to force feedback, the users hand cannot close further, and therefore the robot hand will also not close further. Since the robot hand cannot close further, the positions, and resulting contact forces in imitation learning will also be lower.

More imitation learning tips are further below.

## For teaching world models with human handtracking data / combination with other sensors
- In 2027 we will support OpenXR handtracking data for full hand joints via license, and LeRobot logging in Isaac Sim. Contact sales for more information.
- You likely have a preferred data format (LeRobot, csv, etc), which you also want to include other data, such as camera's, etc. Therefore, we recommend getting desired data from any `SG_main` or ROS/Isaac functions you want, then logging them with the other data.
- Since force sensors are measuring via tension on the wire, and not on the fingertip itself, we cannot log force of the glove touching an object directly. Only via telerobotic control we can actuate and measure forces of the glove.

## For data analysis, and development without real glove
The API supports recording/playback of glove tracking recordings as if a real glove were connected. That means:

- It supports any regular API calls, which means: `SG_main.get_fingertips_pos_rot()`, ROS messages, etc, all work while playing the recording.
- There is no difference between having a real glove connected, or playing back this recorded data.
- This is currently used for tracking data, since the main functionality is playback. 
- To analyze fingertips data, etc, we made a script recordings_to_all_data_csv.py to post process it.

You can also make your own recordings, see `examples/recordings_and_playback/record_glove_no_gui.py`
If you require it processed for data analysis (to also have fingertips, etc), then run `recording_to_all_data_csv.py`.

## Imitation learning tips
If you encounter the hand not properly learning to close, check the following:

- Is the PID for your final trajectory control well tuned, so it follows the positions closely.
- If in simulation: Do you have the correct friction and squishiness settings to mimic reality? It requires huge forces to pick up an object if friction is not set correctly.
- Are there examples in your dataset where the robot hand is fully closed? Otherwise the ML may not know the hand can even close more.



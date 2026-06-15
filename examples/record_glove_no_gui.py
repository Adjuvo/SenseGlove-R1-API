
"""
Run this to record the glove tracking data without a GUI.
That can be played back with play_recording.py as a simulated glove.

Set the file name and duration below.
Run the script. It will record for the set amount of seconds, then exit.
The recording will be saved in the /recordings/ folder.
Use play_recording.py to play it back as a simulated glove.

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

import sys
import os

#------------ Necessary for SG_API include ------------------------
sys.path.append(os.path.abspath('.')) # so it recognizes the SG_API folder

from SG_API import SG_main, SG_types as SG_T
from SG_API import SG_recorder


def main():
    device_ids = SG_main.init(1, SG_T.Com_type.REAL_GLOVE_USB) # new: 1 indicates nr of gloves it waits on before continuing from this line.
    hand_id = device_ids[0]

    filename = "test_recording.csv"
    duration = 15.0
    print("Recording glove data to recordings/" + filename + " for " + str(duration) + " seconds...")
    SG_recorder.record_glove_data(hand_id, duration, filename)

    print("device_info: ", SG_main.get_device_info(hand_id))


if __name__ == "__main__":
    main()

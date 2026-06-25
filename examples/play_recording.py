"""
Plays recordings of a real glove as a simulated glove. Can be used to develop without a physical glove.
Record your own? See examples/record_glove.py.

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

# common imports
import sys
import numpy as np
import math
import os
import sys
import traceback
import time
import warnings

from typing import List, Tuple




#------------ Necessary for SG_API include ------------------------
sys.path.append(os.path.abspath('.')) # so it recognizes the SG_API folder

from SG_API import SG_main, SG_types as SG_T 
from SG_API import SG_recorder

# ------------ GUI init ------------------
import SG_API.SG_GUI as GUI

app = GUI.QApplication(sys.argv)
gui = GUI.UI_Exo_Display_With_PercentageBent()
gui.show()
app.processEvents()



#------------- Rembrandt ----------







try:
    """
        The recording file should be in "recordings/" or "internal/recordings/".
    """
    recording_filename = "0076_finger_bending.csv"

    recording_device_info = SG_recorder.get_device_info(recording_filename)
    if recording_device_info is None:
        raise ValueError(
            f"Recording '{recording_filename}' has no metadata. "
            "Use a JSON recording from record_glove.py, or a CSV (raw_/filtered_ columns)."
        )

    SG_main.init(0, SG_T.Com_type.SIMULATED_GLOVE)

    recording_device_info.device_id = (9999 if recording_device_info.hand == SG_T.Hand.RIGHT else 9998    )
    simulator = SG_main.SG_sim.create_glove_sim_device(recording_device_info, SG_main.SG_sim.Simulation_Mode.PLAYBACK_MODE)
    hand_id = simulator.device_id

    SG_recorder.play_recording(simulator.device_info, recording_filename, loop=True)


    exo_poss, rots = SG_main.get_exo_joints_poss_rots(hand_id)
    gui.create_hand_exo(exo_poss)

    def on_new_data(from_device_id):
        if from_device_id == hand_id:
            exo_poss, exo_rots = SG_main.get_exo_joints_poss_rots(hand_id)
            gui.update_hand_exo(exo_poss)

            fingertips_poss, fingertips_rots = SG_main.get_fingertips_pos_rot(hand_id)
            gui.set_fingertip_points(fingertips_poss, fingertips_rots)
            
            thimble_dims = SG_main.get_fingertip_thimble_dims(hand_id)
            gui.set_fingertip_thimbles(thimble_dims)

            flexion_perc_bents, abduction_perc_bents = SG_main.get_percentage_bents(hand_id)
            gui.update_percentage_bent(flexion_perc_bents, abduction_perc_bents)

    SG_main.subscr_r1_data_callback(on_new_data)
    SG_recorder.restart_playback()
    on_new_data(hand_id)

    app.exec()
    
    sys.exit()
    

   

except Exception as X:
    print("Exception")
    print(traceback.print_exc())
    quit()




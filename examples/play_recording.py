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



#------------- Rembrandt ----------







try:
    # Initialize the API
    SG_main.init(0, SG_T.Com_type.SIMULATED_GLOVE)
    
    """
        The recording file should be in the "recordings" folder.
    """
    recording_filename = "percentage_bent_test.json"

    recording_device_info = SG_recorder.get_device_info(recording_filename)
    simulator = SG_main.init_rembrandt_sim(recording_device_info.hand, SG_main.SG_sim.Simulation_Mode.STEADY_MODE)
    
    hand_id = simulator.device_id
    

    exo_poss, rots = SG_main.get_exo_joints_poss_rots(hand_id)
    gui.create_hand_exo(exo_poss)


    SG_recorder.play_recording(simulator.device_info, recording_filename, loop=True)



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

            flex_angles, abd_angles = SG_main.get_raw_percentage_bent_angles(hand_id)

            #print(flex_angles, flexion_perc_bents, abd_angles, abduction_perc_bents)

            forces = simulate_forces()
            #print("forces", forces)
            #SG_main.set_force_goals(hand_id, forces)

    SG_main.subscr_r1_data_callback(on_new_data)

    #---------------------- Generate test forces ----------------------
    t = 0

    def smoothstep(t):
        return t * t * (3 - 2 * t)  # Custom easing function

    def simulate_forces():
        global t
        dt = 1

        MIN_FORCE_GOAL = 0
        MAX_FORCE_GOAL = 800

        t += dt * 0.0008  # Keep time increasing normally

        t_normalized = 0.5 * (1 - math.cos(2 * math.pi * t))  

        # Scale the angle to fit between MIN and MAX
        force = MIN_FORCE_GOAL + smoothstep(t_normalized) * (MAX_FORCE_GOAL - MIN_FORCE_GOAL)

        forces = [force] * SG_main.nr_of_fingers_force(hand_id)
        return forces
        

    
    app.exec()
    
    sys.exit()
    

   

except Exception as X:
    print("Exception")
    print(traceback.print_exc())
    quit()



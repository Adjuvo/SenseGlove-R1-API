
"""
Run this to record the glove tracking data .
That can be played back with play_recording.py as a simulated glove.

Set the file name and duration below. 
Run the script. The gui will start up white screen for the set amount of seconds. DURING THIS TIME, IT IS RECORDING!!!
After the seconds completed, you will then see the replay of the recording. That recording will be saved in the /recordings/ folder.
Use play_recording.py to play it back as a simulated glove.

Questions? Written by:
- Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api/
Support: https://www.senseglove.com/support/
"""


from fileinput import filename
import sys
import numpy as np
import math
import os
import sys
import traceback
import time
import warnings

from typing import List, Tuple


#TODO FIRST THING! Make different exoskeleton type actually work!!!
#GUI API to module
#Types rename test
#Comments


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
    device_ids = SG_main.init(1, SG_T.Com_type.REAL_GLOVE_USB) # new: 1 indicates nr of gloves it waits on before continuing from this line. 
    hand_id = device_ids[0]
    

    exo_poss, rots = SG_main.get_exo_joints_poss_rots(hand_id)
    gui.create_hand_exo(exo_poss)

    filename = "myfilename.json"
    duration = 10.0
    print("Recording glove data to recordings/" + filename + " for " + str(duration) + " seconds... (Screen is white during recording)")
    SG_recorder.record_glove_data(hand_id, duration, filename)

    print("device_info: ", SG_main.get_device_info(hand_id))

    simulator = SG_main.init_rembrandt_sim(SG_main.get_handedness(hand_id), SG_main.SG_sim.Simulation_Mode.STEADY_MODE)



    SG_recorder.play_recording(simulator.device_info, filename, loop=True)




    def on_new_data(from_device_id):
        if from_device_id == hand_id:
            exo_poss, exo_rots = SG_main.get_exo_joints_poss_rots(simulator.device_id)
            gui.update_hand_exo(exo_poss)

            fingertips_poss, fingertips_rots = SG_main.get_fingertips_pos_rot(simulator.device_id)
            gui.set_fingertip_points(fingertips_poss, fingertips_rots)

            thimble_dims = SG_main.get_fingertip_thimble_dims(simulator.device_id)
            gui.set_fingertip_thimbles(thimble_dims)

            flexion_perc_bents, abduction_perc_bents = SG_main.get_percentage_bents(simulator.device_id)
            gui.update_percentage_bent(flexion_perc_bents, abduction_perc_bents)
            
            forces = simulate_forces()
            #SG_main.set_force_goals(hand_id, forces, current_percentage_bent_flexion= (np.array(flexion_perc_bents) * 6.5534).tolist())

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



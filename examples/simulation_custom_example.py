"""
Example on how to make the simulation exo angles move in a custom way when no physical glove is used.
Alternatively, use play_recording.py to play a recording of a glove, or use main_example for the built in OPEN_CLOSE or STEADY_MODE.
"""

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
sys.path.append(os.path.abspath('.')) # so it recognises the SG_API folder

from SG_API import SG_main, SG_types as SG_T 

# ------------ GUI init ------------------
import SG_API.SG_GUI as GUI

# Create combined GUI with 3D view and percentage bent display
app = GUI.QApplication(sys.argv)
gui = GUI.UI_Exo_Display_With_PercentageBent()
gui.show()

from SG_API import SG_simulator

from typing import Sequence, Union

#------------- Rembrandt ----------


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
    #  1 = nr of gloves it waits on before continuing from this line. 
    # CHANGE between SG_T.Com_type.SIMULATED_GLOVE and SG_T.Com_type.REAL_GLOVE_UART

    device_ids = SG_main.init(1, SG_T.Com_type.SIMULATED_GLOVE, SG_main.SG_sim.Simulation_Mode.STEADY_MODE) 
    hand_id = device_ids[0]

    SG_main.SG_sim.set_simulation_fn(hand_id,  test_custom_fn)
    SG_main.SG_sim.set_mode(hand_id, SG_main.SG_sim.Simulation_Mode.CUSTOM_FUNCTION)


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

            flex_angles, abd_angles = SG_main.get_raw_percentage_bent_angles(hand_id)

            #print("flexion_angles:", flex_angles, "abd_angles:", abd_angles)

            #forces = [int(f) for f in simulate_forces()]            #  print("forces", forces)
            forces = [0] * SG_main.nr_of_fingers_force(hand_id)


            SG_main.set_force_goals(hand_id, forces) 

            #The latest set vibration/force data is sent automatically at the end of this callback, no matter from where you set it.





    SG_main.subscr_r1_data_callback(on_new_data)


    # Fixing percentage bent. I'm currently trying to unrotate the finger so I can do the percentage bent calculation axis aligned, but getting errors.
    # Next step would be to stash the changes, then see if calling percentage bent previous version also gives errors, since I'm getting errors in part of the code that I did not touch.


    #---------------------- Generate test forces ----------------------
    t = 0

    def smoothstep(t):
        return t * t * (3 - 2 * t)  # Custom easing function

    def simulate_forces():
        global t
        dt = 1

        MIN_FORCE_GOAL = 0
        MAX_FORCE_GOAL = 4000

        t += dt * 0.0008  # Keep time increasing normally

        t_normalized = 0.5 * (1 - math.cos(2 * math.pi * t))  

        # Scale the angle to fit between MIN and MAX
        force = MIN_FORCE_GOAL + smoothstep(t_normalized) * (MAX_FORCE_GOAL - MIN_FORCE_GOAL)
        forces = [force] * SG_main.nr_of_fingers_force(hand_id)
        return forces
        
                    

    #---------------------------------------------------------



    #TODO: implement fingertip display and direction display
    #TODO: print or plot values
    #TODO: make it fancier
    #TODO: test if 1kHz update rate is in fact 1kHz update rate?




    
    app.exec() # This keeps the program running using Qt, which is needed for the GUI.
    #---- IMPORTANT:-----------------IMPORTANT-------------------IMPORTANT------------------IMPORTANT-------------------IMPORTANT---------------------
    #SG_main.keep_program_running() # Call if not using the GUI, to keep the program alive until closing on Ctrl+C
   
    
    sys.exit()
    

   

except Exception as X:
    print("Exception")
    print(traceback.print_exc())
    quit()




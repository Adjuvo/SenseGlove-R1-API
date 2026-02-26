"""
The main example how to use the SenseGlove R1 glove.
It initializes the glove, and then creates a GUI to display the exo and fingertip positions.
Turn on forces further below to create force feedback on the fingers, gradually increasing and decreasing.

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""



import sys
import numpy as np
import math
import os
import sys
import traceback


#------------ Necessary for SG_API include ------------------------
sys.path.append(os.path.abspath('.')) # so it recognizes the SG_API folder

from SG_API import SG_main, SG_types as SG_T 

# ------------ GUI init ------------------
import SG_API.SG_GUI as GUI

# Create combined GUI with 3D view and percentage bent display
app = GUI.QApplication(sys.argv)
gui = GUI.UI_Exo_Display_With_PercentageBent()
gui.show()



try: 
    """
        Develop without a physical glove? Switch SG_T.Com_type.REAL_GLOVE_USB to SG_T.Com_type.SIMULATED_GLOVE. Or use play_recording.py for actual glove recordings. 
        Simulation_Mode = ignored for the real glove, but can set movement for the simulated glove.
        wait_for_x_gloves = nr of gloves it waits on before continuing from this line. 
    """
    wait_for_x_gloves = 1
    device_ids = SG_main.init(wait_for_x_gloves, SG_T.Com_type.SIMULATED_GLOVE, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE) 
    hand_id = device_ids[0]


    # initialize the GUI with the exo positions
    exo_poss, rots = SG_main.get_exo_joints_poss_rots(hand_id)
    gui.create_hand_exo(exo_poss)

    # callback called when new data is available
    def on_new_data(from_device_id):
        if from_device_id == hand_id:
            
            """
            Tracking data:
            """
            exo_poss, exo_rots = SG_main.get_exo_joints_poss_rots(hand_id)
            gui.update_hand_exo(exo_poss)


            fingertips_poss, fingertips_rots = SG_main.get_fingertips_pos_rot(hand_id)
            gui.set_fingertip_points(fingertips_poss, fingertips_rots)
            
            thimble_dims = SG_main.get_fingertip_thimble_dims(hand_id)
            gui.set_fingertip_thimbles(thimble_dims)

            flexion_perc_bents, abduction_perc_bents = SG_main.get_percentage_bents(hand_id)
            gui.update_percentage_bent(flexion_perc_bents, abduction_perc_bents)
            
            fingertips_distances = SG_main.get_fingertip_distances(hand_id)

            """
            Forces: switch on or off by commenting/uncommenting
            """
            forces = [int(f) for f in simulate_forces()]            # gradual on/off forces
            #forces = [0, 0, 0, 0]                                    # no force. 

            SG_main.set_force_goals(hand_id, forces)

            """
            The latest vibration/force data is sent automatically at the end of this callback, no matter from where it was set.
            """


    # subscribe to activate on_new_data callback
    SG_main.subscr_r1_data_callback(on_new_data)


    #---------------------- Generate test forces ----------------------
    t = 0

    def smoothstep(t):
        return t * t * (3 - 2 * t)  # Custom easing function

    def simulate_forces():
        global t
        dt = 1

        MIN_FORCE_GOAL = 0
        MAX_FORCE_GOAL = 4000 # you can do much higher.

        t += dt * 0.0008  # Keep time increasing normally

        t_normalized = 0.5 * (1 - math.cos(2 * math.pi * t))  

        # Scale the angle to fit between MIN and MAX
        force = MIN_FORCE_GOAL + smoothstep(t_normalized) * (MAX_FORCE_GOAL - MIN_FORCE_GOAL)
        forces = [force] * SG_main.nr_of_fingers_force(hand_id)
        return forces
        
                    

    
    app.exec() 
    """
    app.exec() is a while loop that keeps the program running using Qt, which is needed for the GUI.

    #---- IMPORTANT:-----------------IMPORTANT-------------------IMPORTANT------------------IMPORTANT-------------------IMPORTANT---------------------
    SG_main.keep_program_running() # Call if not using the GUI, to keep the program alive until closing on Ctrl+C. If desiring to use your own while loop, read Getting started docs.
     """  
    
    sys.exit()
    

   

except Exception as X:
    print("Exception")
    print(traceback.print_exc())
    quit()




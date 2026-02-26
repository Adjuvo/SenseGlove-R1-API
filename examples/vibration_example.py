"""
The main example how to use the SenseGlove R1 glove.

Aside from the force example, this also shows how to set vibrations.

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
import time
import warnings

from typing import List, Tuple


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
        To develop without physical glove, switch SG_T.Com_type.REAL_GLOVE_USB to SG_T.Com_type.SIMULATED_GLOVE. Or use play_recording.py for actual glove recordings. 
        Only for simulation, the Simulation_Mode matters, it is ignored for the real glove.
        wait_for_x_gloves = nr of gloves it waits on before continuing from this line. 
    """
    wait_for_x_gloves = 1
    device_ids = SG_main.init(wait_for_x_gloves, SG_T.Com_type.REAL_GLOVE_USB, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE) 
    hand_id = device_ids[0]
    

    """
    If using a simulated glove, you can set some different angles for it's start. It's ignored for the real glove.
    """
    if SG_main.get_COM_type(hand_id) == SG_T.Com_type.SIMULATED_GLOVE:
        SG_main.SG_sim.set_mode(hand_id, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
        angles_deg_single_finger = np.array([0, -15, 45, -90, 120, -100, 90, 90]) # this is a more natural starting pose for a single finger
        angles = [angles_deg_single_finger.copy() for _ in range(5)]  # Create list of arrays, one per finger
        SG_main.SG_sim.set_angles_deg(SG_main.get_device_info(hand_id), angles)
        


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

            """
            Forces: switch on or off by commenting/uncommenting
            """
            #forces = [int(f) for f in simulate_forces()]            # gradual on/off forces
            forces = [0, 0, 0, 0]                                    # no force. 

            SG_main.set_force_goals(hand_id, forces)

            """
            Vibration data:
            """

            # Example of vibration data that makes the palm buzz. For each finger and palm, you can set up to 4 waveforms.
            # The frequencies are determined by the waveform index, reading from a database of pre-made waveforms/frequencies in the glove.
            outVibroData = [ 
                [0, 0, 0],                              # Finger 1 (thumb) - inactive
                [0, 0, 0],                              # Finger 2 (index) - inactive
                [0, 0, 0],                              # Finger 3 (middle) - inactive  
                [0, 0, 0],                              # Finger 4 (ring) - inactive
                [0, 0, 0],                              # Finger 5 (pinky) - inactive
                # cmd, ampl, tot_waveforms, waveform1_index, waveform1_phase, waveform1_amplitude, waveform2_index, waveform2_phase, waveform2_amplitude, etc
                [0b10,     127,    2,                 1,             0,                   127,               2,               0,                  127],                              # Palm actuator 1   
                [0b10,     127,    2,                 1,             0,                   127,               2,               0,                  127],                              # Palm actuator 2
                [0b10,     127,    2,                 1,             0,                   127,               2,               0,                  127]                               # Palm actuator 3 
            ]


            SG_main.set_raw_vibro_data(hand_id, outVibroData) 

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




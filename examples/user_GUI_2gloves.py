"""
This is an example showing two Rembrandt gloves using a simple side-by-side layout.
It creates two GUI instances in a single window container.

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

import sys
import numpy as np
import math
import os
import traceback
import time
import warnings

from typing import List, Tuple, Optional

#------------ Necessary for SG_API include ------------------------
sys.path.append(os.path.abspath('.')) # so it recognizes the SG_API folder

from SG_API import SG_main, SG_types as SG_T 

# ------------ GUI init ------------------
import SG_API.SG_GUI as GUI
from PySide6.QtWidgets import QApplication

# Create the application and dual GUI
app = QApplication(sys.argv)
dual_gui = GUI.DualHandGUI()
dual_gui.show()

#------------- Rembrandt ----------

try: 

    # TO PUT 2 HANDS to REAL Device:
    #device_ids = SG_main.init(2, SG_T.Com_type.REAL_GLOVE_USB) 

    # TO PUT 1 (RIGHT) HAND to SIMULATED & 1 (LEFT) to REAL:
    device_ids = SG_main.init(1, SG_T.Com_type.REAL_GLOVE_USB) 
    SG_main.init_rembrandt_sim(SG_T.Hand.LEFT, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
    
    # Get hand IDs with inline None checks using walrus operator
    if (left_hand_id := SG_main.get_left_hand_deviceid()) is None:
        raise RuntimeError("Left hand device not found")
    if (right_hand_id := SG_main.get_right_hand_deviceid()) is None:
        raise RuntimeError("Right hand device not found")

    # Set up simulation mode for both hands if they're simulated
    if SG_main.get_COM_type(left_hand_id) == SG_T.Com_type.SIMULATED_GLOVE:
        SG_main.SG_sim.set_mode(left_hand_id, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
        print("Left hand simulated")
    
    if SG_main.get_COM_type(right_hand_id) == SG_T.Com_type.SIMULATED_GLOVE:
        SG_main.SG_sim.set_mode(right_hand_id, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
        print("Right hand simulated")

    # Initialize both GUI windows with hand data
    left_exo_poss, left_rots = SG_main.get_exo_joints_poss_rots(left_hand_id)
    dual_gui.left_gui.create_hand_exo(left_exo_poss)
    
    right_exo_poss, right_rots = SG_main.get_exo_joints_poss_rots(right_hand_id)
    dual_gui.right_gui.create_hand_exo(right_exo_poss)

    def on_new_data(from_device_id: int):
        if from_device_id == left_hand_id:
            # Update left GUI with left hand data
            exo_poss, exo_rots = SG_main.get_exo_joints_poss_rots(left_hand_id)
            dual_gui.left_gui.update_hand_exo(exo_poss)

            fingertips_poss, fingertips_rots = SG_main.get_fingertips_pos_rot(left_hand_id)
            dual_gui.left_gui.set_fingertip_points(fingertips_poss, fingertips_rots)
            
            thimble_dims = SG_main.get_fingertip_thimble_dims(left_hand_id)
            dual_gui.left_gui.set_fingertip_thimbles(thimble_dims)

            # Update percentage bent display
            flexion, abduction = SG_main.get_percentage_bents(left_hand_id)
            dual_gui.left_perc_bent.update(flexion, abduction)

            forces = simulate_forces(left_hand_id)
            #SG_main.set_force_goals(left_hand_id, forces)
            
        elif from_device_id == right_hand_id:
            # Update right GUI with right hand data
            exo_poss, exo_rots = SG_main.get_exo_joints_poss_rots(right_hand_id)
            dual_gui.right_gui.update_hand_exo(exo_poss)

            fingertips_poss, fingertips_rots = SG_main.get_fingertips_pos_rot(right_hand_id)
            dual_gui.right_gui.set_fingertip_points(fingertips_poss, fingertips_rots)
            
            thimble_dims = SG_main.get_fingertip_thimble_dims(right_hand_id)
            dual_gui.right_gui.set_fingertip_thimbles(thimble_dims)

            # Update percentage bent display
            flexion, abduction = SG_main.get_percentage_bents(right_hand_id)
            dual_gui.right_perc_bent.update(flexion, abduction)

            forces = simulate_forces(right_hand_id)
            #SG_main.set_force_goals(right_hand_id, forces)

    SG_main.subscr_r1_data_callback(on_new_data)

    #---------------------- Generate test forces ----------------------
    t = 0

    def smoothstep(t):
        return t * t * (3 - 2 * t)  # Custom easing function

    def simulate_forces(hand_id: int):
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

    #---------------------------------------------------------

    app.exec()
    sys.exit()

except Exception as X:
    print("Exception")
    print(traceback.print_exc())
    quit()
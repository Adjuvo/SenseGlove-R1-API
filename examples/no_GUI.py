"""
Example of how to use the SenseGlove R1 glove without a GUI.
It is faster, may run at higher framerate.

Questions? Written by:
- Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api/
Support: https://www.senseglove.com/support/
"""

import sys
import os
import time


# Add SG_API to path  
sys.path.append(os.path.abspath('.'))

from SG_API import SG_main, SG_types as SG_T

def main():

    device_ids = SG_main.init(1, SG_T.Com_type.REAL_GLOVE_USB)
    hand_id = device_ids[0]
    
    if SG_main.get_COM_type(hand_id) == SG_T.Com_type.SIMULATED_GLOVE:
        SG_main.SG_sim.set_mode(hand_id, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
    
    def on_new_data(from_device_id):
        if from_device_id == hand_id:
            exo_poss, exo_rots = SG_main.get_exo_joints_poss_rots(hand_id)
            fingertip_poss, fingertip_rots = SG_main.get_fingertips_pos_rot(hand_id)
            flexion_perc_bents, abduction_perc_bents = SG_main.get_percentage_bents(hand_id)
            #print(fingertip_poss)
            pass
    
    SG_main.subscr_r1_data_callback(on_new_data)
    
    SG_main.keep_program_running()



if __name__ == "__main__":
    main()
"""
Robot Hand Pinch Calibration 

See the docs on robot hand mapper for more info.

Questions? Written by:
- Akshay Radhamohan M
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

import sys, traceback
from pathlib import Path
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout

from SG_API import SG_main, SG_types as SG_T
from SG_API import SG_GUI as GUI
from SG_API.SG_logger import sg_logger

from SG_API.SG_robot_hand_mapper import RobotHandMapper as RHM
from SG_API.SG_robot_pinch_gui import PinchMapperGUI
from SG_API import SG_recorder

# from ...configs.robot_hand_mapper.seed_hand import config as seed_hand_config
# from SG_API.configs.robot_hand_mapper.rh8d_seed_hand import config


# Main
def main():
    app = QApplication(sys.argv)

    hand_id =SG_main.init(1, SG_T.Com_type.SIMULATED_GLOVE)[0]
    
    if SG_main.get_COM_type(hand_id) == SG_T.Com_type.SIMULATED_GLOVE:
        ## play recording if in simulation mode
        recording_filename = "pinch_normally.json"

        recording_device_info = SG_recorder.get_device_info(recording_filename)
        simulator = SG_main.init_rembrandt_sim(recording_device_info.hand, SG_main.SG_sim.Simulation_Mode.STEADY_MODE)
        
        hand_id = simulator.device_id

        SG_recorder.play_recording(simulator.device_info, recording_filename, loop=True)
    
    # Create combined window
    main_window = QWidget()
    main_window.setWindowTitle("Robot Hand Pinch Mapper")
    main_layout = QHBoxLayout()
    main_layout.setSpacing(0)
    main_layout.setContentsMargins(0, 0, 0, 0)

    # 3D visualization on the left (Qt3DWindow needs to be wrapped in a container)
    gui_3d = GUI.UI_Exo_Display()
    exo_poss, rots = SG_main.get_exo_joints_poss_rots(hand_id)
    gui_3d.create_hand_exo(exo_poss)
    gui_3d_container = QWidget.createWindowContainer(gui_3d)
    main_layout.addWidget(gui_3d_container, 6)

    # Robot Hand Mapper
    mapper = SG_main.create_robot_hand_mapper(hand_id)
    
    # Pinch GUI on the right
    pinch_gui = SG_main.create_rhm_pinch_gui(hand_id)
    pinch_gui.setMaximumWidth(600)  # Limit max width so 3D view can expand
    main_layout.addWidget(pinch_gui, 1)

    main_window.setLayout(main_layout)
    main_window.setGeometry(100, 100, 1600, 700)  # Wider window to see stretch effect
    main_window.show()    

    
    
    # Callback
    def on_new_data(from_device_id):
        if from_device_id != hand_id:
            return

        # Update visualization
        exo_poss, rots = SG_main.get_exo_joints_poss_rots(hand_id)
        gui_3d.update_hand_exo(exo_poss)

        fingertips_poss, fingertips_rots = SG_main.get_fingertips_pos_rot(hand_id)
        gui_3d.set_fingertip_points(fingertips_poss, fingertips_rots)

        thimble_dims = SG_main.get_fingertip_thimble_dims(hand_id)
        gui_3d.set_fingertip_thimbles(thimble_dims)

        # Glove flexion and robot-mapped flexion
        normal_flex, normal_abd = SG_main.get_percentage_bents(hand_id)
        robot_flex, robot_abd = SG_main.get_rhm_percentage_bents(hand_id)
        debug = SG_main.get_pinch_debug_info(hand_id)

        # Update Mapper GUI
        SG_main.update_robot_hand_mapper_gui(hand_id)


    SG_main.subscr_r1_data_callback(on_new_data)

    app.exec()
    sys.exit()

if __name__ == "__main__":
    main()

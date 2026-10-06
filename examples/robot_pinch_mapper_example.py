"""
Robot Hand Pinch Calibration 

See the docs on robot hand mapper for more info.

Questions? Written by:
- Akshay Radhamohan M
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

import sys
import os

#------------ Necessary for SG_API include ------------------------
sys.path.append(os.path.abspath('.'))  # so it recognizes the SG_API folder

from SG_API import SG_main, SG_types as SG_T
from SG_API import SG_GUI as GUI

from SG_API.SG_robot_pinch_mapper import Robot_Pinch_Mapper




def main():
    app = GUI.QApplication(sys.argv)

    gui = GUI.UI_Robot_Pinch_Mapper_Display()
    gui.show()

    hand_id = SG_main.init(1, SG_T.Com_type.REAL_GLOVE_USB)[0]

    gui.attach_mapper(Robot_Pinch_Mapper(hand_id))

    exo_poss, rots = SG_main.get_exo_joints_poss_rots(hand_id)
    gui.create_hand_exo(exo_poss)

    def on_new_data(from_device_id):
        if from_device_id != hand_id:
            return

        exo_poss, rots = SG_main.get_exo_joints_poss_rots(hand_id)
        gui.update_hand_exo(exo_poss)

        fingertips_poss, fingertips_rots = SG_main.get_fingertips_pos_rot(hand_id)
        gui.set_fingertip_points(fingertips_poss, fingertips_rots)

        thimble_dims = SG_main.get_fingertip_thimble_dims(hand_id)
        gui.set_fingertip_thimbles(thimble_dims)

        glove_flex, glove_abd = SG_main.get_percentage_bents(hand_id)
        distances = SG_main.get_fingertip_distances(hand_id)
        joint_distances = SG_main.get_thumb_to_finger_joint_distances(hand_id)
        robot_flex, robot_abd = gui.mapper.compute_rpm_bents(glove_flex, glove_abd, distances, joint_distances)



        print(
            f"Values sent to robot, flexions: {_fmt_vals(robot_flex):<25}  "
           # f"robot abductions: {_fmt_vals(robot_abd):<25}  "
            f" Glove flexions: {_fmt_vals(glove_flex):<25}  "
            f" Glove abductions: {_fmt_vals(glove_abd):<25}"
        )

        gui.update_pinch_mapper(glove_flex, glove_abd, robot_flex, robot_abd)




        # if you want to change the percentage bent coming out of the glove depending on raw original angles, you can use this:
        # raw_flex, raw_abd = SG_main.get_raw_percentage_bent_angles(hand_id)
        # print(f"raw flexions: {_fmt_vals(raw_flex):<25}  "
        #     f"raw abductions: {_fmt_vals(raw_abd):<25}")
        # use this to then set the limits mapping from 0 to 10000
        # SG_main.set_percentage_bent_vars(yourvalues)

    SG_main.subscr_r1_data_callback(on_new_data)

    app.exec()
    sys.exit()


def _fmt_vals(vals):
    parts = []
    for v in vals:
        fv = float(v)
        if fv == int(fv):
            parts.append(f"{int(fv)}")
        else:
            parts.append(f"{fv:.3f}")
    return "[" + ", ".join(parts) + "]"


if __name__ == "__main__":
    main()

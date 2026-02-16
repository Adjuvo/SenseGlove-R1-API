# Control

## Force control
Internally within the glove, a force controller runs much faster than 1khz to set the tension on the wire to the specified force by rotating the motor. 

[set_force_goals()](api-reference.md#SG_API.SG_main.set_force_goals) accepts a list with one force goal per finger (in milliNewtons) and is sent to the glove, which will from then on be the new force goals. When the force is set to 0, it keeps a minimal tension of ~80 grams (=800 mN) on the wire to prevent it from getting slack, allowing the finger to move as free as possible.

The max force the glove can actively pull is around 3500 mN. If the user presses harder than that, the motor acts as a brake up to ~20000 mN.

Notes: 

- The final force on the wire might differ from the force goal requested to allow stable control. Scale up the forces if necessary.
- The milliNewtons are the tension in the wire pulling the finger back.
- The pinky does not have a force feedback motor, so is not controllable.
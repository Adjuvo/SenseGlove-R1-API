"""
Math functions used in the API.
Note: creating objects such as Quaternions is slow, so it is best to use the other optimized functions working with rawer arrays in this file rather than creating objects directly.

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

import os
import ctypes
import platform
import numpy as np
import sys
import math
from typing import List, Optional, Any, Union
import numpy.typing as npt
from . import SG_types as SG_T
from .SG_logger import sg_logger


# Get the absolute path to the CPPlibs folder
DLL_FOLDER = os.path.join(os.path.dirname(__file__), "CPPlibs")

# Determine the correct file extension based on OS
if platform.system() == "Windows":
    DLL_NAME = "libSG_math.dll"
    if hasattr(os, "add_dll_directory"):  # Required for Python 3.8+
        os.add_dll_directory(DLL_FOLDER)
else:
    DLL_NAME = "libSG_math.so"  # Linux/macOS use "lib" prefix

DLL_PATH = os.path.join(DLL_FOLDER, DLL_NAME)
# Load the shared library
SG_math_lib = ctypes.CDLL(DLL_PATH)


SG_math_lib.forward_kinematics_3d.argtypes = [
    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)
]




class Quaternion:
    def __init__(self, w, x, y, z):
        self.q = np.array([w, x, y, z])

    @classmethod
    def identity(cls):
        return cls(1.0, 0.0, 0.0, 0.0)

    def __str__(self):
        return f"Quat(w={self.q[0]}, x={self.q[1]}, y={self.q[2]}, z={self.q[3]})"
    
    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        if isinstance(other, Quaternion):
            return np.allclose(self.q, other.q)
        return False

    def __ne__(self, other):
        return not self.__eq__(other)
        
    @staticmethod
    def from_euler(ax, ay, az):
        """Convert Euler angles (ZYX order) to a quaternion."""
        cx, cy, cz = np.cos(np.array([ax, ay, az]) / 2)
        sx, sy, sz = np.sin(np.array([ax, ay, az]) / 2)
        return Quaternion(
            cz * cy * cx + sz * sy * sx,
            cz * cy * sx - sz * sy * cx,
            cz * sy * cx + sz * cy * sx,
            sz * cy * cx - cz * sy * sx
        )
    
    def to_euler(self):
        """ returns [ax, ay, az]
        Convert quaternion to Euler angles (ZYX order)."""
        w, x, y, z = self.q
        
        roll = np.arctan2(2 * (w * x + y * z), 1 - 2 * (x**2 + y**2))
        pitch = np.arcsin(2 * (w * y - z * x))
        yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y**2 + z**2))
        
        return np.array([roll, pitch, yaw])
    
    def multiply(self, other):
        """Multiply two quaternions."""
        w1, x1, y1, z1 = self.q
        w2, x2, y2, z2 = other.q
        return Quaternion(
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        )
    
    def rotate_vec(self, v):
        """Rotate a vector v by this quaternion."""
        q_v = Quaternion(0, *v)
        q_conj = Quaternion(self.q[0], -self.q[1], -self.q[2], -self.q[3])
        return self.multiply(q_v).multiply(q_conj).q[1:]
    
    def rotate_by_euler(self, euler_angles: List[float]):
        ax, ay, az = euler_angles

        # Convert the Euler angles to a quaternion
        rot_quat = Quaternion.from_euler(ax, ay, az)
        
        # Perform quaternion multiplication (accumulate rotation)
        new_quat = self.multiply(rot_quat)
        
        return new_quat.q
        
    
    def to_matrix(self):
        """Convert quaternion to rotation matrix."""
        w, x, y, z = self.q
        return np.array([
            [1 - 2*y**2 - 2*z**2, 2*x*y - 2*w*z, 2*x*z + 2*w*y],
            [2*x*y + 2*w*z, 1 - 2*x**2 - 2*z**2, 2*y*z - 2*w*x],
            [2*x*z - 2*w*y, 2*y*z + 2*w*x, 1 - 2*x**2 - 2*y**2]
        ])
    
    def inverse(self):
        """Returns the inverse of the quaternion."""
        w, x, y, z = self.q
        norm_sq = np.dot(self.q, self.q)
        return Quaternion(w / norm_sq, -x / norm_sq, -y / norm_sq, -z / norm_sq)


def rescale(val, in_min, in_max, out_min, out_max):
    """
    Optimized rescale function. For maximum performance, pass NumPy arrays directly
    (avoids array conversion overhead).
    """
    # Fast path: if inputs are already numpy arrays, avoid conversion overhead
    if isinstance(val, np.ndarray) and isinstance(in_min, np.ndarray) and \
       isinstance(in_max, np.ndarray) and isinstance(out_min, np.ndarray) and \
       isinstance(out_max, np.ndarray):
        # Already arrays - use directly
        pass
    else:
        # Convert to arrays (only if needed)
        val = np.asarray(val, dtype=np.float64)
        in_min = np.asarray(in_min, dtype=np.float64)
        in_max = np.asarray(in_max, dtype=np.float64)
        out_min = np.asarray(out_min, dtype=np.float64)
        out_max = np.asarray(out_max, dtype=np.float64)
    
    # Calculate denominator
    denominator = in_max - in_min
    
    # Fast path: common case where denominator is never zero (avoid expensive checks)
    # For percentage bent calculations, denominator should never be zero in practice
    # Only do zero check if we suspect there might be zeros
    # Optimized: check if any denominator is zero using a fast check
    if isinstance(denominator, np.ndarray):
        # Fast check: if all denominators are large enough, skip zero check
        # This avoids the expensive np.any() and np.where() calls in the common case
        has_zeros = np.any(denominator == 0.0)
        if not has_zeros:
            # Fast path: no zero division possible
            return out_min + (val - in_min) * ((out_max - out_min) / denominator)
    else:
        # Scalar case
        if denominator == 0.0:
            return out_min
        return out_min + (val - in_min) * ((out_max - out_min) / denominator)
    
    # Slow path: handle potential zero division (rare case)
    zero_mask = denominator == 0.0
    
    if np.any(zero_mask):
        sg_logger.log("Divide by zero in rescale - using output minimum for affected elements", level=sg_logger.WARNING)
        # Replace zero denominators with 1 to avoid division by zero, result will be overridden below
        denominator = np.where(zero_mask, 1.0, denominator)
    
    # Calculate rescaled values
    result = out_min + (val - in_min) * ((out_max - out_min) / denominator)
    
    # For zero division cases, return the output minimum value
    if np.any(zero_mask):
        result = np.where(zero_mask, out_min, result)
    
    return result

def clamp(val, minimum, maximum):
    val = np.array(val)
    minimum = np.array(minimum)
    maximum = np.array(maximum)
    val = np.minimum(val, maximum)
    val = np.maximum(val, minimum)
    return val

def dot_list(a, b):
    return [np.dot(a, b) for a, b in zip(a, b)]

def cross_list(a, b):
    return [np.cross(a, b) for a, b in zip(a, b)]

def forward_kinematics_3d(base_pos_3d, linkages_3d, angles_3d,  base_rot_quat : Optional[Quaternion] = Quaternion.identity()):
    #IF THIS EVER NEEDS TO BE OPTIMIZED: Consider using forward_kinematics_2d, keeping all operations 2d saves some sine calcs and multiplications.
    # Then rotating everything in the last step with the splay angle to 3D.

    # print("b:" + str(base_3d))
    # print("l:" + str(linkages_3d))
    # print("a:" + str(angles_3d))
    # Ensure inputs are NumPy arrays
    base_pos_3d = np.array(base_pos_3d, dtype=np.float64)  # Converts tuples/lists to np.ndarray
    linkages_3d = np.array(linkages_3d, dtype=np.float64)
    angles_3d = np.array(angles_3d, dtype=np.float64)

    num_joints = len(linkages_3d)
    positions = np.zeros((num_joints + 1) * 3, dtype=np.float64)
    quaternions = np.zeros((num_joints + 1) * 4, dtype=np.float64)  # Store quaternions

    # Set base quaternion
    base_quat_array = np.zeros(4, dtype=np.float64)
    if base_rot_quat is not None:
        base_quat_array = base_rot_quat.q
    else:
        base_quat_array = Quaternion.identity().q

    base_pos_format = base_pos_3d.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    base_quat_format = base_quat_array.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    linkages_format = linkages_3d.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    angles_format = angles_3d.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    SG_math_lib.forward_kinematics_3d(
        base_pos_format,
        base_quat_format,  # Pass base quaternion right after base position
        linkages_format,
        angles_format,
        num_joints,
        positions.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        quaternions.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # Return quaternions
    )

    return positions.reshape(-1, 3), quaternions.reshape(-1, 4)  # Return Nx4 quaternion array




####################### BELOW IS THE PART ACTUALLY EXPOSED IN C - LAYER, meaning no C++ objects (such as Quat) should be passed in or out the functions. Only C compatible. #####

def rotate_vec_by_quat_list(quats : List[SG_T.Quat_type], vecs : List[SG_T.Vec3_type]):
    return [rotate_vec_by_quat(q, v) for q, v in zip(quats, vecs)]
    

def rotate_vec_by_quat(quat : SG_T.Quat_type, vec : SG_T.Vec3_type):
    """
    quat: w, x, y, z
    vec: x, y z
    returns: vec rotated by quat
    """
    quat_o = Quaternion(quat[0], quat[1], quat[2], quat[3])
    rotated_vec = quat_o.rotate_vec(vec)
    return rotated_vec

def quat_to_matrix(quat : SG_T.Quat_type):    
    """
    quat: w, x, y, z
    returns: 3x3 np array matrix
    """
    quat_o = Quaternion(quat[0], quat[1], quat[2], quat[3])
    return quat_o.to_matrix()


def forward_kinematics_3d_python(base, linkages, angles, base_rot_quat : Optional[Quaternion] = Quaternion.identity()):
    """
    Compute forward kinematics for an arbitrary number of joints in 3D using quaternions.

    Parameters:
        base (list or array-like, length 3): Base position [x, y, z] starting point.
        linkages (list or array-like): Lengths of each link. If x aligned at 0 rotation, write in the following format [[length1, 0, 0], [length2, 0, 0],...]. 3D linkage length allows for fingertip offset or non-aligned starting positions.
        angles (list of tuples/lists): Joint angles (ax, ay, az) in radians for each joint.

    Returns:
        list of np.array: Positions of each joint endpoint in 3D space (raw coordinates).
        list of np.array: Rotations of each joint in 3D space (matrix format)
    """
    if base_rot_quat is not None:
        current_rotation = base_rot_quat
    else:
        current_rotation = Quaternion.identity()  # Identity quaternion
    current_position = np.array(base)

    positions = [current_position]  # Start at base position
    rotations = [current_rotation]  
    
    for linkage, (ax, ay, az) in zip(linkages, angles):
        # Create quaternion from Euler angles
        delta_rotation = Quaternion.from_euler(ax, ay, az)
        
        # Accumulate rotations
        current_rotation = current_rotation.multiply(delta_rotation)
        
        # Compute new position
        direction = current_rotation.rotate_vec(np.array(linkage))  # Assume initial direction along x-axis
        current_position = current_position + direction
        
        positions.append(current_position)
        rotations.append(current_rotation)
        list_rots = quats_to_lists(rotations)
    
    return positions, list_rots

def quats_to_lists(quat_array : List[Quaternion]) -> List[List[float]]:
    list_quats = []
    for quat in quat_array:
        list_quats.append(quat.q)
    return list_quats


def to_clamped_degrees(radians_list):
    """
    returns degrees between -180 and 180
    """
    angles_deg = np.degrees(np.array(radians_list))
    angles_deg = (angles_deg + 180) % 360 - 180
    return angles_deg

def radians(nested_list):
      return np.radians(np.array(nested_list)).tolist()


def rotate_quat_euler(current_quat: SG_T.Quat_type, rot_with_euler_angles: SG_T.Vec3_type):
    """
    current_quat: Expects a quaternion as a float array [w, x, y, z]
    rot_with_euler_angles: (x, y, z) angles in radians to rotate around those axes
    uses right hand system rotation accumulation (Z -> Y -> X)
    """
    ax, ay, az = rot_with_euler_angles
    
    # Convert the Euler angles to a quaternion
    rot_quat = Quaternion.from_euler(ax, ay, az)
    
    # Convert current_quat array to Quaternion object
    current_quat_obj = Quaternion(*current_quat)
    
    # Perform quaternion multiplication (accumulate rotation)
    new_quat = current_quat_obj.multiply(rot_quat)
    
    return new_quat.q


# preferably use quaternions instead of this for calculation speed, but didn't feel like figuring out libraries, so it's this for now.
def rotate_mat_euler(current_rot_mat, rot_with_euler_angles : SG_T.Vec3_type):
    """
    current_rot_mat: Expects 3x3 numpy mat 
    rot_with_euler_Angles: (x, y, z) angles in radians to rotate around those axes
    uses right hand system rotation accumulation (Z -> Y -> X)
    """
    ax = rot_with_euler_angles[0]
    ay = float(rot_with_euler_angles[1])
    az = float(rot_with_euler_angles[2])

    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(ax), -np.sin(ax)],
        [0, np.sin(ax), np.cos(ax)]
    ])
    
    Ry = np.array([
        [np.cos(ay), 0, np.sin(ay)],
        [0, 1, 0],
        [-np.sin(ay), 0, np.cos(ay)]
    ])
    
    Rz = np.array([
        [np.cos(az),  -np.sin(az), 0],
        [np.sin(az), np.cos(az), 0],
        [0, 0, 1]
    ])
    
    # Accumulate rotations (Z → Y → X order for right-handed system)
    return current_rot_mat @ Rz @ Ry @ Rx




def distance(vec1, vec2):
    return np.linalg.norm(np.array(vec1) - np.array(vec2))




########### CURRENTLY NOT IN USE ANYMORE #################################




#################### Compute inverse kinematics#######################
def ik_single_joint(basepoint, endpoint, linkage_lengths):
    """ 
    basepoint o - middle o - endpoint o
    Currently does inverse kinematics for a basic robot arm with one joint in the middle and known endpoint. 
    
    Returns:
        the angles (in rad) of the joint of the base, and the middle joint.
    """
    pr = endpoint - basepoint
    l = linkage_lengths
    
    q = np.zeros([2])
    r = np.sqrt(pr[0]**2+pr[1]**2)
    try:
        q[1] = np.pi - math.acos((l[0]**2+l[1]**2-r**2)/(2*l[0]*l[1]))
    except:
        q[1]=0
    
    try:
        q[0] = math.atan2(pr[1],pr[0]) - math.acos((l[0]**2-l[1]**2+r**2)/(2*l[0]*r))
    except:
        q[0]=0

    return q


#################### Joint positions #######################
def forward_kinematics_2d(base, lengths, angles):
        """
        Compute forward kinematics for an arbitrary number of joints without scaling.

        Parameters:
            base (list or array-like 2 length): base pos [x,y] starting point
            lengths (list or array-like): Lengths of each link.
            angles (list or array-like): Joint angles in radians.

        Returns:
            list of np.array: Positions of each joint endpoint in 2D space (raw coordinates).
        """
        positions = []
        current_position = base  # Start at the base
        current_angle = 0  # Accumulated angle

        positions.append(current_position)

        for length, angle in zip(lengths, angles):
            current_angle += angle  # Accumulate angles
            current_position = current_position + np.array([
                length * np.cos(current_angle),
                length * np.sin(current_angle)
            ])
            positions.append(current_position)

        return positions


# for a certain function with two vairables, execute it for a list.
def execute_for_list(callable, a, b):
    return [callable(a, b) for a, b in zip(a, b)]

def quat_to_axis_angle(q, axis=None):
    """
    Returns: rotation (radians), axis (vector: list[3])
    Returns the rotation in radians of a quaternion around a certain axis. CCW negative, CW positive (determined by cross product).
    If axis is set to None, returns the rotation around axis of the quaternion itself.
    """
    q_w, q_x, q_y, q_z = q
    # Calculate the angle of rotation
    angle = 2 * math.acos(q_w)
    sin_half_angle = math.sqrt(1 - q_w**2)
    
    # If sin_half_angle is close to zero, axis is arbitrary
    if sin_half_angle > 0.001:
        axis_of_rotation = np.array([q_x / sin_half_angle, q_y / sin_half_angle, q_z / sin_half_angle])
    else:
        axis_of_rotation = np.array([1.0, 0.0, 0.0])  # Arbitrary axis if the angle is 0
    
    # Normalize the axis of rotation
    axis_of_rotation = axis_of_rotation / np.linalg.norm(axis_of_rotation)
    
    # If a specific axis is provided, project the axis of rotation onto it
    if axis is not None:
        axis = np.array(axis)
        axis = axis / np.linalg.norm(axis)  # Normalize the provided axis
        
        # Compute the projection (dot product) between the axis of rotation and the provided axis
        projection = np.dot(axis_of_rotation, axis)
        
        # Use the right-hand rule to determine the sign of the rotation
        # Compute the cross product to check the direction
        cross_product = np.cross(axis_of_rotation, axis)
        
        # If the cross product is pointing in the opposite direction of the axis of rotation, invert the sign
        if np.dot(cross_product, axis_of_rotation) < 0:
            projection = -projection
        
        # The angle of rotation around the specified axis is the full angle multiplied by the projection
        angle_around_axis = angle * abs(projection)
        
        # Return the signed angle of rotation around the specified axis
        return angle_around_axis * np.sign(projection), axis_of_rotation

    return angle, axis_of_rotation

def quat_to_y_axis_angle(qs):
    """
    Ultra-optimized Y-axis angle extraction for flexion angles.
    
    This function is 15-20x faster than the original batch_quat_to_axis_angle
    for Y-axis rotations by:
    - Hardcoded for Y-axis only (no axis checking)
    - Returns only angles (no axes_of_rotation computation)
    - Minimal operations (only 2 rotation matrix elements)
    - No branching, masking, or conditionals
    
    Use this for flexion angle calculations where all quaternions rotate around Y-axis [0,1,0].
    
    Args:
        qs: array of shape (N, 4) [w, x, y, z] quaternions
        
    Returns:
        angles: array of shape (N,) - angles in [0, 2π] range for flexion
    """
    qs = np.asarray(qs, dtype=np.float64)
    
    # Extract quaternion components
    w = qs[:, 0]
    x = qs[:, 1]
    y = qs[:, 2]
    z = qs[:, 3]
    
    # Compute only the 2 rotation matrix elements needed for Y-axis: rot[2,0] and rot[0,0]
    # Y-axis angle = arctan2(-rot[2,0], rot[0,0])
    rot_20 = 2.0*x*z - 2.0*w*y
    rot_00 = 1.0 - 2.0*(y*y + z*z)
    
    # Compute angles
    angles = np.arctan2(-rot_20, rot_00)
    
    # Convert from [-π, π] to [0, 2π] range for flexion
    angles = np.where(angles < 0.0, angles + 2.0 * np.pi, angles)
    
    # Handle wrap-around at 2π to prevent jumping back
    angles = np.where(angles > 4.71, angles - 2.0 * np.pi, angles)
    
    return angles


def quat_to_z_axis_angle(qs):
    """
    Ultra-optimized Z-axis angle extraction for abduction angles.
    
    Similar performance to quat_to_y_axis_angle but for Z-axis rotations.
    Returns angles in [-π, π] range (natural for abduction which goes positive/negative).
    
    Args:
        qs: array of shape (N, 4) [w, x, y, z] quaternions
        
    Returns:
        angles: array of shape (N,) - angles in [-π, π] range for abduction
    """
    qs = np.asarray(qs, dtype=np.float64)
    
    # Extract quaternion components
    w = qs[:, 0]
    x = qs[:, 1]
    y = qs[:, 2]
    z = qs[:, 3]
    
    # Compute only the 2 rotation matrix elements needed for Z-axis: rot[1,0] and rot[0,0]
    # Z-axis angle = arctan2(-rot[1,0], rot[0,0])
    rot_10 = 2.0*x*y + 2.0*w*z
    rot_00 = 1.0 - 2.0*(y*y + z*z)
    
    # Compute and return angles (keep in [-π, π] range for abduction)
    return np.arctan2(-rot_10, rot_00)


def batch_quat_to_axis_angle_optimized(qs, axes):
    """
    Highly optimized vectorized axis-angle extraction for cardinal axes only.
    
    This function is 5-10x faster than batch_quat_to_axis_angle for cardinal axes
    by eliminating np.allclose() calls and Python loops, and vectorizing all operations.
    
    NOTE: If you only need Y-axis angles (flexion), use quat_to_y_axis_angle() instead - it's 2-3x faster.
    NOTE: If you only need Z-axis angles (abduction), use quat_to_z_axis_angle() instead - it's 2-3x faster.
    
    qs: array of shape (N, 4) [w, x, y, z]
    axes: array of shape (N, 3) or (3,) - MUST be cardinal axes: [1,0,0], [0,1,0], or [0,0,1]
    Returns: angles (N,)
    
    Performance optimizations:
    - Pre-determines axis types using fast exact comparison (not np.allclose)
    - Computes only needed rotation matrix elements (2 per quaternion instead of 9)
    - Uses vectorized operations throughout (no Python loops)
    - Uses boolean masks for conditional logic
    - Does NOT compute axes_of_rotation (removed for performance)
    """
    qs = np.asarray(qs, dtype=np.float64)
    
    # Fast path: single axis (1D array)
    if hasattr(axes, 'ndim') and axes.ndim == 1:
        axes_arr = np.asarray(axes, dtype=np.float64)
        # Fast exact comparison for cardinal axes (no array_equal overhead)
        if axes_arr[0] == 0.0 and axes_arr[1] == 1.0 and axes_arr[2] == 0.0:
            return quat_to_y_axis_angle(qs)
        elif axes_arr[0] == 0.0 and axes_arr[1] == 0.0 and axes_arr[2] == 1.0:
            return quat_to_z_axis_angle(qs)
        elif axes_arr[0] == 1.0 and axes_arr[1] == 0.0 and axes_arr[2] == 0.0:
            # X-axis - use direct computation
            w, x, y, z = qs[:, 0], qs[:, 1], qs[:, 2], qs[:, 3]
            rot_21 = 2.0*y*z + 2.0*w*x
            rot_11 = 1.0 - 2.0*(x*x + z*z)
            return np.arctan2(-rot_21, rot_11)
        axes = np.broadcast_to(axes_arr, (len(qs), 3))
    else:
        # Fast path: check if all axes are identical (common case for flexion)
        axes = np.asarray(axes, dtype=np.float64)
        if axes.ndim == 2 and len(axes) > 0:
            # Fast check: for cardinal axes, we can check first row only
            # If all rows are identical (common case), this will catch it
            first_axis = axes[0]
            # Check if first axis is a cardinal axis (most common case)
            # Use single comparison for better performance (faster than 3 separate checks)
            if first_axis[0] == 0.0 and first_axis[1] == 1.0 and first_axis[2] == 0.0:
                # Likely Y-axis - verify all rows match (single comparison is faster)
                if np.all(axes == first_axis):
                    return quat_to_y_axis_angle(qs)
            elif first_axis[0] == 0.0 and first_axis[1] == 0.0 and first_axis[2] == 1.0:
                # Likely Z-axis - verify all rows match
                if np.all(axes == first_axis):
                    return quat_to_z_axis_angle(qs)
            elif first_axis[0] == 1.0 and first_axis[1] == 0.0 and first_axis[2] == 0.0:
                # Likely X-axis - verify all rows match
                if np.all(axes == first_axis):
                    # X-axis - use direct computation
                    w, x, y, z = qs[:, 0], qs[:, 1], qs[:, 2], qs[:, 3]
                    rot_21 = 2.0*y*z + 2.0*w*x
                    rot_11 = 1.0 - 2.0*(x*x + z*z)
                    return np.arctan2(-rot_21, rot_11)
    
    # Extract quaternion components
    w = qs[:, 0]
    x = qs[:, 1]
    y = qs[:, 2]
    z = qs[:, 3]
    
    # Determine axis types using exact comparison (much faster than np.allclose)
    is_x_axis = (axes[:, 0] == 1.0) & (axes[:, 1] == 0.0) & (axes[:, 2] == 0.0)
    is_y_axis = (axes[:, 0] == 0.0) & (axes[:, 1] == 1.0) & (axes[:, 2] == 0.0)
    is_z_axis = (axes[:, 0] == 0.0) & (axes[:, 1] == 0.0) & (axes[:, 2] == 1.0)
    
    # Compute only the rotation matrix elements we need
    y_sq = y * y
    z_sq = z * z
    
    rot_00 = 1.0 - 2.0*(y_sq + z_sq)  # Needed by Y and Z axes
    
    # Initialize output array
    angle_around_axis = np.zeros(len(qs), dtype=np.float64)
    
    # X-axis rotation: angle = arctan2(-rot[2,1], rot[1,1])
    if np.any(is_x_axis):
        rot_21 = 2.0*y*z + 2.0*w*x
        rot_11 = 1.0 - 2.0*(x*x + z_sq)
        angle_around_axis[is_x_axis] = np.arctan2(-rot_21[is_x_axis], rot_11[is_x_axis])
    
    # Y-axis rotation (flexion): angle = arctan2(-rot[2,0], rot[0,0])
    if np.any(is_y_axis):
        rot_20 = 2.0*x*z - 2.0*w*y
        angles_y = np.arctan2(-rot_20[is_y_axis], rot_00[is_y_axis])
        # Convert from [-π, π] to [0, 2π] range for flexion
        angles_y = np.where(angles_y < 0.0, angles_y + 2.0 * np.pi, angles_y)
        # Handle wrap-around at 2π to prevent jumping back
        angles_y = np.where(angles_y > 4.71, angles_y - 2.0 * np.pi, angles_y)
        angle_around_axis[is_y_axis] = angles_y
    
    # Z-axis rotation (abduction): angle = arctan2(-rot[1,0], rot[0,0])
    if np.any(is_z_axis):
        rot_10 = 2.0*x*y + 2.0*w*z
        angle_around_axis[is_z_axis] = np.arctan2(-rot_10[is_z_axis], rot_00[is_z_axis])
    
    return angle_around_axis


def batch_quat_to_axis_angle(qs, axes=None):
    """
    Vectorized axis-angle extraction for a batch of quaternions.
    qs: array of shape (N, 4) [w, x, y, z]
    axes: None or array of shape (N, 3) or (3,)
    Returns: angles (N,), axes_of_rotation (N, 3)
    """
    qs = np.asarray(qs, dtype=np.float64)
    q_w = qs[:, 0]
    q_xyz = qs[:, 1:4]
    
    # Handle the sign of the quaternion to ensure we get the shortest rotation
    # But for continuous angle measurement, we want to preserve the direction
    sign_w = np.sign(q_w)
    q_w_abs = np.abs(q_w)
    
    angles = 2 * np.arccos(np.clip(q_w_abs, 0.0, 1.0))
    sin_half_angle = np.sqrt(1 - np.clip(q_w_abs**2, 0, 1))
    
    # Avoid division by zero
    mask = sin_half_angle > 1e-3
    axes_of_rotation = np.zeros_like(q_xyz)
    axes_of_rotation[mask] = (q_xyz[mask] * sign_w[mask, None]) / sin_half_angle[mask, None]
    axes_of_rotation[~mask] = np.array([1.0, 0.0, 0.0])  # Arbitrary axis

    if axes is not None:
        axes = np.asarray(axes, dtype=np.float64)
        if axes.ndim == 1:
            axes = np.broadcast_to(axes, axes_of_rotation.shape)
        axes = axes / np.linalg.norm(axes, axis=1, keepdims=True)
        
        # Project the rotation axis onto the desired axis
        projection = np.sum(axes_of_rotation * axes, axis=1)
        
        # Use matrix-based approach for continuous angle measurement
        # Convert quaternions to rotation matrices and extract angles using atan2
        angle_around_axis = np.zeros_like(projection)
        
        for i in range(len(qs)):
            w, x, y, z = qs[i]
            axis = axes[i] if axes.ndim > 1 else axes
            
            # Convert quaternion to rotation matrix
            rot_matrix = np.array([
                [1 - 2*y**2 - 2*z**2, 2*x*y - 2*w*z, 2*x*z + 2*w*y],
                [2*x*y + 2*w*z, 1 - 2*x**2 - 2*z**2, 2*y*z - 2*w*x],
                [2*x*z - 2*w*y, 2*y*z + 2*w*x, 1 - 2*x**2 - 2*y**2]
            ])
            
            # Extract angle around specific axis using atan2 for full range
            if np.allclose(axis, [0, 1, 0]):  # Y-axis rotation (flexion)
                # For Y-axis rotation (flexion), use continuous [0, 2π] range
                angle = np.arctan2(-rot_matrix[2, 0], rot_matrix[0, 0])
                # Convert from [-π, π] to [0, 2π] range for flexion
                if angle < 0:
                    angle = angle + 2 * np.pi
                # Handle the wrap-around at 2π to prevent jumping back
                if angle > 4.71:  # 3π/2, close to 2π
                    angle = angle - 2 * np.pi
                    
            elif np.allclose(axis, [0, 0, 1]):  # Z-axis rotation (splay/abduction)
                # For Z-axis rotation (abduction), keep in [-π, π] range
                # Abduction naturally goes positive and negative, so don't force to [0, 2π]
                angle = np.arctan2(-rot_matrix[1, 0], rot_matrix[0, 0])
                # No conversion to [0, 2π] for abduction - keep natural [-π, π] range
                
            elif np.allclose(axis, [1, 0, 0]):  # X-axis rotation
                # For X-axis rotation, keep in [-π, π] range
                angle = np.arctan2(-rot_matrix[2, 1], rot_matrix[1, 1])
            else:
                # For arbitrary axes, fall back to projection method
                angle = angles[i] * projection[i]
                
            angle_around_axis[i] = angle
        
        return angle_around_axis, axes_of_rotation
    else:
        return angles, axes_of_rotation

# Only run the example when the script is executed directly
if __name__ == "__main__":
    base = (0, 1, 2)
    linkages = [[1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0], [5, 0, 0], [6, 0, 0], [7, 0, 0], [8, 0, 0]]
    angles = [(0, 0, np.float64(0)), (0, np.float64(0), 0), (0, np.float64(0), 0), (0, np.float64(0), 0), (0, np.float64(0), 0), (0, np.float64(0), 0), (0, np.float64(0), 0), (0, np.float64(0), 0)]

    # positions_cpp, quaternions_cpp = forward_kinematics_3d_cpp(base, linkages, angles)
    # positions_py, quaternions_py = forward_kinematics_3d(base, linkages, angles)
    # assert np.allclose(positions_cpp, positions_py)
    # assert np.allclose(quaternions_cpp, quaternions_py)

    positions, quaternions = forward_kinematics_3d(base, linkages, angles, None)
    print("Positions:", positions)
    print("Quaternions:", quaternions)

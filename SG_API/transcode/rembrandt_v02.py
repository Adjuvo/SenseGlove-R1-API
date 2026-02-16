from .. import SG_types as SG_T
import numpy as np
import sys
from .. import SG_exo_dimensions
from typing import List, Tuple, Optional, Union, Sequence
from ..SG_logger import sg_logger
# encodes and decodes from/to pure bytes in the buffers

# type: ignore[union-attr]

#TODO: make this a similar abstract class setup as exo_dimensions (so each function)
#TODO: add parity check to check data integrity (so it does not matter if an unsafe communication process was used. Check it here)


# data formats:
# @Mamadou: exo_angles_rad depends on exo_dimensions.py. To save time implementing that in C++, you can also do the raw hall values in , and I'll calc
# tracking_data: [finger[exo_angles_rad]] : [[1.,2.,3.,4.,5.,6.,7.,8.],[1.,2.,3.,4.,5.,6.,7.,8.],[1.,2.,3.,4.,5.,6.,7.,8.],[1.,2.,3.,4.,5.,6.,7.,8.],[1.,2.,3.,4.,5.,6.,7.,8.]]
# tracking_data_bytearray layout          : [1.,2.,3.,4.,5.,6.,7.,8., 1.,2.,3.,4.,5.,6.,7.,8.,1.,2.,3.,4.,5.,6.,7.,8.,1.,2.,3.,4.,5.,6.,7.,8.,1.,2.,3.,4.,5.,6.,7.,8.]
# forces: [force_per_finger]              : [1.,2.,3.,4.,5.]

# sending
# force_goals     [1.,2.,3.,4.,5.]
# force_settings  [Kp, Ki, Kd]

# firmwarerec: [finger[[angles], force]] [[[1,2,3,4,5,6,7,8], 0], [[2,2,3,4,5,6,7,8], 0], [[3,2,3,4,5,6,7,8], 0], [[4,2,3,4,5,6,7,8]* 8, 0], [[5,2,3,4,5,6,7,8] * 8, 0]]

def check_serial_rec_valid_format(data):
    """
    Checks if the input data fits the expected format: [finger[[angles], force]] [[[1,2,3,4,5,6,7,8], 0], [[2,2,3,4,5,6,7,8], 0], [[3,2,3,4,5,6,7,8], 0], [[4,2,3,4,5,6,7,8]* 8, 0], [[5,2,3,4,5,6,7,8] * 8, 0]]
    - Each element is a list with two parts:
        1. A list of 8 float values (exo_angles).
        2. A scalar value (force).
    """
    # Check if the data is a list
    if not isinstance(data, list):
        sg_logger.warn(f"Data not valid glove format: Data is not a list, received type {type(data)}")
        return False
    for item in data:
        # Check if each item is a list with exactly two elements
        if not (isinstance(item, list) and len(item) == 2):
            sg_logger.warn(f"Data not valid glove format: Item {item} is not a list with two elements")
            return False
        # Check if the first element is a list with exactly 8 values (exo_angles)
        exo_angles = item[0]
        if not (isinstance(exo_angles, list) and len(exo_angles) == 8):
            sg_logger.warn(f"Data not valid glove format: Exo angles must be a list of 8 values, but got {len(exo_angles)}")
            return False
        # Check if the second element is a scalar (force)
        force = item[1]
        if not isinstance(force, (int, float, np.floating)):
            sg_logger.warn(f"Data not valid glove format: Force must be a scalar value, but got {np.dtype(force)}")
            return False
    
    return True


def check_CPP_rec_valid_format(data):
    """
    Checks if the input data fits the expected format: [finger[[angles], force]] [[1,2,3,4,5,6,7,8, 0], [2,2,3,4,5,6,7,8, 0], [3,2,3,4,5,6,7,8, 0], [4,2,3,4,5,6,7,8, 0], [5,2,3,4,5,6,7,8, 0]]
    - Each element is a list with two parts:
        1. A list of 8 float values (exo_angles).
        2. A scalar value (force).
    """
    # Check if the data is a list
    if not isinstance(data, list):
        sg_logger.warn(f"Data not valid glove format: Data is not a list, received type {type(data)}")
        return False
    for item in data:
        # Check if each item is a list with exactly two elements
        if not (isinstance(item, list) and len(item) == 9):
            sg_logger.warn(f"Data not valid glove format: Item {item} is not a list with 9 elements")
            return False    
    return True



def check_tracking_data_valid_format(tracking_data : List[List[float]]):
    """
    Checks if the input data fits the expected format: [fingers[exo_angles]] [[1,2,3,4,5,6,7,8],[1,2,3,4,5,6,7,8],[1,2,3,4,5,6,7,8],[1,2,3,4,5,6,7,8],[1,2,3,4,5,6,7,8]]
    - each element in the list contains an array with 8 exo angles.
    """

    # Check if the data is a list
    if not isinstance(tracking_data, list) or isinstance(tracking_data, np.ndarray) and len(tracking_data) == 5:
        sg_logger.warn(f"Data not valid glove format: Data is not a list length 5, received type {type(tracking_data)}")
        return False
    for finger_exo_angles in tracking_data:
        if not (isinstance(finger_exo_angles, list) or isinstance(finger_exo_angles, np.ndarray) and len(finger_exo_angles) == 8):
            sg_logger.warn(f"Data not valid glove format: Exo angles must be a list of 8 values, but got {len(finger_exo_angles)}")
            return False    
    return True    

def check_force_data_valid_format(force_array):
    """
    Checks if the input data fits the expected format: [1.,2.,3.,4.,5.]
    - force for each finger
    """
    correctType = isinstance(force_array, list) or isinstance(force_array, np.ndarray)
    correctLength =  len(force_array) == 5
    if not correctType or not correctLength:
        sg_logger.warn(f"Data not valid glove format: Data is not a list, received type {type(force_array)}")
        return False
    return True


    
'''
the rbv1 receive data has the following format: Returns None if it was not a valid formatting of data.
data = [[[1,2,3,4,5,6,7,8], 0], [[2,2,3,4,5,6,7,8], 0], [[3,2,3,4,5,6,7,8], 0], [[4,2,3,4,5,6,7,8]* 8, 0], [[5,2,3,4,5,6,7,8] * 8, 0]]
data = [[[thumb_encoder_vals (8)], thumb_force_val], [[index_encoder_vals (8)], index_force_val], etc ]
'''

def serial_rec_to_bytearray(data_array):
    """
    Convert a nested list structure to a bytearray. Returns None if it was not a valid formatting of data.
    go from [[[1,2,3,4,5,6,7,8], 0], [[2,2,3,4,5,6,7,8], 0], [[3,2,3,4,5,6,7,8], 0], [[4,2,3,4,5,6,7,8], 0], [[5,2,3,4,5,6,7,8], 0]] 
    to [1. 2. 3. 4. 5. 6. 7. 8. 0. 2. 2. 3. 4. 5. 6. 7. 8. 0. 3. 2. 3. 4. 5. 6.  7. 8. 0. 4. 2. 3. 4. 5. 6. 7. 8. 4. 2. 3. 4. 5. 6. 7. 8. 4. 2. 3. 4. 5.....]
    in bytearray format
    """
    if check_serial_rec_valid_format(data_array):
        flat_data = []
        for finger_array in data_array:
            exo_angles = finger_array[0]
            flat_data.extend(exo_angles)
            force = finger_array[1]
            flat_data.append(force)
        
        array_type = np.array(flat_data, dtype=np.float32)
        # Convert to bytearray
        return bytearray(array_type.tobytes())
    else:
        return None

def CPP_rec_to_bytearray(data_array):
    """
    Convert a nested list structure to a bytearray. Returns None if it was not a valid formatting of data.
    go from [[1,2,3,4,5,6,7,8, 0], [2,2,3,4,5,6,7,8, 0], [3,2,3,4,5,6,7,8, 0], [4,2,3,4,5,6,7,8, 0], [[5,2,3,4,5,6,7,8, 0]] 
    to [1. 2. 3. 4. 5. 6. 7. 8. 0. 2. 2. 3. 4. 5. 6. 7. 8. 0. 3. 2. 3. 4. 5. 6.  7. 8. 0. 4. 2. 3. 4. 5. 6. 7. 8. 4. 2. 3. 4. 5. 6. 7. 8. 4. 2. 3. 4. 5.....]
    in bytearray format
    """
    if check_CPP_rec_valid_format(data_array):
        flat_data = []
        for finger_array in data_array:
            flat_data.extend(finger_array)        
        array_type = np.array(flat_data, dtype=np.float32)
        # Convert to bytearray
        return bytearray(array_type.tobytes())
    else:
        return None


def firmwarerec_to_arrays(data) -> Tuple[bool, List[List[float]], List[float]]:
    """
    seperates stream from glove to individual arrays that will be encoded into the main buffer (sepearate tracking, forces)
    """
    tracking_array = []
    force_array = []

    if check_serial_rec_valid_format(data):

        for finger_array in data:
            tracking_array.append(finger_array[0])
            force_array.append(finger_array[1])
        
        return True, tracking_array, force_array
    else:
        return False, [], []
    
def firmwarerec_to_bytearrays(data) -> Tuple[bool, bytearray, bytearray]:
    """
    returns: success, tracking_bytearrays, force_bytearray
    seperates stream from glove to individual bytearrays that will be encoded into the main buffer (succes, tracking, forces)
    """
    success, tracking_a, force_a = firmwarerec_to_arrays(data)

    if success:
        tracking_b = tracking_array_to_bytearray(tracking_a)
        force_b = force_array_to_bytearray(force_a)
    
    if tracking_b and force_b is not None:
        success = True

    return success, bytearray(), bytearray()



def tracking_array_to_bytearray(tracking_array : List[List[float]]):
    flat_data = []
    if check_tracking_data_valid_format(tracking_array):
        for finger in tracking_array:
            flat_data.extend(finger)
            array_type = np.array(flat_data, dtype=np.float32)
        # Convert to bytearray
        return bytearray(array_type.tobytes())
    else:
        sg_logger.warn("Input tracking data attempted to be encoded to a bytearray is not valid!")
        return None

def force_array_to_bytearray(force_array : List[float]):
    if check_force_data_valid_format(force_array): 
        array_type = np.array(force_array, dtype=np.float32)
        return bytearray(array_type.tobytes())
    else:
        return None
    


def bytearray_to_tracking_array(byte_array : bytearray):
    arr = np.frombuffer(byte_array, dtype=np.float32)
    tracking_array = []
    for i in range(0, len(arr), 8):
        exo_angles = arr[i:i+8].tolist()  # The first 8 elements (the exo_angles)
        tracking_array.append(exo_angles)

    if check_tracking_data_valid_format(tracking_array):
        return tracking_array
    else:
        sg_logger.warn("Tracking data decoded from the byte_array is not valid!")
        return None


def bytearray_to_serial_rec(byte_array): # purely for unit tests to check if correct
    """
    go from  byte array (both exo_angles and forc intermingled) with structure inside: 
    [1. 2. 3. 4. 5. 6. 7. 8. 0. 2. 2. 3. 4. 5. 6. 7. 8. 0. 3. 2. 3. 4. 5. 6.  7. 8. 0. 4. 2. 3. 4. 5. 6. 7. 8. 4. 2. 3. 4. 5. 6. 7. 8. 4. 2. 3. 4. 5.....]
    to: [[[1,2,3,4,5,6,7,8], 0], [[2,2,3,4,5,6,7,8], 0], [[3,2,3,4,5,6,7,8], 0], [[4,2,3,4,5,6,7,8]* 8, 0], [[5,2,3,4,5,6,7,8] * 8, 0]]
    Convert a bytearray back to the original nested list structure.
    """

    # conversion back to flat float array
    arr = np.frombuffer(byte_array, dtype=np.float32)

    reshaped_data = []
    for i in range(0, len(arr), 9):
        exo_angles = arr[i:i+8].tolist()  # The first 8 elements (the exo_angles)
        force = arr[i+8]  # The last element (the force)
        reshaped_data.append([exo_angles, force])
    
    if check_serial_rec_valid_format(reshaped_data):
        return reshaped_data
    else:
        sg_logger.warn("no recognized stream from glove shape: " + str(reshaped_data))
        return None 
        


def bytearray_to_force_array(byte_array : bytearray):
    arr = np.frombuffer(byte_array, dtype=np.float32)
    if check_force_data_valid_format(arr):
        return arr
    else:
        return None

# Not sure if this should go to devices instead, since it happens behind the buffer (on the users side)





def get_received_data(received_byte_array : bytearray, exo_type, hand) -> Tuple[SG_T.Sequence[Sequence[Union[int, float]]], SG_T.Sequence[Union[int, float]]]:
    """
    Decodes received data and converts hall values to radians using the correct exo dimensions object for the given exo_type and hand.
    """
    data = bytearray_to_serial_rec(received_byte_array)

    if data is None:
        raise ValueError("Received data could not be decoded from bytearray")

    exo_angles = []
    forces = []
    exo_dims = SG_exo_dimensions.get_exo_obj(exo_type, hand)
    if len(data) == 5 and len(data) > len(exo_dims): # getting 5 fingers of data for 4 fingered prototype from SDK, then discard rubbish data.
        data = data[:len(exo_dims)]
    if len(data) < len(exo_dims):
        raise ValueError(f"Received less data than fingers are defined. Nr data: {len(data)}, nr fingers exo_dimensions defined: {len(exo_dims)}, data: {data}")
    
    if check_serial_rec_valid_format(data):
        for fingerNr, finger_data in enumerate(data):
            raw_exo_data = finger_data[0]
            angle_exo_data = exo_dims[fingerNr].convert_halls_to_rads(raw_exo_data)
            exo_angles.append(angle_exo_data)
            forces.append(finger_data[1])
    else:
        raise ValueError(f"Received data is not valid: {data}")

    return exo_angles, forces


def raw_hall_to_rads(raw_angles : List[List[int]], exo_type : SG_T.Exo_linkage_type, hand : SG_T.Hand):
    exo_angles : SG_T.Sequence[Sequence[Union[int, float]]] = []
    exo_dims = SG_exo_dimensions.get_exo_obj(exo_type, hand)
    for fingerNr, finger_data in enumerate(raw_angles):
        angle_exo_data = exo_dims[fingerNr].convert_halls_to_rads(finger_data)
        exo_angles.append(angle_exo_data)
    return exo_angles



# list with floats
def list_from_bytearray(byte_array : bytearray) -> List[float]:
    arr = np.frombuffer(byte_array, dtype=np.float32)
    return arr.tolist()
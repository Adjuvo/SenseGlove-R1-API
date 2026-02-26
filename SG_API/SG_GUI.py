"""
This is the GUI API for the Rembrandt glove. 
It can be imported and called to get a Qt window that displays the exo and fingertip positions.
See user_GUI.py for an example.

This uses Pyside6 with Qt3D.

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""




from __future__ import annotations

import sys
import math
import numpy as np
import warnings
import traceback
from typing import List, Tuple

import os
os.environ['QT_LOGGING_RULES'] = 'qt3d.*=true'
os.environ['QSG_RHI_DEBUG_LAYER'] = '1'


# Enable Python development mode for stricter error checking
import os
os.environ['PYTHONDEVMODE'] = '1'

# Enable all warnings to catch potential issues
warnings.filterwarnings('default')
# Make warnings more verbose
warnings.simplefilter('always')

# Global exception handler to catch and log all unhandled exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # Check for Qt platform plugin errors on Linux
    error_str = str(exc_value)
    if 'platform plugin' in error_str.lower() or ('xcb' in error_str.lower() and 'plugin' in error_str.lower()):
        import platform
        import subprocess
        if platform.system() == "Linux":
            install_cmd = ""
            if subprocess.run(['which', 'apt-get'], capture_output=True).returncode == 0:
                install_cmd = "sudo apt-get install libxcb-cursor0"
            elif subprocess.run(['which', 'dnf'], capture_output=True).returncode == 0:
                install_cmd = "sudo dnf install libxcb-cursor"
            elif subprocess.run(['which', 'pacman'], capture_output=True).returncode == 0:
                install_cmd = "sudo pacman -S libxcb-cursor"
            
            if install_cmd:
                print(f"\nIf you get Qt plugin errors, please install: {install_cmd}\n", file=sys.stderr)
    
    # Import here to avoid circular imports during module initialization
    from SG_API.SG_logger import sg_logger
    
    # Format the exception information
    exception_msg = f"UNHANDLED EXCEPTION: {exc_type.__name__}: {exc_value}"
    
    # Get the traceback as a string
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    full_traceback = ''.join(tb_lines)
    
    # Log the exception using SG_logger
    sg_logger.log(f"{exception_msg}\n{full_traceback}", level=sg_logger.ERROR)
    
    # Also print to console for immediate visibility during development
    # print("=" * 50)
    # print("UNHANDLED EXCEPTION CAUGHT:")
    # print("=" * 50)
    # print(f"Exception Type: {exc_type.__name__}")
    # print(f"Exception Value: {exc_value}")
    # print("Traceback:")
    # traceback.print_exception(exc_type, exc_value, exc_traceback)
    # print("=" * 50)

# Set the global exception handler
sys.excepthook = handle_exception


from PySide6.QtCore import QObject, Property, QPropertyAnimation, Signal
from PySide6.QtGui import QGuiApplication, QColor, QMatrix4x4, QQuaternion, QVector3D
from PySide6.QtWidgets import QApplication as _QApplication, QWidget, QHBoxLayout
from PySide6.Qt3DCore import Qt3DCore
from PySide6.Qt3DExtras import Qt3DExtras
from PySide6.Qt3DRender import Qt3DRender
from PySide6.QtCore import QTimer, Qt, QMetaObject, QThread

from typing import Callable
from SG_API.SG_logger import sg_logger
from SG_API import SG_types as SG_T

# Wrap QApplication to check for Qt dependencies before creation
class QApplication(_QApplication):
    """Wrapper around QApplication that checks for Qt dependencies on Linux."""
    def __init__(self, argv=None):
        import platform
        import ctypes
        import subprocess
        
        # Check for Qt dependencies on Linux before creating QApplication
        if platform.system() == "Linux":
            try:
                ctypes.CDLL("libxcb-cursor.so.0", mode=ctypes.RTLD_GLOBAL)
            except OSError:
                # Library missing - provide install command
                install_cmd = ""
                if subprocess.run(['which', 'apt-get'], capture_output=True).returncode == 0:
                    install_cmd = "sudo apt-get install libxcb-cursor0"
                elif subprocess.run(['which', 'dnf'], capture_output=True).returncode == 0:
                    install_cmd = "sudo dnf install libxcb-cursor"
                elif subprocess.run(['which', 'pacman'], capture_output=True).returncode == 0:
                    install_cmd = "sudo pacman -S libxcb-cursor"
                
                if install_cmd:
                    print(f"\nIf you get Qt plugin errors, please install: {install_cmd}\n", file=sys.stderr)
        
        super().__init__(argv if argv is not None else sys.argv)

def log_gui_exception(operation_name: str, exception: Exception):
    """Helper function to consistently log GUI exceptions with context"""
    sg_logger.log(f"GUI Error in {operation_name}: {str(exception)}", level=sg_logger.ERROR)
    # Also log traceback for debugging
    sg_logger.log(f"Traceback for {operation_name}:\n{traceback.format_exc()}", level=sg_logger.DEBUG)

# pan around the objects with the right mouse button. Do not use the left mouse button

class OrbitTransformController(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self._target = None
        self._matrix = QMatrix4x4()
        self._radius = 1
        self._angle = 0

    def setTarget(self, t):
        self._target = t

    def getTarget(self):
        return self._target

    def setRadius(self, radius):
        if self._radius != radius:
            self._radius = radius
            self.updateMatrix()
            self.radiusChanged.emit()

    def getRadius(self):
        return self._radius

    def setAngle(self, angle):
        if self._angle != angle:
            self._angle = angle
            self.updateMatrix()
            self.angleChanged.emit()

    def getAngle(self):
        return self._angle

    def updateMatrix(self):
        self._matrix.setToIdentity()
        self._matrix.rotate(self._angle, QVector3D(0, 1, 0))
        self._matrix.translate(self._radius, 0, 0)
        if self._target is not None:
            self._target.setMatrix(self._matrix)

    angleChanged = Signal()
    radiusChanged = Signal()
    angle = Property(float, getAngle, setAngle, notify=angleChanged)
    radius = Property(float, getRadius, setRadius, notify=radiusChanged)



def to_qvector3d(value) -> QVector3D:
    if isinstance(value, QVector3D):
        return value
    elif isinstance(value, (tuple, list)) and len(value) == 3:
        return QVector3D(*value)
    elif isinstance(value, np.ndarray) and value.shape == (3,):
        return QVector3D(*value.tolist())
    else:
        raise TypeError(f"Expected QVector3D, tuple, or list of 3 elements, got {type(value).__name__}: {value}")

# Currently this can only display one hand, since linkages = basically an array of fingers.
# Maybe that should be split in hands
class OrientationPoint:
    def __init__(self, parent_entity, position, radius: float, material):
        self.entity = Qt3DCore.QEntity(parent_entity)
        
        # Create mesh
        try:
            self.mesh = Qt3DExtras.QSphereMesh()
            self.mesh.setRadius(radius)
        except Exception as e:
            log_gui_exception("OrientationPoint mesh creation", e)

        # Create transform
        self.transform :  Qt3DCore.QTransform = Qt3DCore.QTransform()
        
        # Add components in the same order as LinkObject
        try:
            self.entity.addComponent(self.mesh)
            self.entity.addComponent(material)
            self.entity.addComponent(self.transform)
        except Exception as e:
            sg_logger.warn("  Component addition failed:" + repr(e))
        
        # Set initial position
        self.set_position(position)
    
    def set_position(self, position):
        try:
            if hasattr(position, 'tolist'):
                pos_list = position.tolist()
            else:
                pos_list = position
            self.transform.setTranslation(QVector3D(pos_list[0], pos_list[1], pos_list[2]))
            self.transform.setTranslation(QVector3D(pos_list[0], pos_list[1], pos_list[2]))
        except Exception as e:
            sg_logger.warn("  Position update failed:" + repr(e))



class Fingertip:
    def __init__(self, parent_entity, position, radius: float, material):
        # Create separate entities for sphere and cylinder
        self.sphere_entity = Qt3DCore.QEntity(parent_entity)
        self.cylinder_entity = Qt3DCore.QEntity(parent_entity)
        
        # Create meshes
        try:
            self.sphere_mesh = Qt3DExtras.QSphereMesh()
            self.sphere_mesh.setRadius(radius)
            self.cylinder_mesh = Qt3DExtras.QCylinderMesh()
            self.cylinder_mesh.setRadius(radius)  # Thinner cylinder
            self.cylinder_mesh.setLength(30)
        except Exception as e:
            sg_logger.warn("  Mesh creation failed:" + repr(e))

        # Create separate transforms
        self.sphere_transform = Qt3DCore.QTransform()
        self.cylinder_transform = Qt3DCore.QTransform()
        
        # Add components to sphere entity
        try:
            self.sphere_entity.addComponent(self.sphere_mesh)
            self.sphere_entity.addComponent(material)
            self.sphere_entity.addComponent(self.sphere_transform)
        except Exception as e:
            sg_logger.warn("  Sphere component addition failed:" + repr(e))
            
        # Add components to cylinder entity
        try:
            self.cylinder_entity.addComponent(self.cylinder_mesh)
            self.cylinder_entity.addComponent(material)
            self.cylinder_entity.addComponent(self.cylinder_transform)
        except Exception as e:
            sg_logger.warn("  Cylinder component addition failed:" + repr(e))
        
        # Set initial position
        self.set_position(position)
    
    def set_position(self, position):
        try:
            pos_list = position.tolist()
            self.sphere_transform.setTranslation(QVector3D(pos_list[0], pos_list[1], pos_list[2]))
        except Exception as e:
            sg_logger.warn("  Position update failed:" + repr(e))

    def set_rotation(self, rotation):
        try:
            # Convert numpy array to QQuaternion if needed
            if hasattr(rotation, 'tolist'):
                # It's a numpy array [w, x, y, z]
                rot_list = rotation.tolist()
                quat_rotation = QQuaternion(rot_list[0], rot_list[1], rot_list[2], rot_list[3])
            elif isinstance(rotation, QQuaternion):
                quat_rotation = rotation
            else:
                raise TypeError(f"Unsupported rotation type: {type(rotation)}")
            
            self.sphere_transform.setRotation(quat_rotation)
        except Exception as e:
            sg_logger.warn("  Rotation update failed:" + repr(e))

    def set_radius(self, radius):
        try:
            self.sphere_mesh.setRadius(radius)
            self.cylinder_mesh.setRadius(radius)
        except Exception as e:
            sg_logger.warn("  Radius update failed:" + repr(e))
    
    def set_cylinder_length(self, cylinder_length):
        try:
            self.cylinder_mesh.setLength(cylinder_length)
        except Exception as e:
            sg_logger.warn("  Cylinder length update failed:" + repr(e))
    
    def set_cylinder_pos_rot(self, cylinder_center_pos: QVector3D, rotation: QQuaternion):
        try:
            self.cylinder_transform.setTranslation(to_qvector3d(cylinder_center_pos))
            
            # Convert numpy array to QQuaternion if needed
            if hasattr(rotation, 'tolist'):
                # It's a numpy array [w, x, y, z]
                rot_list = rotation.tolist()
                quat_rotation = QQuaternion(rot_list[0], rot_list[1], rot_list[2], rot_list[3])
            else:
                quat_rotation = rotation
            
            
            # Qt3D cylinders are oriented along Y-axis by default
            # First rotate 90° around Z-axis to orient along X-axis, then apply fingertip rotation
            base_rotation = QQuaternion.fromAxisAndAngle(QVector3D(0, 0, 1), 90)
            combined_rotation = quat_rotation * base_rotation
            
            self.cylinder_transform.setRotation(combined_rotation)
            
        except Exception as e:
            sg_logger.warn("  Cylinder rotation update failed:" + repr(e))


    def set_cylinder_from_end(self, end_pos: QVector3D, rotation, length=None):
        """
        Position the cylinder so that one end is at end_pos, and it extends along its local X axis (after rotation).
        """
        if length is None:
            length = self.cylinder_mesh.length()

        # Ensure rotation is a QQuaternion
        if hasattr(rotation, 'tolist'):
            # It's a numpy array [w, x, y, z]
            rot_list = rotation.tolist()
            quat_rotation = QQuaternion(rot_list[0], rot_list[1], rot_list[2], rot_list[3])
        elif isinstance(rotation, QQuaternion):
            quat_rotation = rotation
        else:
            raise TypeError(f"Unsupported rotation type: {type(rotation)}")

        # Step 1: Local offset
        local_offset = QVector3D(-length / 2, 0, 0)
        # Step 2: Rotate offset by rotation
        rotated_offset = quat_rotation.rotatedVector(local_offset)
        # Step 3: Compute center position
        center_pos = QVector3D(*end_pos) + rotated_offset

        # Orient cylinder along X: rotate 90° around Z, then apply desired rotation
        base_rotation = QQuaternion.fromAxisAndAngle(QVector3D(0, 0, 1), 90)
        combined_rotation = quat_rotation * base_rotation
        self.cylinder_mesh.setLength(length)
        self.cylinder_transform.setTranslation(center_pos)
        self.cylinder_transform.setRotation(combined_rotation)


class LinkObject:
    def __init__(self, parent_entity, start : tuple[float, float, float], end: tuple[float, float, float], thickness: float, material):
        self.entity = Qt3DCore.QEntity(parent_entity)
        self.start = to_qvector3d(start)
        self.end = to_qvector3d(end)

        # Geometry
        try:
            self.mesh = Qt3DExtras.QCuboidMesh()
            self.mesh.setXExtent(thickness)
            self.mesh.setYExtent((self.end - self.start).length())
            self.mesh.setZExtent(thickness)
            #print("  Mesh created.")
        except Exception as e:
            print("  Mesh creation failed:", e)

        self.transform = Qt3DCore.QTransform()
        # set position
        self.set_position(self.start, self.end)
       

        # Add components
        try:
          
            self.entity.addComponent(self.mesh)
            self.entity.addComponent(material)
            self.entity.addComponent(self.transform)
            #print("  Components added.")
        except Exception as e:
            print("  Component addition failed:", e)
    
    def set_position(self, start, end):


        self.start = to_qvector3d(start)
        self.end = to_qvector3d(end)
         # Transform
        try:
            center = (self.start + self.end) * 0.5
            self.transform.setTranslation(center)

            up = QVector3D(0, 1, 0)
            direction = self.end - self.start
            direction.normalize()
            axis = QVector3D.crossProduct(up, direction)
            angle = np.degrees(np.arccos(QVector3D.dotProduct(up, direction)))
            if axis.lengthSquared() > 0.001:
                self.transform.setRotation(QQuaternion.fromAxisAndAngle(axis.normalized(), angle))
            #print("  Transform created.")
        except Exception as e:
            sg_logger.warn("  Transform creation failed:"  + repr(e))

        
class LinkageSystem:
    def __init__(self, parent_entity, joint_poss_world : list[QVector3D], thickness : float, material):
        self.parent_entity = parent_entity
        self.linkages = []  # Store link objects
        
        for index in range(1, len(joint_poss_world)):
            # Create link objects and store them
            start = joint_poss_world[index - 1]
            end = joint_poss_world[index]
            # print("link start: ", start, " end: ", end)
            link = LinkObject(self.parent_entity, start, end, thickness, material)
            self.linkages.append(link)

    def update_linkages(self, joint_poss_world: list[QVector3D]):
            """
            Updates the positions of existing linkages based on a new list of joint positions.
            """
            if len(joint_poss_world) < 2:
                sg_logger.warn(f"Warning: Not enough joints to form linkages ({len(joint_poss_world)}.")
                return  
            
            # Ensure the number of linkages matches the new joint positions
            # The number of linkages should always be len(joint_poss_world) - 1
            if len(self.linkages) != (len(joint_poss_world) - 1):
                sg_logger.warn(f"Warning: The number of already existing linkages ({len(self.linkages)}) should be one less than the of joints ({len(joint_poss_world)}).")
                return
            
            # Update the position of each linkage
            for index in range(len(self.linkages)):
                joint_poss_world[index]
                start = joint_poss_world[index]
                end = joint_poss_world[index + 1]
                self.linkages[index].set_position(start, end)


class PointLightObject:
    def __init__(self, parent_entity, position : QVector3D, intensity: float, color: QColor = QColor("white")):
        position = to_qvector3d(position)

        # Store as member variables to prevent garbage collection
        self.lightEntity = Qt3DCore.QEntity(parent_entity)
        self.light = Qt3DRender.QPointLight(self.lightEntity)
        self.light.setIntensity(intensity)
        self.light.setColor(color)
        
        self.lightTransform = Qt3DCore.QTransform()
        self.lightTransform.setTranslation(position)
        # No rotation needed for point lights - they emit omnidirectionally
        
        self.lightEntity.addComponent(self.light)
        self.lightEntity.addComponent(self.lightTransform)



def print_list_entities(entity: Qt3DCore.QEntity, depth=0):
    indent = "  " * depth
    print(f"{indent}Entity: {entity}")

    # List components of this entity
    for component in entity.components():
        print(f"{indent}  - Component: {type(component).__name__}")

    # Recurse into child entities
    for child in entity.children():
        if isinstance(child, Qt3DCore.QEntity):
            print_list_entities(child, depth + 1)







class UI_Exo_Display(Qt3DExtras.Qt3DWindow):
    def __init__(self):
        super().__init__()

        self.lines = []  # store this as a member variable
        self.linkages : List[LinkageSystem] = [] # entire finger link system
        self.lights = []
        self.fingertip_points = []  # store fingertip orientation points

        
        self.camera().lens().setPerspectiveProjection(30, 16 / 9, 0.1, 1000) 
        self.camera().setPosition(QVector3D(100, 50, 700))
        self.camera().setViewCenter(QVector3D(100, 50, 0))

        # For camera controls
        self.create_scene()
        self.camController = Qt3DExtras.QOrbitCameraController(self.rootEntity)
        self.camController.setLinearSpeed(50)
        self.camController.setLookSpeed(180)
        self.camController.setCamera(self.camera())

        self.setRootEntity(self.rootEntity)

        self.refresh_rate = 60 #fps

        self._gui_update_timer = QTimer()
        self._gui_update_timer.timeout.connect(self._update_display)
        self._gui_update_timer.start(1000 // self.refresh_rate ) 

        self.exo_poss = None
        self.fingertip_point_poss = None
        self.thimble_dims = None

    def create_loop_cb(self, ms_between_frames, cb : Callable[[], None]):
        """
        This allows your program to run a main loop. Running while(true) will block the GUI from updating, so instead use this function to tick your main loop.
        """
        self.timer = QTimer(self)
        self.timer.timeout.connect(cb)
        self.timer.start(ms_between_frames)


        

    def create_line(self, start, end, thickness: float, material):
        """
        Draw multiple links by providing a list of (start, end) positions.
        """
        link = LinkObject(self.rootEntity, start, end, thickness, material)
        self.lines.append(link)
    
    def create_linkages(self, joint_poss_world: list[QVector3D], thickness: float, material = None):
        """
        Create a linkage line drawing links from point to point. 
        Returns the linkage system in which positions can be updated. Do not recreate linkages each frame.
        Setting material to None will use the default linkage material.
        """
        if material == None:
            material = self.material_link
        linkage_system = LinkageSystem(self.rootEntity, joint_poss_world, thickness, material)
        self.linkages.append(linkage_system)
        return linkage_system
    
    def create_fingertips(self, positions: list[QVector3D], rotations: list[QQuaternion], radius: float, material = None):
        """
        Creates a fingertip object for each position. This is approximately the dimensions of the thimble.
        """
        # Clear any existing fingertip points
        self.fingertip_thimbles : List[Fingertip] = []
        
        if material is None:
            material = self.material_thimble
        
        for pos in positions:
            point = Fingertip(self.rootEntity, pos, radius, material)
            self.fingertip_thimbles.append(point)
        
    
    def create_fingertip_points(self, positions: list[QVector3D], radius: float, material = None):
        """
        Creates small balls indicating the fingertip position returned by the SG_API.
        """
        # Clear any existing fingertip points
        self.fingertip_points = []
        
        if material is None:
            material = self.material_fingertip_point
        
        for pos in positions:
            point = OrientationPoint(self.rootEntity, pos, radius, material)
            self.fingertip_points.append(point)


    def create_point_lights(self, positions: list[QVector3D], intensity: float, color: QColor = QColor("white")):
        for pos in positions:
            pos = np.array(pos)
            light = PointLightObject(self.rootEntity, pos, intensity, color)
            self.lights.append(light)
            self.create_line(pos, pos + np.array([1, 1, 1]), 3, self.material_light_visualizer)

    def nr_fingers(self):
        return len(self.linkages)

    def create_hand_exo(self, initial_exo_poss, draw_thimbles = False):
        for finger in initial_exo_poss:
            self.create_linkages(finger, 5)
        # Get the last position from each finger's position array
        last_positions = [pos[-1] for pos in initial_exo_poss]
        self.draw_thimbles = draw_thimbles
        if draw_thimbles:
            self.create_fingertips(last_positions, [QQuaternion.fromAxisAndAngle(QVector3D(1, 0, 0), 0)] * len(last_positions), 11)
        self.create_fingertip_points(last_positions, 3)

    
    def update_hand_exo(self, exo_poss):
        self.exo_poss = exo_poss

    def set_fingertip_points(self, fingertip_poss, fingertip_rots):
        self.fingertip_point_poss = fingertip_poss
        self.fingertip_point_rots = fingertip_rots

    
    
    def set_fingertip_thimbles(self, thimble_dims : List[SG_T.Thimble_dims] ):
        if self.draw_thimbles:
           self.thimble_dims = thimble_dims

    def _update_display(self):
        try:
            if self.exo_poss:
                self._update_exo_display(self.exo_poss)
            if self.fingertip_point_poss:
                self._update_fingertips(self.fingertip_point_poss)
            if self.thimble_dims and self.draw_thimbles:
                self._update_fingertip_thimbles(self.thimble_dims)
        except Exception as e:
            log_gui_exception("_update_display", e)

    def _update_exo_display(self, exo_poss):
        for finger_nr in range(0, self.nr_fingers()):
            self.linkages[finger_nr].update_linkages(exo_poss[finger_nr])

    def _update_fingertips(self, fingertip_poss):
        for i, pos in enumerate(fingertip_poss):
            self.fingertip_points[i].set_position(pos) # position


    def _update_fingertip_thimbles(self, thimble_dims : List[SG_T.Thimble_dims]):
        if self.draw_thimbles:
            for i, thimble in enumerate(thimble_dims):
                if i < len(self.fingertip_thimbles):
                    self.fingertip_thimbles[i].set_position(thimble.sphere_center_pos)
                    self.fingertip_thimbles[i].set_rotation(thimble.rot)
                    self.fingertip_thimbles[i].set_radius(thimble.radius)
                    self.fingertip_thimbles[i].set_cylinder_from_end(thimble.sphere_center_pos, thimble.rot)
                    self.fingertip_thimbles[i].set_cylinder_length(thimble.cylinder_length)



    def disable_default_lighting(self):
        """
        Disable Qt3D's default lighting completely
        """
        # Set background to black
        self.defaultFrameGraph().setClearColor(QColor(10, 10, 30))
        
        # Create a black directional light to override the default white one
        self.override_light_entity = Qt3DCore.QEntity(self.rootEntity)
        self.override_light = Qt3DRender.QDirectionalLight(self.override_light_entity)
        self.override_light.setColor(QColor(0, 0, 0))  # Black light
        self.override_light.setIntensity(0.0)  # No intensity
        self.override_light.setWorldDirection(QVector3D(0, -1, 0))  # Point downward
        
        self.override_light_entity.addComponent(self.override_light)

    def create_scene(self):
        # Root entity
        self.rootEntity = Qt3DCore.QEntity()

        # Disable default lighting by creating a completely dark environment
        self.disable_default_lighting()

        # Material
        self.material_x = Qt3DExtras.QPhongMaterial(self.rootEntity)
        self.material_x.setDiffuse(QColor("red"))
        self.material_x.setSpecular(QColor("white"))
        self.material_x.setShininess(1)
        self.material_x.setAmbient(QColor(255,255,255))

        self.material_y = Qt3DExtras.QPhongMaterial(self.rootEntity)
        self.material_y.setDiffuse(QColor("green"))
        self.material_y.setSpecular(QColor("white"))
        self.material_y.setShininess(1)
        self.material_y.setAmbient(QColor(255,255,255))

        self.material_z = Qt3DExtras.QPhongMaterial(self.rootEntity)
        self.material_z.setDiffuse(QColor("blue"))
        self.material_z.setSpecular(QColor("white"))
        self.material_z.setShininess(1)
        self.material_z.setAmbient(QColor(255,255,255))



        # make_material_always_on_top(self.material_x)
        # make_material_always_on_top(self.material_y)
        # make_material_always_on_top(self.material_z)

        self.material_link = Qt3DExtras.QPhongMaterial(self.rootEntity)
        self.material_link.setDiffuse(QColor("white"))
        self.material_link.setSpecular(QColor("white"))
        self.material_link.setShininess(0.2)
        self.material_link.setAmbient(QColor(0, 0, 0))  # Low ambient to see directional lighting


        self.material_thimble = Qt3DExtras.QPhongMaterial(self.rootEntity)
        self.material_thimble.setDiffuse(QColor(220, 120, 30))
        self.material_thimble.setSpecular(QColor(20, 20, 20)) 
        self.material_thimble.setShininess(1)  
        self.material_thimble.setAmbient(QColor(150, 50, 0)) 

        self.material_fingertip_point = Qt3DExtras.QPhongMaterial(self.rootEntity)
        self.material_fingertip_point.setDiffuse(QColor("blue"))
        self.material_fingertip_point.setSpecular(QColor("white"))
        self.material_fingertip_point.setShininess(0.5)
        self.material_fingertip_point.setAmbient(QColor(0, 0, 0))  # Low ambient to see directional lighting


        #self.material_link.setAmbient(QColor(200,200,200))

        self.material_light_visualizer = Qt3DExtras.QPhongMaterial(self.rootEntity)
        self.material_light_visualizer.setDiffuse(QColor("orange"))
        self.material_light_visualizer.setSpecular(QColor("orange"))
        self.material_light_visualizer.setShininess(1) 
        self.material_light_visualizer.setAmbient(QColor(255,255,0))


        # render axis always on top
        
        
        # Torus
        # self.torusEntity = Qt3DCore.QEntity(self.rootEntity)
        # self.torusMesh = Qt3DExtras.QTorusMesh()
        # self.torusMesh.setRadius(5)
        # self.torusMesh.setMinorRadius(1)
        # self.torusMesh.setRings(100)
        # self.torusMesh.setSlices(20)

        # self.torusTransform = Qt3DCore.QTransform()
        # self.torusTransform.setScale3D(QVector3D(1.5, 1, 0.5))
        # self.torusTransform.setRotation(QQuaternion.fromAxisAndAngle(QVector3D(1, 0, 0), 45))

        # self.torusEntity.addComponent(self.torusMesh)
        # self.torusEntity.addComponent(self.torusTransform)
        # self.torusEntity.addComponent(self.material_link)

        # box
        # self.boxEntity = Qt3DCore.QEntity(self.rootEntity)
        # self.boxMesh = Qt3DExtras.QCuboidMesh()
        # self.boxMesh.setXExtent(3)
        # self.boxMesh.setYExtent(5)
        # self.boxMesh.setZExtent(7)

        # self.boxTransform = Qt3DCore.QTransform() #might be nice to rotate the light
        # self.controller = OrbitTransformController(self.boxTransform)
        # self.controller.setTarget(self.boxTransform)
        # self.controller.setRadius(20)

        # self.boxRotateTransformAnimation = QPropertyAnimation(self.boxTransform)
        # self.boxRotateTransformAnimation.setTargetObject(self.controller)
        # self.boxRotateTransformAnimation.setPropertyName(b"angle")
        # self.boxRotateTransformAnimation.setStartValue(0)
        # self.boxRotateTransformAnimation.setEndValue(360)
        # self.boxRotateTransformAnimation.setDuration(10000)
        # self.boxRotateTransformAnimation.setLoopCount(-1)
        # self.boxRotateTransformAnimation.start()

        # self.boxEntity.addComponent(self.boxMesh)
        # self.boxEntity.addComponent(self.boxTransform)
        # self.boxEntity.addComponent(self.material_link)

        #self.create_point_lights([QVector3D(20, 20, 40), QVector3D(-20, -20, 40), QVector3D(0, -30, 40), QVector3D(0, 0, 50)], 0.2)
        self.create_point_lights([(10, 10, 100)], 0.1) # fill light top
        self.create_point_lights([(10, 10, -100)], 0.1) # fill light bottom
        self.create_point_lights([(300, -80, 100)], 0.1) # back light
        self.create_point_lights([(10, 400, 100)], 0.3)  #key light
        self.create_point_lights([(500, 0, 100)], 0.3)  #fill light fingertips

        # create axes
        self.create_line((0, 0, 0), (10, 0, 0), 1, self.material_x)
        self.create_line((0, 0, 0), (0, 10, 0), 1, self.material_y)
        self.create_line((0, 0, 0), (0, 0, 10), 1, self.material_z)


        #print_list_entities(self.rootEntity, 3)



# Import percentage bent GUI for easy access
from .SG_percentage_bent_gui import PercentageBentGUI


class UI_Exo_Display_With_PercentageBent(QWidget):
    """
    Combined window showing 3D exoskeleton view and percentage bent display side by side.
    
    Usage:
        combined_gui = GUI.UI_Exo_Display_With_PercentageBent()
        combined_gui.show()
        
        # Access the 3D view: combined_gui.exo_display
        # Access the percentage bent GUI: combined_gui.perc_bent_gui
    """
    
    def __init__(self, window_width=1200, window_height=800):
        super().__init__()
        
        self.setWindowTitle("Rembrandt Glove Display")
        
        # Create main layout
        main_layout = QHBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create 3D exoskeleton display
        self.exo_display = UI_Exo_Display()
        exo_container = QWidget.createWindowContainer(self.exo_display)
        main_layout.addWidget(exo_container, 5)  # 3D view gets 75% of space
        
        # Create percentage bent display
        self.perc_bent_gui = PercentageBentGUI()
        self.perc_bent_gui.setMaximumWidth(500)
        main_layout.addWidget(self.perc_bent_gui, 1)  # Percentage bent gets 25%
        
        self.setLayout(main_layout)
        self.setGeometry(100, 100, window_width, window_height)
    
    # Forward common methods to the 3D display for convenience
    def create_hand_exo(self, exo_poss):
        return self.exo_display.create_hand_exo(exo_poss)
    
    def update_hand_exo(self, exo_poss):
        return self.exo_display.update_hand_exo(exo_poss)
    
    def set_fingertip_points(self, fingertips_poss, fingertips_rots):
        return self.exo_display.set_fingertip_points(fingertips_poss, fingertips_rots)
    
    def set_fingertip_thimbles(self, thimble_dims):
        return self.exo_display.set_fingertip_thimbles(thimble_dims)
    
    def update_percentage_bent(self, flexion, abduction):
        """Update the percentage bent display"""
        return self.perc_bent_gui.update(flexion, abduction)


class DualHandGUI(QWidget):
    """
    Dual hand display showing two gloves side by side, each with 3D view and percentage bent display.
    
    Usage:
        dual_gui = GUI.DualHandGUI()
        dual_gui.show()
        
        # Access left hand: dual_gui.left_gui, dual_gui.left_perc_bent
        # Access right hand: dual_gui.right_gui, dual_gui.right_perc_bent
    """
    
    def __init__(self, window_width=1920, window_height=600):
        super().__init__()
        self.setWindowTitle("Dual Hand Rembrandt Display")
        self.setGeometry(0, 0, window_width, window_height)
        
        # Create horizontal layout
        layout = QHBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # ===== LEFT HAND SECTION =====
        # Create 3D display for left hand
        self.left_gui = UI_Exo_Display()
        self.left_container = QWidget.createWindowContainer(self.left_gui)
        layout.addWidget(self.left_container, 2)
        
        # Create percentage bent display for left hand
        self.left_perc_bent = PercentageBentGUI()
        self.left_perc_bent.setMaximumWidth(400)
        layout.addWidget(self.left_perc_bent, 1)
        
        # ===== RIGHT HAND SECTION =====
        # Create 3D display for right hand
        self.right_gui = UI_Exo_Display()
        self.right_container = QWidget.createWindowContainer(self.right_gui)
        layout.addWidget(self.right_container, 2)
        
        # Create percentage bent display for right hand
        self.right_perc_bent = PercentageBentGUI()
        self.right_perc_bent.setMaximumWidth(400)
        layout.addWidget(self.right_perc_bent, 1)
        
        self.setLayout(layout)


if __name__ == '__main__':
    app = QGuiApplication(sys.argv)
    view = UI_Exo_Display()
    view.show()
    sys.exit(app.exec())
    
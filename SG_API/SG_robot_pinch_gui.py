"""
Robot Hand Mapping GUI that has the orange bars below the usual percentage bent bars that show the remapping of the percentage bent values to the robot hand.

For use see examples/robot_hand_mapper_pbent.py.

Questions? Written by:
- Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api/robot_hand_mapper/
Support: https://www.senseglove.com/support/
"""
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFileDialog

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFrame, QPushButton, QLineEdit, QGridLayout, QSizePolicy
)
from SG_API.SG_logger import sg_logger

import json
import os

# Qt signal helper to connect device loop to GUI thread
class DataUpdateSignaler(QObject):
    update_display = Signal(list, list, list, list, dict)

class PinchMapperGUI(QWidget):
    def __init__(self, mapper):
        super().__init__()
        self.mapper = mapper
        self.mapper.register_gui(self)

        self.data_signaler = DataUpdateSignaler()
        self.data_signaler.update_display.connect(self.update_values)        

        self.confirm_labels = {}
        self.setWindowTitle("Robot Hand Pinch Mapper GUI")
        self.resize(560, 740)

        main = QVBoxLayout()
        main.setSpacing(5)
        main.setAlignment(Qt.AlignTop)

        # Title
        title = QLabel("Robot Hand Pinch Mapping")
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        main.addWidget(title)

        # Thumb section
        thumb_frame = QFrame()
        thumb_frame.setFrameStyle(QFrame.Box)
        thumb_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        thumb_layout = QVBoxLayout()
        thumb_layout.setSpacing(4)
        thumb_layout.setContentsMargins(8, 6, 8, 6)

        # Thumb title
        thumb_label = QLabel("Thumb")
        thumb_label.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setBold(True)
        thumb_label.setFont(f)
        thumb_layout.addWidget(thumb_label)

        def make_bar(color):
            bar = QProgressBar()
            bar.setMaximum(10000)
            bar.setFixedHeight(14)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid grey;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 2px;
                }}
            """)
            return bar

        # Header row with Flex/Abd labels
        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 0)
        header_row.setSpacing(6)
        header_spacer = QLabel("")
        header_spacer.setMinimumWidth(55)
        header_row.addWidget(header_spacer)
        flex_header = QLabel("Flex")
        flex_header.setAlignment(Qt.AlignCenter)
        flex_header.setStyleSheet("font-size:9pt;")
        header_row.addWidget(flex_header, 1)
        abd_header = QLabel("Abd")
        abd_header.setAlignment(Qt.AlignCenter)
        abd_header.setStyleSheet("font-size:9pt;")
        header_row.addWidget(abd_header, 1)
        thumb_layout.addLayout(header_row)

        def make_thumb_row(label, flex_color, abd_color):
            h = QHBoxLayout()
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(6)
            
            # Row label
            lbl = QLabel(label)
            lbl.setMinimumWidth(55)
            h.addWidget(lbl)
            
            # Flex section (bar + value)
            flex_layout = QVBoxLayout()
            flex_layout.setSpacing(1)
            flex_bar = make_bar(flex_color)
            flex_val = QLabel("0")
            flex_val.setAlignment(Qt.AlignCenter)
            flex_val.setFixedWidth(36)
            flex_layout.addWidget(flex_bar)
            flex_layout.addWidget(flex_val)
            h.addLayout(flex_layout, 1)
            
            # Abd section (bar + value)
            abd_layout = QVBoxLayout()
            abd_layout.setSpacing(1)
            abd_bar = make_bar(abd_color)
            abd_val = QLabel("0")
            abd_val.setAlignment(Qt.AlignCenter)
            abd_val.setFixedWidth(36)
            abd_layout.addWidget(abd_bar)
            abd_layout.addWidget(abd_val)
            h.addLayout(abd_layout, 1)
            
            return h, flex_bar, flex_val, abd_bar, abd_val

        # Normal row
        normal_row, thumb_nflex_bar, thumb_nflex_val, thumb_nabd_bar, thumb_nabd_val = \
            make_thumb_row("Normal:", "#4CAF50", "#2196F3")
        thumb_layout.addLayout(normal_row)
        
        # Robot row
        robot_row, thumb_rflex_bar, thumb_rflex_val, thumb_rabd_bar, thumb_rabd_val = \
            make_thumb_row("Robot:", "#FF9800", "#9C27B0")
        thumb_layout.addLayout(robot_row)

        thumb_frame.setLayout(thumb_layout)
        main.addWidget(thumb_frame)

        # Reference
        self.thumb_bars = (thumb_nflex_bar, thumb_rflex_bar, thumb_nflex_val,
                        thumb_rflex_val, thumb_nabd_bar, thumb_rabd_bar,
                        thumb_nabd_val, thumb_rabd_val)

        # Finger blocks stacked vertically
        self.blocks = []
        finger_names = ["Index", "Middle", "Ring", "Pinky"]
        for idx, name in enumerate(finger_names, start=1):
            block = self._make_finger_block(name, idx)
            main.addWidget(block)
            self.blocks.append(block)

        # Pinch Parameters
        main.addWidget(self._make_param_frame())

        # Pinch Mode Info
        self.status = QLabel("Pinch Mode: Inactive")
        self.status.setAlignment(Qt.AlignCenter)
        fs = QFont()
        fs.setBold(True)
        self.status.setFont(fs)
        main.addWidget(self.status)

        self.details = QLabel("Distance: -- mm | Influence: 0.00 | Blend: 0.000")
        self.details.setAlignment(Qt.AlignCenter)
        main.addWidget(self.details)

        # Save Config
        save_frame = QFrame()
        save_frame.setFrameStyle(QFrame.Box)
        h = QHBoxLayout()
        h.setContentsMargins(10, 6, 10, 6)
        h.setSpacing(8)

        self.save_in = QLineEdit()
        self.save_in.setPlaceholderText("Enter config name")
        self.save_in.setFixedWidth(300)
        self.save_in.setStyleSheet(
            "QLineEdit { background:#f5f5f5; border:1px solid #bdbdbd; border-radius:3px; padding:3px 5px; }"
        )

        btn = QPushButton("Save Config")
        btn.setFixedWidth(120)
        btn.setStyleSheet("""
            QPushButton {
                background:#e0e0e0; border:1px solid #bdbdbd;
                border-radius:5px; padding:3px 8px;
            }
            QPushButton:hover { background:#d6d6d6; }
        """)
        btn.clicked.connect(self._on_save_config)

        self.save_msg = QLabel("")
        h.addWidget(self.save_in)
        h.addWidget(btn)
        h.addWidget(self.save_msg)
        save_frame.setLayout(h)
        main.addWidget(save_frame)
        main.addSpacing(2)

        self.setLayout(main)

    def _make_finger_block(self, name, idx):
        frm = QFrame()
        frm.setFrameStyle(QFrame.Box)
        frm.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout()
        lay.setSpacing(4)
        lay.setContentsMargins(8, 6, 8, 6)

        lbl = QLabel(name)
        lbl.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setBold(True)
        lbl.setFont(f)
        lay.addWidget(lbl)

        def make_bar(color):
            bar = QProgressBar()
            bar.setMaximum(10000)
            bar.setFixedHeight(14)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid grey;
                    border-radius: 3px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 2px;
                }}
            """)
            return bar

        def bar_row(label, color):
            h = QHBoxLayout()
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(6)
            lbl = QLabel(label)
            lbl.setMinimumWidth(55)
            bar = make_bar(color)
            val = QLabel("0")
            val.setFixedWidth(36)
            val.setAlignment(Qt.AlignRight)
            h.addWidget(lbl)
            h.addWidget(bar)
            h.addWidget(val)
            return h, bar, val

        nrow, nbar, nval = bar_row("Normal:", "#4CAF50")
        rrow, rbar, rval = bar_row("Robot:", "#FF9800")
        lay.addLayout(nrow)
        lay.addLayout(rrow)
        lay.addSpacing(6)

        if name != "Thumb":
            # Descriptive label above button
            desc_label = QLabel(f"Press when {name}-Thumb of the Robot hand is Pinched")
            desc_label.setAlignment(Qt.AlignCenter)
            desc_label.setStyleSheet("font-size:9pt; color:#666;")
            
            b = QPushButton(f"Set {name} calibration")
            b.setStyleSheet("""
                QPushButton {
                    background:#e0e0e0; border:1px solid #bdbdbd;
                    border-radius:5px; padding:3px 8px; font-size:10pt;
                }
                QPushButton:hover { background:#d6d6d6; }
            """)
            b.setFixedWidth(190)
            b.clicked.connect(lambda _, fidx=idx: self._on_set_pinch_target(fidx))
            msg = QLabel("")
            msg.setAlignment(Qt.AlignCenter)
            lay.addSpacing(2)
            lay.addWidget(desc_label, alignment=Qt.AlignCenter)
            lay.addWidget(b, alignment=Qt.AlignCenter)
            lay.addSpacing(2)
            lay.addWidget(msg, alignment=Qt.AlignCenter)
            self.confirm_labels[idx] = msg

        frm.setLayout(lay)
        self.__dict__.setdefault("bars", []).append((nbar, rbar, nval, rval))
        return frm

    def _make_param_frame(self):
        f = QFrame()
        f.setFrameStyle(QFrame.Box)
        v = QVBoxLayout()
        v.setSpacing(4)
        v.setContentsMargins(8, 6, 8, 6)
        title = QLabel("Pinch Parameters")
        ft = QFont()
        ft.setBold(True)
        title.setFont(ft)
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        cfg = self.mapper.config
        vals = {
            "Blend Weight": str(round(cfg.blend_weight, 3)),
            "Enter Distance (mm)": str(cfg.distance_thresholds.get("enter_distance", 20)),
            "Exit Distance (mm)": str(cfg.distance_thresholds.get("exit_distance", 30)),
            "Min Distance (mm)": str(cfg.distance_thresholds.get("min_distance", 5)),
            "Max Distance (mm)": str(cfg.distance_thresholds.get("max_distance", 30))
        }

        grid = QGridLayout()
        grid.setVerticalSpacing(4)
        grid.setHorizontalSpacing(10)
        self.inputs = {}

        def make_input(value):
            inp = QLineEdit(value)
            inp.setFixedWidth(80)
            inp.setAlignment(Qt.AlignRight)
            inp.setStyleSheet("QLineEdit { border:1px solid #bdbdbd; border-radius:3px; padding:2px 4px; }")
            return inp

        ent = make_input(vals["Enter Distance (mm)"])
        ext = make_input(vals["Exit Distance (mm)"])
        mnd = make_input(vals["Min Distance (mm)"])
        mxd = make_input(vals["Max Distance (mm)"])
        bld = make_input(vals["Blend Weight"])

        lbl1 = QLabel("Enter Distance (mm):")
        lbl2 = QLabel("Exit Distance (mm):")
        lbl3 = QLabel("Min Distance (mm):")
        lbl4 = QLabel("Max Distance (mm):")
        lbl5 = QLabel("Blend Weight:")

        btn = QPushButton("Set Parameters")
        btn.setFixedWidth(120)
        btn.setStyleSheet("""
            QPushButton {
                background:#e0e0e0; border:1px solid #bdbdbd;
                border-radius:5px; padding:3px 8px;
            }
            QPushButton:hover { background:#d6d6d6; }
        """)
        btn.clicked.connect(self._on_set_parameters)

        self.msg = QLabel("")
        self.msg.setAlignment(Qt.AlignLeft)

        grid.addWidget(lbl1, 0, 0)
        grid.addWidget(ent, 0, 1)
        grid.addWidget(lbl2, 0, 2)
        grid.addWidget(ext, 0, 3)

        grid.addWidget(lbl3, 1, 0)
        grid.addWidget(mnd, 1, 1)
        grid.addWidget(lbl4, 1, 2)
        grid.addWidget(mxd, 1, 3)

        grid.addWidget(lbl5, 2, 0)
        grid.addWidget(bld, 2, 1)
        grid.addWidget(btn, 2, 2)
        grid.addWidget(self.msg, 2, 3)

        self.inputs = {"Enter": ent, "Exit": ext, "Min": mnd, "Max": mxd, "Blend": bld}
        v.addLayout(grid)
        f.setLayout(v)
        return f

    def _on_set_pinch_target(self, idx):
        try:
            flexion, abduction = self.mapper.get_rhm_percentage_bents()
            self.mapper.set_pinch_targets(idx, abduction[0], flexion[0], flexion[idx])
            self.confirm_labels[idx].setText("Updated")
        except Exception:
            self.confirm_labels[idx].setText("Failed")

    def _on_set_parameters(self):
        try:
            enter_distance = float(self.inputs["Enter"].text() or 20)
            exit_distance  = float(self.inputs["Exit"].text() or 30)
            min_distance  = float(self.inputs["Min"].text() or 5)
            max_distance = float(self.inputs["Max"].text() or 30)
            blend_weight = float(self.inputs["Blend"].text() or 0.1)

            self.mapper.set_blend_weight(blend_weight)
            self.mapper.set_distance_thresholds(enter_distance, exit_distance, min_distance, max_distance)
            self.msg.setText("Applied")
        except Exception:
            self.msg.setText("Invalid")

    def _on_save_config(self):
        last_path = os.path.expanduser("~/.sg_pinch_config_paths.json")
        last_directory = None

        # Load previous save directory
        if os.path.exists(last_path):
            try:
                with open(last_path, "r") as f:
                    last_directory = json.load(f).get("last_saved_directory", None)
            except Exception:
                pass

        # Ask user for target directory
        target_directory = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Save Config",
            last_directory or os.getcwd()
        )

        if not target_directory:
            self.save_msg.setText("Save canceled")
            return

        # Store this folder as last used
        try:
            with open(last_path, "w") as f:
                json.dump({"last_saved_directory": target_directory}, f)
        except Exception:
            sg_logger.warn("Could not save last directory preference")

        try:
            name = self.save_in.text().strip()
            if not name:
                self.save_msg.setText("No name provided!")
                return

            self.mapper.save_config(name, target_directory)
            self.save_msg.setText(f"Saved in: {os.path.basename(target_directory)}")
        except Exception as e:
            self.save_msg.setText("Failed")
            sg_logger.warn(f"Save failed: {e}")

    def update_values(self, nf, rf, na, ra, dbg):
        # Update thumb (Flex + Abduction)
        if hasattr(self, "thumb_bars"):
            (
                nflex_b, rflex_b, nflex_v, rflex_v,
                nabd_b, rabd_b, nabd_v, rabd_v
            ) = self.thumb_bars

            # Thumb flex
            nflex_val = int(nf[0])
            rflex_val = int(rf[0])
            nflex_b.setValue(nflex_val)
            rflex_b.setValue(rflex_val)
            nflex_v.setText(str(nflex_val))
            rflex_v.setText(str(rflex_val))

            # Thumb abduction
            nabd_val = int(na[0])
            rabd_val = int(ra[0])
            nabd_b.setValue(nabd_val)
            rabd_b.setValue(rabd_val)
            nabd_v.setText(str(nabd_val))
            rabd_v.setText(str(rabd_val))

        # Update the other fingers (Index -> Pinky)
        for i, (nbar, rbar, nval, rval) in enumerate(self.bars):
            finger_idx = i + 1  # Skip thumb (0), start from index (1)
            if finger_idx < len(nf):
                nval_i = int(nf[finger_idx])
                rval_i = int(rf[finger_idx])
                nbar.setValue(nval_i)
                rbar.setValue(rval_i)
                nval.setText(str(nval_i))
                rval.setText(str(rval_i))

        # Update pinch status + debug info
        act = dbg.get("pinch_mode_active", False)
        self.status.setText("Pinch Mode: ACTIVE" if act else "Pinch Mode: Inactive")
        self.status.setStyleSheet("color:green;" if act else "color:red;")

        self.details.setText(
            f"Distance: {dbg.get('closest_distance', 0):.1f} mm | "
            f"Blend Factor: {dbg.get('blend_factor', 0):.3f} | "
            f"Active Pinch Config: {dbg.get('config_name', 'Default')} "
        )
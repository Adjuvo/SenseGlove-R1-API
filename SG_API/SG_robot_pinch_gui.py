"""
Robot Hand Mapping GUI
Has two modes:
- Glove: live tracking from the glove device, bars only (read-only).
- Manual: per-finger Abd/Flex sliders that you move by hand.

For use see examples/robot_hand_mapper_pbent.py.

Questions? Written by:
- Akshay Radhamohan M
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/robot_hand_mapper/
Support: https://www.senseglove.com/support/
"""
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFileDialog

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QProgressBar,
    QFrame, QPushButton, QLineEdit, QSizePolicy, QGroupBox, QComboBox,
    QSlider, QSpinBox
)
from SG_API.SG_logger import sg_logger

import json
import os
import threading

VALUE_MIN = 0
VALUE_MAX = 10000

BUTTON_STYLE = """
    QPushButton {
        background:#e0e0e0; border:1px solid #bdbdbd;
        border-radius:5px; padding:3px 8px;
    }
    QPushButton:hover { background:#d6d6d6; }
"""

# Qt signal helper to connect device loop to GUI thread
class DataUpdateSignaler(QObject):
    update_display = Signal(list, list, list, list, dict)


class _ManualSlider(QWidget):
    """Slider + spinbox pair (0-10000) used to manually drive a value in Manual mode."""
    valueChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(VALUE_MIN)
        self.slider.setMaximum(VALUE_MAX)
        self.slider.setSingleStep(100)
        self.slider.setPageStep(1000)

        self.spinbox = QSpinBox()
        self.spinbox.setMinimum(VALUE_MIN)
        self.spinbox.setMaximum(VALUE_MAX)
        self.spinbox.setFixedWidth(70)

        self.slider.valueChanged.connect(self.spinbox.setValue)
        self.spinbox.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(self.valueChanged.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spinbox)

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, value: int) -> None:
        self.slider.setValue(value)


class Robot_Pinch_GUI(QWidget):
    def __init__(self, mapper):
        super().__init__()
        self.mapper = mapper
        self.mapper.register_gui(self)

        self.data_signaler = DataUpdateSignaler()
        self.data_signaler.update_display.connect(self.update_values)

        self.mode = "glove"
        self.save_row_msgs = {}
        self.goto_row_msgs = {}
        self.finger_manual_sliders = {}
        self.setWindowTitle("Robot Hand Pinch Mapper GUI")
        self.resize(780, 900)

        main = QVBoxLayout()
        main.setSpacing(9)
        main.setContentsMargins(9, 9, 9, 15)
        main.setAlignment(Qt.AlignTop)

        # Title
        title = QLabel("Robot Hand Pinch Mapping")
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        main.addWidget(title)

        # Mode selector: Glove (live tracking) vs Manual (slider-driven calibration)
        mode_row = QHBoxLayout()
        mode_row.setAlignment(Qt.AlignCenter)
        mode_label = QLabel("Mode:")
        mode_row.addWidget(mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Glove", "glove")
        self.mode_combo.addItem("Manual", "manual")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_combo)
        main.addLayout(mode_row)

        # Reset button: zero out all manual-mode values
        self.reset_container = QWidget()
        reset_layout = QHBoxLayout(self.reset_container)
        reset_layout.setContentsMargins(0, 0, 0, 0)
        reset_layout.setAlignment(Qt.AlignCenter)
        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Reset all manual sliders (thumb + all fingers) back to 0")
        reset_btn.setStyleSheet(BUTTON_STYLE)
        reset_btn.setMinimumWidth(160)
        reset_btn.clicked.connect(self._on_reset_manual)
        reset_layout.addWidget(reset_btn)
        main.addWidget(self.reset_container)

        # Thumb section
        self.thumb_frame = thumb_frame = QGroupBox("Thumb")
        thumb_frame.setStyleSheet("QGroupBox { font-weight: bold; }")
        thumb_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        thumb_layout = QVBoxLayout()
        thumb_layout.setSpacing(2)
        thumb_layout.setContentsMargins(8, 4, 8, 4)

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

        # Header row with Abd/Flex labels (Abduction on the left, Flexion on the right)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 0)
        header_row.setSpacing(6)
        header_spacer = QLabel("")
        header_spacer.setMinimumWidth(55)
        header_row.addWidget(header_spacer)
        abd_header = QLabel("Abd")
        abd_header.setAlignment(Qt.AlignCenter)
        abd_header.setStyleSheet("font-size:9pt;")
        header_row.addWidget(abd_header, 1)
        flex_header = QLabel("Flex")
        flex_header.setAlignment(Qt.AlignCenter)
        flex_header.setStyleSheet("font-size:9pt;")
        header_row.addWidget(flex_header, 1)

        def make_thumb_row(label, flex_color, abd_color):
            h = QHBoxLayout()
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(6)

            # Row label
            lbl = QLabel(label)
            lbl.setMinimumWidth(55)
            h.addWidget(lbl)

            # Abd section (bar + value), shown first (left)
            abd_layout = QHBoxLayout()
            abd_layout.setSpacing(4)
            abd_bar = make_bar(abd_color)
            abd_val = QLabel("0")
            abd_val.setAlignment(Qt.AlignRight)
            abd_val.setFixedWidth(42)
            abd_layout.addWidget(abd_bar)
            abd_layout.addWidget(abd_val)
            h.addLayout(abd_layout, 1)

            # Flex section (bar + value), shown second (right)
            flex_layout = QHBoxLayout()
            flex_layout.setSpacing(4)
            flex_bar = make_bar(flex_color)
            flex_val = QLabel("0")
            flex_val.setAlignment(Qt.AlignRight)
            flex_val.setFixedWidth(42)
            flex_layout.addWidget(flex_bar)
            flex_layout.addWidget(flex_val)
            h.addLayout(flex_layout, 1)

            return h, flex_bar, flex_val, abd_bar, abd_val

        # Normal row
        normal_row, thumb_nflex_bar, thumb_nflex_val, thumb_nabd_bar, thumb_nabd_val = \
            make_thumb_row("Normal:", "#4CAF50", "#2196F3")

        # Robot row
        robot_row, thumb_rflex_bar, thumb_rflex_val, thumb_rabd_bar, thumb_rabd_val = \
            make_thumb_row("Robot:", "#FF9800", "#9C27B0")

        # Bars container: everything shown in Glove mode (read-only)
        self.thumb_bars_container = QWidget()
        thumb_bars_layout = QVBoxLayout()
        thumb_bars_layout.setContentsMargins(0, 0, 0, 0)
        thumb_bars_layout.setSpacing(2)
        thumb_bars_layout.addLayout(header_row)
        thumb_bars_layout.addLayout(normal_row)
        thumb_bars_layout.addLayout(robot_row)
        self.thumb_bars_container.setLayout(thumb_bars_layout)
        thumb_layout.addWidget(self.thumb_bars_container)

        # Manual container: sliders shown in Manual mode. These are the values captured
        # (together with each finger's own sliders) when saving a Pinch Row.
        self.thumb_manual_container = QWidget()
        thumb_manual_layout = QVBoxLayout()
        thumb_manual_layout.setContentsMargins(0, 0, 0, 0)
        thumb_manual_layout.setSpacing(2)

        def manual_row(label):
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(6)
            lbl = QLabel(label)
            lbl.setMinimumWidth(55)
            slider = _ManualSlider()
            h.addWidget(lbl)
            h.addWidget(slider, 1)
            return container, slider

        thumb_abd_container, self.thumb_abd_slider = manual_row("Abd:")
        thumb_flex_container, self.thumb_flex_slider = manual_row("Flex:")
        self.thumb_abd_slider.valueChanged.connect(self._on_manual_slider_changed)
        self.thumb_flex_slider.valueChanged.connect(self._on_manual_slider_changed)
        thumb_manual_layout.addWidget(thumb_abd_container)
        thumb_manual_layout.addWidget(thumb_flex_container)
        self.thumb_manual_container.setLayout(thumb_manual_layout)
        self.thumb_manual_container.setVisible(False)
        thumb_layout.addWidget(self.thumb_manual_container)

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

        self.details = QLabel(
            "Pinch Factor: 0.000 | Thumb Factor: 0.000 | Distance Factor: 0.000\n"
            "Active Finger: -- | Distance: -- mm | Active Pinch Config: --"
        )
        self.details.setAlignment(Qt.AlignCenter)
        self.details.setWordWrap(True)
        main.addWidget(self.details)

        # Save Config (Manual mode only; there's nothing manually-set to save in Glove mode)
        self.save_frame = save_frame = QFrame()
        save_frame.setFrameStyle(QFrame.Box)
        h = QHBoxLayout()
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(8)

        self.save_in = QLineEdit()
        self.save_in.setPlaceholderText("Enter config name")
        self.save_in.setFixedWidth(220)
        self.save_in.setStyleSheet(
            "QLineEdit { background:#f5f5f5; border:1px solid #bdbdbd; border-radius:3px; padding:3px 5px; }"
        )

        btn = QPushButton("Save Config")
        btn.setFixedWidth(120)
        btn.setStyleSheet(BUTTON_STYLE)
        btn.clicked.connect(self._on_save_config)

        self.save_msg = QLabel("")
        h.addStretch(1)
        h.addWidget(self.save_in)
        h.addWidget(btn)
        h.addWidget(self.save_msg, 0, Qt.AlignVCenter)
        h.addStretch(1)
        save_frame.setLayout(h)
        main.addWidget(save_frame)

        self.setLayout(main)
        self._update_mode_visibility()
        self._sync_window_height()
        self.mode_combo.setCurrentIndex(0)  # default to Glove mode

    def showEvent(self, event):
        """
        Re-sync the window height once this widget is actually mapped by the window manager.
        """
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_window_height)

    def _make_finger_block(self, name, idx):
        frm = QGroupBox(name)
        frm.setStyleSheet("QGroupBox { font-weight: bold; }")
        frm.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout()
        lay.setSpacing(2)
        lay.setContentsMargins(8, 4, 8, 4)

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

        # Header row with Abd/Flex labels (matches the Thumb section layout)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 0)
        header_row.setSpacing(6)
        header_spacer = QLabel("")
        header_spacer.setMinimumWidth(55)
        header_row.addWidget(header_spacer)
        abd_header = QLabel("Abd")
        abd_header.setAlignment(Qt.AlignCenter)
        abd_header.setStyleSheet("font-size:9pt;")
        header_row.addWidget(abd_header, 1)
        flex_header = QLabel("Flex")
        flex_header.setAlignment(Qt.AlignCenter)
        flex_header.setStyleSheet("font-size:9pt;")
        header_row.addWidget(flex_header, 1)

        def make_abd_flex_row(label, abd_color, flex_color):
            h = QHBoxLayout()
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(6)

            lbl = QLabel(label)
            lbl.setMinimumWidth(55)
            h.addWidget(lbl)

            abd_layout = QHBoxLayout()
            abd_layout.setSpacing(4)
            abd_bar = make_bar(abd_color)
            abd_val = QLabel("0")
            abd_val.setAlignment(Qt.AlignRight)
            abd_val.setFixedWidth(42)
            abd_layout.addWidget(abd_bar)
            abd_layout.addWidget(abd_val)
            h.addLayout(abd_layout, 1)

            flex_layout = QHBoxLayout()
            flex_layout.setSpacing(4)
            flex_bar = make_bar(flex_color)
            flex_val = QLabel("0")
            flex_val.setAlignment(Qt.AlignRight)
            flex_val.setFixedWidth(42)
            flex_layout.addWidget(flex_bar)
            flex_layout.addWidget(flex_val)
            h.addLayout(flex_layout, 1)

            return h, flex_bar, flex_val, abd_bar, abd_val

        nrow, nbar, nval, nabd_bar, nabd_val = make_abd_flex_row("Normal:", "#2196F3", "#4CAF50")
        rrow, rbar, rval, rabd_bar, rabd_val = make_abd_flex_row("Robot:", "#9C27B0", "#FF9800")

        # Bars container: everything shown in Glove mode (read-only)
        bars_container = QWidget()
        bars_layout = QVBoxLayout()
        bars_layout.setContentsMargins(0, 0, 0, 0)
        bars_layout.setSpacing(2)
        bars_layout.addLayout(header_row)
        bars_layout.addLayout(nrow)
        bars_layout.addLayout(rrow)
        bars_container.setLayout(bars_layout)
        lay.addWidget(bars_container)

        # Manual container: sliders (shown in Manual mode) + Save Pinch Row button.
        # Save Pinch Row additionally captures them into this mapper's live Robot_Pinch_Config.
        manual_container = QWidget()
        manual_layout = QVBoxLayout()
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(2)

        def manual_row(label):
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(6)
            lbl = QLabel(label)
            lbl.setMinimumWidth(55)
            slider = _ManualSlider()
            h.addWidget(lbl)
            h.addWidget(slider, 1)
            return container, slider

        abd_container, abd_slider = manual_row("Abd:")
        flex_container, flex_slider = manual_row("Flex:")
        abd_slider.valueChanged.connect(self._on_manual_slider_changed)
        flex_slider.valueChanged.connect(self._on_manual_slider_changed)
        manual_layout.addWidget(abd_container)
        manual_layout.addWidget(flex_container)
        self.finger_manual_sliders[idx] = (abd_slider, flex_slider)

        # Go To button: loads this finger's configured pinch target
        # (from the currently loaded config) into the sliders
        goto_row = QHBoxLayout()
        goto_row.setSpacing(10)
        goto_row.setAlignment(Qt.AlignCenter)

        goto_pinch_btn = QPushButton(f"Go To {name} Pinch")
        goto_pinch_btn.setToolTip(f"Load {name}'s configured pinch target into the sliders")
        goto_pinch_btn.setStyleSheet(BUTTON_STYLE)
        goto_pinch_btn.setMinimumWidth(200)
        goto_pinch_btn.clicked.connect(lambda _, fidx=idx: self._on_goto_pinch_row(fidx))
        goto_msg = QLabel("")
        goto_msg.setFixedWidth(70)

        goto_row.addWidget(goto_pinch_btn)
        goto_row.addWidget(goto_msg, 0, Qt.AlignVCenter)
        manual_layout.addLayout(goto_row)
        self.goto_row_msgs[idx] = goto_msg

        # Save button: captures the current manual sliders (thumb + this finger)
        # directly into the mapper's Robot_Pinch_Config, no live device reading required.
        save_row = QHBoxLayout()
        save_row.setSpacing(10)
        save_row.setAlignment(Qt.AlignCenter)

        save_pinch_btn = QPushButton(f"Save {name} Pinch Row")
        save_pinch_btn.setToolTip(f"Save the current sliders as {name}'s pinch target")
        save_pinch_btn.setStyleSheet(BUTTON_STYLE)
        save_pinch_btn.setMinimumWidth(200)
        save_pinch_btn.clicked.connect(lambda _, fidx=idx: self._on_save_pinch_row(fidx))
        pinch_msg = QLabel("")
        pinch_msg.setFixedWidth(70)

        save_row.addWidget(save_pinch_btn)
        save_row.addWidget(pinch_msg, 0, Qt.AlignVCenter)
        manual_layout.addLayout(save_row)
        self.save_row_msgs[idx] = pinch_msg

        manual_container.setLayout(manual_layout)
        manual_container.setVisible(False)
        lay.addWidget(manual_container)

        frm.setLayout(lay)
        self.__dict__.setdefault("bars", []).append((nbar, rbar, nval, rval))
        self.__dict__.setdefault("abd_bars", []).append((nabd_bar, rabd_bar, nabd_val, rabd_val))
        self.__dict__.setdefault("bars_containers", []).append(bars_container)
        self.__dict__.setdefault("manual_containers", []).append(manual_container)
        return frm

    def _make_param_frame(self):
        f = QGroupBox("Pinch Parameters")
        f.setStyleSheet("QGroupBox { font-weight: bold; }")
        v = QVBoxLayout()
        v.setSpacing(3)
        v.setContentsMargins(8, 4, 8, 4)

        cfg = self.mapper.config
        vals = {
            "Min Distance (mm)": str(cfg.distance_thresholds.get("min_distance", 5)),
            "Max Distance (mm)": str(cfg.distance_thresholds.get("max_distance", 30)),
            "Weight Thumb": str(cfg.blend_weights.get("thumb", 0.4)),
            "Weight Distance": str(cfg.blend_weights.get("distance", 0.6)),
        }

        def make_input(value):
            inp = QLineEdit(value)
            inp.setFixedWidth(80)
            inp.setAlignment(Qt.AlignRight)
            inp.setStyleSheet("QLineEdit { border:1px solid #bdbdbd; border-radius:3px; padding:2px 4px; }")
            return inp

        mnd = make_input(vals["Min Distance (mm)"])
        mxd = make_input(vals["Max Distance (mm)"])
        wt = make_input(vals["Weight Thumb"])
        wd = make_input(vals["Weight Distance"])

        # 2-column grid: each column's label/input line up across both rows.
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)

        def add_param(row, col, label_text, input_widget):
            lbl = QLabel(label_text)
            grid.addWidget(lbl, row, col * 2)
            grid.addWidget(input_widget, row, col * 2 + 1)

        add_param(0, 0, "Min Distance (mm):", mnd)
        add_param(0, 1, "Max Distance (mm):", mxd)
        add_param(1, 0, "Weight Thumb:", wt)
        add_param(1, 1, "Weight Distance:", wd)

        v.addLayout(grid)

        btn = QPushButton("Set Parameters")
        btn.setFixedWidth(120)
        btn.setStyleSheet(BUTTON_STYLE)
        btn.clicked.connect(self._on_set_parameters)

        self.msg = QLabel("")
        self.msg.setAlignment(Qt.AlignLeft)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(btn)
        btn_row.addWidget(self.msg, 0, Qt.AlignVCenter)
        btn_row.addStretch(1)
        v.addLayout(btn_row)

        self.inputs = {
            "Min": mnd, "Max": mxd,
            "WeightThumb": wt, "WeightDistance": wd,
        }
        f.setLayout(v)
        return f

    def _on_mode_changed(self, _index):
        self.mode = self.mode_combo.currentData()
        self.mapper.set_manual_mode(self.mode == "manual")
        if self.mode == "manual":
            self._on_manual_slider_changed()
        self._update_mode_visibility()
        self._sync_window_height()

    def _on_manual_slider_changed(self, _value=None):
        """Push the current manual sliders (thumb + all fingers) into the mapper"""
        if self.mode != "manual":
            return
        flex = [self.thumb_flex_slider.value()]
        abdn = [self.thumb_abd_slider.value()]
        for idx in (1, 2, 3, 4):
            abd_slider, flex_slider = self.finger_manual_sliders[idx]
            flex.append(flex_slider.value())
            abdn.append(abd_slider.value())
        self.mapper.set_manual_values(flex, abdn)

    def _update_mode_visibility(self):
        """Show live read-only bars in Glove mode, manual sliders + save buttons in Manual mode."""
        is_manual = self.mode == "manual"
        if hasattr(self, "reset_container"):
            self.reset_container.setVisible(is_manual)
        if hasattr(self, "save_frame"):
            self.save_frame.setVisible(is_manual)
        if hasattr(self, "thumb_bars_container"):
            self.thumb_bars_container.setVisible(not is_manual)
        if hasattr(self, "thumb_manual_container"):
            self.thumb_manual_container.setVisible(is_manual)
        for container in getattr(self, "bars_containers", []):
            container.setVisible(not is_manual)
        for container in getattr(self, "manual_containers", []):
            container.setVisible(is_manual)

    def _sync_window_height(self):
        """Resize to fit exactly the currently visible content"""
        containers = (
            list(getattr(self, "bars_containers", []))
            + list(getattr(self, "manual_containers", []))
            + [
                getattr(self, "reset_container", None),
                getattr(self, "save_frame", None),
                getattr(self, "thumb_bars_container", None),
                getattr(self, "thumb_manual_container", None),
            ]
        )
        for container in containers:
            if container is not None:
                container.updateGeometry()
        for block in getattr(self, "blocks", []) + [getattr(self, "thumb_frame", None)]:
            if block is not None:
                block.updateGeometry()

        layout = self.layout()
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        self.resize(self.width(), layout.sizeHint().height())
        layout.activate()

        last_item = None
        for i in range(layout.count() - 1, -1, -1):
            item = layout.itemAt(i)
            widget = item.widget()
            if widget is None or widget.isVisible():
                last_item = item
                break
        if last_item is None:
            last_item = layout.itemAt(layout.count() - 1)

        _, _, _, bottom_margin = layout.getContentsMargins()
        natural_height = last_item.geometry().y() + last_item.geometry().height() + bottom_margin

        self.setFixedHeight(natural_height)

    def _sync_all_manual_sliders_from_mapper(self):
        """
        Reflect the mapper's current manual_flex/manual_abdn (thumb + all fingers) into the sliders.
        """
        m = self.mapper
        updates = [
            (self.thumb_abd_slider, m.manual_abdn[0]),
            (self.thumb_flex_slider, m.manual_flex[0]),
        ]
        for idx in (1, 2, 3, 4):
            abd_slider, flex_slider = self.finger_manual_sliders[idx]
            updates.append((abd_slider, m.manual_abdn[idx]))
            updates.append((flex_slider, m.manual_flex[idx]))
        for slider, value in updates:
            slider.blockSignals(True)
            slider.set_value(int(value))
            slider.blockSignals(False)

    def _on_goto_pinch_row(self, idx):
        try:
            self.mapper.goto_pinch(idx)
            self._sync_all_manual_sliders_from_mapper()
            self.goto_row_msgs[idx].setText("Loaded")
        except Exception as e:
            self.goto_row_msgs[idx].setText("Failed")
            sg_logger.warn(f"Failed to go to pinch for finger {idx}: {e}")

    def _on_reset_manual(self):
        try:
            self.mapper.reset_manual()
            self._sync_all_manual_sliders_from_mapper()
        except Exception as e:
            sg_logger.warn(f"Failed to reset manual values: {e}")

    def _on_save_pinch_row(self, idx):
        try:
            thumb_abd = self.thumb_abd_slider.value()
            thumb_flex = self.thumb_flex_slider.value()
            abd_slider, flex_slider = self.finger_manual_sliders[idx]
            self.mapper.set_pinch_targets(idx, thumb_abd, thumb_flex, flex_slider.value())
            self.save_row_msgs[idx].setText("Saved")
        except Exception as e:
            self.save_row_msgs[idx].setText("Failed")
            sg_logger.warn(f"Failed to save pinch row for finger {idx}: {e}")

    def _on_set_parameters(self):
        try:
            min_distance = float(self.inputs["Min"].text() or 5)
            max_distance = float(self.inputs["Max"].text() or 30)
            weight_thumb = float(self.inputs["WeightThumb"].text() or 0.4)
            weight_distance = float(self.inputs["WeightDistance"].text() or 0.6)

            self.mapper.set_distance_thresholds(min_distance, max_distance)
            self.mapper.set_blend_weights(weight_thumb, weight_distance)
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

        # Update the other fingers' abduction (Index -> Pinky)
        for i, (nabd_bar, rabd_bar, nabd_val, rabd_val) in enumerate(getattr(self, "abd_bars", [])):
            finger_idx = i + 1  # Skip thumb (0), start from index (1)
            if finger_idx < len(na):
                nabd_i = int(na[finger_idx])
                rabd_i = int(ra[finger_idx])
                nabd_bar.setValue(nabd_i)
                rabd_bar.setValue(rabd_i)
                nabd_val.setText(str(nabd_i))
                rabd_val.setText(str(rabd_i))

        # Update pinch status + debug info
        act = dbg.get("pinch_mode_active", False)
        self.status.setText("Pinch Mode: ACTIVE" if act else "Pinch Mode: Inactive")
        self.status.setStyleSheet("color:green;" if act else "color:red;")

        finger_names = {1: "Index", 2: "Middle", 3: "Ring", 4: "Pinky"}
        active_finger = finger_names.get(dbg.get("active_pinch_finger"), "--")

        self.details.setText(
            f"Pinch Factor: {dbg.get('pinch_factor', 0):.3f} | "
            f"Thumb Factor: {dbg.get('thumb_factor', 0):.3f} | "
            f"Distance Factor: {dbg.get('distance_factor', 0):.3f}\n"
            f"Active Finger: {active_finger} | "
            f"Distance: {dbg.get('closest_distance', 0):.1f} mm | "
            f"Active Pinch Config: {dbg.get('config_name', 'Default')} "
        )


class Robot_Pinch_Mapper_GUI:
    """
    Pending-update bridge for Robot_Pinch_GUI.
    Store values from the data callback; apply on the exo display timer (~60 Hz).
    """

    def __init__(self, mapper):
        self._mapper = mapper
        self.widget = Robot_Pinch_GUI(mapper)
        self._pending = None
        self._update_lock = threading.Lock()

    def emit_update(self, raw_flex, raw_abd, blended_flex, blended_abd):
        state = self._mapper.state
        config = self._mapper.config
        debug = {
            "config_name":               config.name,
            "pinch_mode_active":         state.pinch_mode_active,
            "pinch_factor":              state.pinch_factor,
            "thumb_factor":              state.thumb_factor,
            "distance_factor":           state.distance_factor,
            "closest_distance":          state.min_distance,
            "closest_finger":            state.active_pinch_finger,
            "active_pinch_finger":       state.active_pinch_finger,
            "should_pinch":              state.pinch_factor > 0.1,
            "thumb_abduction_threshold": config.thumb_abduction_threshold,
        }
        with self._update_lock:
            self._pending = (raw_flex, blended_flex, raw_abd, blended_abd, debug)

    def apply_pending_update(self):
        with self._update_lock:
            pending = self._pending
        if pending is None:
            return
        try:
            self.widget.update_values(*pending)
        except Exception:
            pass

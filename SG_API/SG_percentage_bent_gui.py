"""
Percentage Bent Display GUI

Simple GUI to display percentage bent values for flexion and abduction.

Questions? Written by:
- Amber Elferink
Docs:    https://senseglove.gitlab.io/rembrandt/rembrandt-api
Support: https://www.senseglove.com/support/
"""
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QFont

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFrame, QSizePolicy
)


class DataUpdateSignaler(QObject):
    """Signal helper for thread-safe GUI updates"""
    update_display = Signal(list, list)  # flexion, abduction


class PercentageBentGUI(QWidget):
    """Simple GUI showing only percentage bent values (no robot mapping)"""
    
    def __init__(self):
        super().__init__()
        
        # Create signaler for thread-safe updates
        self.data_signaler = DataUpdateSignaler()
        self.data_signaler.update_display.connect(self._update_values)
        
        self.setWindowTitle("Percentage Bent Display")
        
        main = QVBoxLayout()
        main.setSpacing(5)
        main.setAlignment(Qt.AlignTop)
        
        # Title
        title = QLabel("Percentage Bent")
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        main.addWidget(title)
        
        # Thumb section with flex and abduction
        thumb_frame = self._make_thumb_block()
        main.addWidget(thumb_frame)
        
        # Other fingers (Index, Middle, Ring, Pinky) - flexion and abduction
        finger_names = ["Index", "Middle", "Ring", "Pinky"]
        self.finger_bars = []  # List of (flex_bar, abd_bar) tuples
        for name in finger_names:
            block = self._make_finger_block(name)
            main.addWidget(block)
        
        self.setLayout(main)
    
    def _make_thumb_block(self):
        """Create thumb display with flexion and abduction"""
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
            bar.setFixedHeight(20)
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
        
        # Header row with Flex/Abd labels
        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 0)
        header_row.setSpacing(6)
        header_row.addWidget(QLabel("Flex"), 1)
        header_row.addWidget(QLabel("Abd"), 1)
        thumb_layout.addLayout(header_row)
        
        # Bars row
        bars_row = QHBoxLayout()
        bars_row.setContentsMargins(2, 0, 2, 0)
        bars_row.setSpacing(6)
        
        self.thumb_flex_bar = make_bar("#4CAF50")
        self.thumb_abd_bar = make_bar("#2196F3")
        
        bars_row.addWidget(self.thumb_flex_bar, 1)
        bars_row.addWidget(self.thumb_abd_bar, 1)
        thumb_layout.addLayout(bars_row)
        
        thumb_frame.setLayout(thumb_layout)
        return thumb_frame
    
    def _make_finger_block(self, name):
        """Create finger display block with flexion and abduction"""
        frm = QFrame()
        frm.setFrameStyle(QFrame.Box)
        frm.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout()
        lay.setSpacing(4)
        lay.setContentsMargins(8, 6, 8, 6)
        
        # Finger name
        lbl = QLabel(name)
        lbl.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setBold(True)
        lbl.setFont(f)
        lay.addWidget(lbl)
        
        def make_bar(color):
            bar = QProgressBar()
            bar.setMaximum(10000)
            bar.setFixedHeight(20)
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
        
        # Header row with Flex/Abd labels
        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 0)
        header_row.setSpacing(6)
        header_row.addWidget(QLabel("Flex"), 1)
        header_row.addWidget(QLabel("Abd"), 1)
        lay.addLayout(header_row)
        
        # Bars row
        bars_row = QHBoxLayout()
        bars_row.setContentsMargins(2, 0, 2, 0)
        bars_row.setSpacing(6)
        
        flex_bar = make_bar("#4CAF50")
        abd_bar = make_bar("#2196F3")
        
        bars_row.addWidget(flex_bar, 1)
        bars_row.addWidget(abd_bar, 1)
        lay.addLayout(bars_row)
        
        frm.setLayout(lay)
        self.finger_bars.append((flex_bar, abd_bar))  # Store as tuple
        return frm
    
    def update(self, flexion, abduction):
        """
        Update the display with new percentage bent values (thread-safe).
        Call this from your data callback with the values from get_percentage_bents()
        
        Args:
            flexion: List of flexion percentage bent values (5 fingers)
            abduction: List of abduction percentage bent values (5 fingers)
        """
        # Emit signal for thread-safe update
        try:
            self.data_signaler.update_display.emit(list(flexion), list(abduction))
        except Exception as e:
            pass # shutting down gives an error due to C++ object already has been deleted from QT. ignore it.
    
    def _update_values(self, flexion, abduction):
        """Internal method that actually updates the GUI (runs in main thread)"""
        # Update thumb
        if len(flexion) > 0:
            thumb_flex_val = int(flexion[0])
            self.thumb_flex_bar.setValue(thumb_flex_val)
            self.thumb_flex_bar.setFormat(f"{thumb_flex_val}")
        
        if len(abduction) > 0:
            thumb_abd_val = int(abduction[0])
            self.thumb_abd_bar.setValue(thumb_abd_val)
            self.thumb_abd_bar.setFormat(f"{thumb_abd_val}")
        
        # Update other fingers (index through pinky)
        for i, (flex_bar, abd_bar) in enumerate(self.finger_bars):
            finger_idx = i + 1  # Skip thumb (0), start from index (1)
            
            # Update flexion
            if finger_idx < len(flexion):
                flex_val = int(flexion[finger_idx])
                flex_bar.setValue(flex_val)
                flex_bar.setFormat(f"{flex_val}")
            
            # Update abduction
            if finger_idx < len(abduction):
                abd_val = int(abduction[finger_idx])
                abd_bar.setValue(abd_val)
                abd_bar.setFormat(f"{abd_val}")


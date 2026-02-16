"""
Simple FPS counter to measure the FPS of the data coming from the glove.
Use like:
```python
    fps_my_label = SG_FPS.FPSCounter(1.0, "my_label")

    while(True):
        fps_my_label.update() #updates internal fps, and every 1.0 seconds prints the my_label FPS 
        time.sleep(0.1)
```

Questions? Written by:
- Amber Elferink
https://www.senseglove.com/support/
"""

import time
from .SG_logger import sg_logger

class FPSCounter:
    def __init__(self, print_interval_secs: float, message: str = "FPS", severity: int = sg_logger.USER_INFO):
        self.frame_count = 0
        self.last_time = time.time()
        self.print_interval = print_interval_secs
        self.message = message
        self.severity = severity
        
    def update(self) -> None:
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.last_time >= self.print_interval:
            fps = self.frame_count / (current_time - self.last_time)
            sg_logger.log(f"{self.message}: {fps:.1f}", level=self.severity)
            self.frame_count = 0
            self.last_time = current_time 
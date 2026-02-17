"""
SG_timer provides cross-platform high-precision timing functionality for the Rembrandt API, so it can call >1000 Hz.
It is used to call the callback for the simulator for example at specific intervals.

This module offers OS-level timer callbacks with minimal overhead:
- Windows: Automatic timer selection based on frequency requirements
  * ≤1000 Hz: Multimedia timer with 1ms resolution
  * >1000 Hz: High-precision sleep + busy-wait with QueryPerformanceCounter (up to ~10kHz)
- Linux: Uses timerfd for OS-level callbacks with minimal overhead
  * Supports microsecond precision limited only by hardware

The high-precision timer uses busy-waiting (constantly checking the clock), which burns CPU cycles even when idle.
For ≤1000 Hz, the multimedia timer uses OS interrupts with near-zero CPU overhead between ticks (but is capped at 1000 Hz). Only when you need >1000 Hz is the busy-wait CPU cost worth it for the extra precision.
At 1000 Hz, multimedia timer = ~0% CPU, high-precision = ~5-10% CPU from spinning.

**Key Functions:**
- `create_timer()`: Create a new high-precision timer
- `start_timer()`: Start the timer with specified frequency  
- `stop_timer()`: Stop the timer
- `subscribe_timer_callback()`: Subscribe to timer events

**Examples:**
```python
import SG_API.SG_timer as Timer

# Create a 1000 Hz timer
timer_id = Timer.create_timer(frequency_hz=1000)

# Subscribe to timer events
def on_timer_tick(timer_id, missed_events):
    print(f"Timer {timer_id} tick, missed: {missed_events}")

Timer.subscribe_timer_callback(timer_id, on_timer_tick)

# Start the timer
Timer.start_timer(timer_id)

# Your main loop here...

# Stop when done
Timer.stop_timer(timer_id)
```

Questions? Written by:
- Amber Elferink
Docs:    https://adjuvo.github.io/SenseGlove-R1-API/
Support: https://www.senseglove.com/support/
"""

import sys
import os
import time
import signal
import threading
import platform
import traceback
from typing import Callable, Optional, Dict, Any, List
import warnings

from SG_API.SG_logger import sg_logger

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Windows-specific imports
if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    
    # Windows multimedia timer
    winmm = ctypes.windll.winmm
    
    # Timer callback function type
    TIMECALLBACK = ctypes.WINFUNCTYPE(None, wintypes.UINT, wintypes.UINT, 
                                      ctypes.POINTER(wintypes.DWORD), 
                                      ctypes.POINTER(wintypes.DWORD), 
                                      ctypes.POINTER(wintypes.DWORD))

# Linux-specific imports  
elif IS_LINUX:
    import select
    import struct
    try:
        import resource
        # Try to set high priority if possible
        resource.setrlimit(resource.RLIMIT_NICE, (20, 20))
    except:
        pass
    
    # Linux timerfd system calls via ctypes
    import ctypes
    libc = ctypes.CDLL("libc.so.6")
    
    # timerfd constants
    TFD_CLOEXEC = 0o2000000
    CLOCK_MONOTONIC = 1
    TFD_TIMER_ABSTIME = 1

# Global timer management
_timers: Dict[int, 'SGTimer'] = {}
_next_timer_id = 1
_timer_lock = threading.Lock()

class SGTimer:
    """Internal timer class - manages platform-specific timer implementation"""
    
    def __init__(self, timer_id: int, frequency_hz: float):
        self.timer_id = timer_id
        self.frequency_hz = frequency_hz
        self.period_ms = 1000.0 / frequency_hz
        self.is_running = False
        self.callback: Optional[Callable[[int, int], None]] = None
        
        # Platform-specific state
        self.platform_timer_id = None  # Windows timer ID
        self.timer_fd = None          # Linux timer fd
        self.timer_thread = None      # Linux timer thread / Windows waitable timer thread
        
    def start(self):
        """Start the timer"""
        if self.is_running:
            sg_logger.warn(f"Timer {self.timer_id} is already running")
            return
            
        self.is_running = True
        
        if IS_WINDOWS:
            self._start_windows_timer()
        elif IS_LINUX:
            self._start_linux_timer()
        else:
            raise Exception(f"Unsupported platform: {platform.system()}")
            
        sg_logger.info(f"Timer {self.timer_id} started at {self.frequency_hz} Hz")
    
    def stop(self):
        """Stop the timer"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        if IS_WINDOWS:
            self._stop_windows_timer()
        elif IS_LINUX:
            self._stop_linux_timer()
            
        sg_logger.info(f"Timer {self.timer_id} stopped")
    
    def set_callback(self, callback: Callable[[int, int], None]):
        """Set the callback function for timer events"""
        self.callback = callback
    
    def _on_timer_event(self, missed_events: int = 0):
        """Internal method called when timer fires"""
        if self.callback and self.is_running:
            self.callback(self.timer_id, missed_events)

        # Windows implementation
    def _start_windows_timer(self):
        """Start Windows timer with high-resolution support for >1000 Hz"""
        
        # For frequencies > 1000 Hz, use high-precision timer with sleep + busy-wait
        if self.frequency_hz > 1000:
            self._start_windows_high_precision_timer()
        else:
            self._start_windows_multimedia_timer()
    
    def _start_windows_multimedia_timer(self):
        """Start Windows multimedia timer (up to 1000 Hz)"""
        def timer_callback(timer_id, msg, user_data, dw1, dw2):
            self._on_timer_event(0)
        
        # Create the timer callback
        self.callback_func = TIMECALLBACK(timer_callback)
        
        # Set timer resolution to 1ms
        winmm.timeBeginPeriod(1)
        
        # Create multimedia timer
        interval_ms = max(1, round(self.period_ms))  # At least 1ms
        self.platform_timer_id = winmm.timeSetEvent(
            interval_ms,        # Interval
            1,                  # Resolution  
            self.callback_func, # Callback function
            None,               # User data
            1                   # TIME_PERIODIC
        )
        
        if self.platform_timer_id == 0:
            raise Exception(f"Failed to create Windows multimedia timer for timer {self.timer_id}")
    
    def _start_windows_high_precision_timer(self):
        """Start Windows high-precision timer using sleep + busy-wait (>1000 Hz)"""
        import threading
        
        # Set high-resolution timer resolution
        try:
            ntdll = ctypes.windll.ntdll
            actual_resolution = wintypes.DWORD()
            result = ntdll.NtSetTimerResolution(5000, True, ctypes.byref(actual_resolution))
            if result == 0:  # NT_SUCCESS
                sg_logger.info(f"Set timer resolution to {actual_resolution.value / 10000.0:.1f}ms")
            else:
                sg_logger.warn("Failed to set high resolution timer")
        except:
            sg_logger.warn("NtSetTimerResolution not available")
        
        # Use a fake timer ID for consistency
        self.platform_timer_id = 12345  # Dummy value
        
        # Start the high-precision timer thread
        self.timer_thread = threading.Thread(target=self._windows_high_precision_timer_loop, daemon=True)
        self.timer_thread.start()
    
    def _windows_high_precision_timer_loop(self):
        """Windows high-precision timer loop using QueryPerformanceCounter + sleep + busy-wait"""
        kernel32 = ctypes.windll.kernel32
        
        # Get performance counter frequency
        freq = wintypes.LARGE_INTEGER()
        kernel32.QueryPerformanceFrequency(ctypes.byref(freq))
        frequency = freq.value
        
        # Calculate target interval in performance counter ticks
        target_interval_ticks = int(frequency * self.period_ms / 1000.0)
        
        # Get initial timestamp
        start_time = wintypes.LARGE_INTEGER()
        kernel32.QueryPerformanceCounter(ctypes.byref(start_time))
        next_time = start_time.value
        

        while self.is_running:
            next_time += target_interval_ticks
            
            # Current time
            current_time = wintypes.LARGE_INTEGER()
            kernel32.QueryPerformanceCounter(ctypes.byref(current_time))
            
            # Time until next event
            time_until_next = next_time - current_time.value
            
            if time_until_next > 0:
                # Convert to milliseconds for Sleep
                sleep_ms = max(0, int((time_until_next * 1000.0 / frequency) - 0.5))  # Sleep until ~0.5ms before target
                
                if sleep_ms > 0:
                    kernel32.Sleep(sleep_ms)
                
                # Busy-wait for the remaining time with high precision
                while self.is_running:
                    kernel32.QueryPerformanceCounter(ctypes.byref(current_time))
                    if current_time.value >= next_time:
                        break
            
            if self.is_running:
                self._on_timer_event(0)

    
    def _stop_windows_timer(self):
        """Stop Windows timer (multimedia or high-precision)"""
        if self.platform_timer_id:
            if self.frequency_hz > 1000:
                # Stop high-precision timer thread
                # Wait for timer thread to finish
                if self.timer_thread:
                    self.timer_thread.join(timeout=1.0)
                    self.timer_thread = None
                
                # Restore timer resolution
                try:
                    ntdll = ctypes.windll.ntdll
                    actual_resolution = wintypes.DWORD()
                    ntdll.NtSetTimerResolution(0, False, ctypes.byref(actual_resolution))
                except:
                    pass
            else:
                # Stop multimedia timer
                winmm.timeKillEvent(self.platform_timer_id)
                winmm.timeEndPeriod(1)
                
            self.platform_timer_id = None
    
    # Linux implementation
    def _start_linux_timer(self):
        """Start Linux timerfd timer"""
        # Create timerfd
        self.timer_fd = libc.timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC)
        if self.timer_fd < 0:
            raise Exception(f"Failed to create timerfd for timer {self.timer_id}")
        
        # Set up periodic timer
        interval_sec = 0
        interval_nsec = int(self.period_ms * 1000000)  # Convert ms to nanoseconds
        value_sec = 0
        value_nsec = interval_nsec  # Initial expiration
        
        # Pack the itimerspec structure for 64-bit Linux
        # itimerspec contains two timespec structs: it_interval, it_value
        # Each timespec: tv_sec (8 bytes), tv_nsec (8 bytes)
        itimerspec = struct.pack("LLLL", 
                               interval_sec, interval_nsec,  # it_interval
                               value_sec, value_nsec)        # it_value
        
        # Set the timer
        result = libc.timerfd_settime(self.timer_fd, 0, itimerspec, None)
        if result < 0:
            import errno
            error_code = ctypes.get_errno()
            raise Exception(f"Failed to set timerfd for timer {self.timer_id}: errno={error_code} ({os.strerror(error_code)})")
        
        # Debug: Log timer setup details
        sg_logger.info(f"Linux timer {self.timer_id} setup: {self.frequency_hz} Hz ({self.period_ms:.3f} ms = {interval_nsec} ns)")
        
        # Start timer thread
        self.timer_thread = threading.Thread(target=self._linux_timer_loop, daemon=True)
        self.timer_thread.start()
    
    def _stop_linux_timer(self):
        """Stop Linux timerfd timer"""
        if self.timer_fd:
            os.close(self.timer_fd)
            self.timer_fd = None
        if self.timer_thread:
            self.timer_thread.join(timeout=1.0)
            self.timer_thread = None
    
    def _linux_timer_loop(self):
        """Linux timerfd event loop"""
        event_count = 0
        total_missed = 0
        
        while self.is_running and self.timer_fd:
            try:
                # Wait for timer event
                ready, _, _ = select.select([self.timer_fd], [], [], 1.0)
                
                if ready and self.timer_fd in ready and self.is_running:
                    # Read the timer event
                    data = os.read(self.timer_fd, 8)
                    if len(data) == 8:
                        missed_events = struct.unpack('Q', data)[0]  # unsigned long long
                        
                        # Call callback only once per timer read, don't process accumulated events
                        # This matches Windows behavior and prevents callback flooding
                        if self.is_running:
                            self._on_timer_event(0)  # Always 0 like Windows
                        
                        # Track events and missed events for debugging
                        event_count += 1
                        total_missed += missed_events - 1
                        
                        # If the code took too long to execute and can't keep up with the timer, this will show as missed events like this.
                        # But it's also noticable by the fps dropping
                        # if missed_events > 10:
                        # We ignore them right now.
                        #     sg_logger.warn(f"Timer {self.timer_id}: missed {missed_events - 1} events")
                        
                        
                        # Periodic status report (disabled for production)
                        # if event_count % 1000 == 0:
                        #     sg_logger.info(f"Timer {self.timer_id}: {event_count} events processed, {total_missed} total missed")
                    
            except Exception as e:
                if self.is_running:
                    sg_logger.log(f"Timer {self.timer_id} loop error: {e}", level=sg_logger.ERROR)
                break

# Public API functions
def create_timer(frequency_hz: float = 1000.0) -> int:
    """
    Create a new high-precision timer.
    
    Args:
        frequency_hz: Timer frequency in Hz (default: 1000 Hz = 1ms intervals)
        
    Returns:
        timer_id: Unique timer identifier
        
    **Example:**
    ```python
    timer_id = SG_timer.create_timer(frequency_hz=500)  # 500 Hz = 2ms intervals
    ```
    """
    global _next_timer_id
    
    with _timer_lock:
        timer_id = _next_timer_id
        _next_timer_id += 1
        
        timer = SGTimer(timer_id, frequency_hz)
        _timers[timer_id] = timer
        
    sg_logger.info(f"Created timer {timer_id} at {frequency_hz} Hz")
    return timer_id

def start_timer(timer_id: int):
    """
    Start a timer.
    
    Args:
        timer_id: Timer identifier returned by create_timer()
        
    **Example:**
    ```python
    SG_timer.start_timer(timer_id)
    ```
    """
    timer = _timers.get(timer_id)
    if timer is None:
        raise ValueError(f"Timer {timer_id} not found")
    
    timer.start()

def stop_timer(timer_id: int):
    """
    Stop a timer.
    
    Args:
        timer_id: Timer identifier
        
    **Example:**
    ```python
    SG_timer.stop_timer(timer_id)
    ```
    """
    timer = _timers.get(timer_id)
    if timer is None:
        # Silently ignore if timer doesn't exist (already cleaned up)
        return
    
    timer.stop()

def destroy_timer(timer_id: int):
    """
    Stop and destroy a timer.
    
    Args:
        timer_id: Timer identifier
        
    **Example:**
    ```python
    SG_timer.destroy_timer(timer_id)
    ```
    """
    timer = _timers.get(timer_id)
    if timer is None:
        # Silently ignore if timer doesn't exist (already cleaned up)
        return
    
    timer.stop()
    
    with _timer_lock:
        if timer_id in _timers:  # Double-check in case of race condition
            del _timers[timer_id]
    
    sg_logger.info(f"Destroyed timer {timer_id}")

def subscribe_timer_callback(timer_id: int, callback: Callable[[int, int], None]):
    """
    Subscribe to timer events.
    
    Args:
        timer_id: Timer identifier
        callback: Function to call on timer events. 
                 Signature: callback(timer_id: int, missed_events: int) -> None
                 
    **Example:**
    ```python
    def my_timer_callback(timer_id, missed_events):
        print(f"Timer {timer_id} fired, missed: {missed_events}")
        
    SG_timer.subscribe_timer_callback(timer_id, my_timer_callback)
    ```
    """
    timer = _timers.get(timer_id)
    if timer is None:
        raise ValueError(f"Timer {timer_id} not found")
    
    timer.set_callback(callback)
    sg_logger.info(f"Subscribed callback to timer {timer_id}")

def get_timer_info(timer_id: int) -> Dict[str, Any]:
    """
    Get information about a timer.
    
    Args:
        timer_id: Timer identifier
        
    Returns:
        Dictionary with timer information
        
    **Example:**
    ```python
    info = SG_timer.get_timer_info(timer_id)
    print(f"Timer running: {info['is_running']}")
    ```
    """
    timer = _timers.get(timer_id)
    if timer is None:
        raise ValueError(f"Timer {timer_id} not found")
    
    return {
        'timer_id': timer.timer_id,
        'frequency_hz': timer.frequency_hz,
        'period_ms': timer.period_ms,
        'is_running': timer.is_running,
        'platform': platform.system()
    }

def list_timers() -> List[int]:
    """
    Get list of all timer IDs.
    
    Returns:
        List of timer IDs
        
    **Example:**
    ```python
    timer_ids = SG_timer.list_timers()
    print(f"Active timers: {timer_ids}")
    ```
    """
    return list(_timers.keys())

def cleanup_all_timers():
    """
    Stop and destroy all timers. Call this on program exit.
    
    **Example:**
    ```python
    SG_timer.cleanup_all_timers()
    ```
    """
    with _timer_lock:
        for timer in _timers.values():
            timer.stop()
        _timers.clear()
    
    sg_logger.info("Cleaned up all timers")

# Automatic cleanup on module exit
import atexit
atexit.register(cleanup_all_timers)
"""
Simple logger to log messages to the console as well as a log file.
Also summarizes repeated messages to a single message with a count and duration.

The console level can be set to WARNING or another level to only print WARNING and above (and print all others to the file only), but will always still print USER_INFO, as it is the highest level.

It also contains a function to convert a nested array to a string with proper indentation, so it can be printed nicely with sg_logger.nested_array_to_str(array)

Basic usage:
```python
from SG_API.SG_logger import sg_logger

#Logging
sg_logger.enable_file_logging(datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "-SG_API.log")
sg_logger.set_console_level(sg_logger.WARNING)

def log_uncaught_exceptions(exctype, value, tb):
    tb_str = ''.join(traceback.format_exception(exctype, value, tb))
    sg_logger.log("Uncaught exception:\n", tb_str, level=sg_logger.CRITICAL)
    
sys.excepthook = log_uncaught_exceptions


sg_logger.log("Waiting for glove to connect...", level=sg_logger.USER_INFO)

```


Questions? Written by:
- Amber Elferink
Support: https://www.senseglove.com/support/
"""

import os
import datetime
import sys
import glob
import time
import traceback
import numpy as np

# don't use this class directly, use the sg_logger singleton instead
class Class_SGLogger_use_singleton:
    # Priority levels
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    USER_INFO = 60
    LEVEL_NAMES = {
        DEBUG: "DEBUG",
        INFO: "INFO",
        WARNING: "WARNING",
        ERROR: "ERROR",
        CRITICAL: "CRITICAL",
        USER_INFO: "USER_CONSOLE_INFO"
    }

    # ANSI Color codes
    RESET = '\033[0m'
    RED = '\033[91m'      # CRITICAL
    YELLOW = '\033[93m'   # WARNING
    MAGENTA = '\033[95m'  # ERROR
    CYAN = '\033[96m'     # File paths
    BLUE = '\033[94m'     # File paths alternative
    BOLD = '\033[1m'      # Bold text

    def __init__(self):
        self.log_to_file = False
        self.log_file_path = "sg_api.log"
        self.console_level = self.WARNING  # Only print WARNING and above by default
        self.clickable_links = False  # Use full paths for clickable links
        self.show_traceback = True  # Show full traceback for all logs by default
        self.enable_colors = True  # Enable colors for console output
        
        # Message bundling for repeated logs (Unity-style)
        self._message_counts = {}  # message -> count
        self._message_levels = {}  # message -> level
        self._message_first_time = {}  # message -> first occurrence time
        self._last_flush_time = time.time()
        self._bundle_window = 2.0  # seconds to bundle identical messages
        self._max_bundle_count = 500  # max count before forcing a flush
        self._just_bundled = set()  # messages that were just bundled (to prevent immediate traceback)

    def set_console_level(self, level):
        self.console_level = level

    def set_clickable_links(self, enabled=True):
        """Enable/disable full paths for clickable links in IDEs"""
        self.clickable_links = enabled

    def set_show_traceback(self, enabled=True):
        """Enable/disable full traceback for all logs"""
        self.show_traceback = enabled



    def nested_array_to_str(self, arr):
        # Convert numpy arrays to lists (recursively) so that printing is clean
        if isinstance(arr, np.ndarray):
            arr = arr.tolist()
        if not isinstance(arr, (list, tuple)):
            return str(arr) + '\n'

        # For nested arrays, print the first level cleanly
        lines = []
        lines.append('[')
        for sub in arr:
            # Convert any nested numpy array to list for clean printing
            if isinstance(sub, np.ndarray):
                sub = sub.tolist()
            lines.append('  ' + str(sub) + ',')
        lines.append(']')
        return '\n'.join(lines)        

    def enable_file_logging(self, path=None):
        # Ensure logs directory exists
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        # If path is not absolute, put it in logs dir
        if path:
            if not os.path.isabs(path):
                self.log_file_path = os.path.join(logs_dir, path)
            else:
                self.log_file_path = path
        else:
            self.log_file_path = os.path.join(logs_dir, "sg_api.log")
        self.log_to_file = True
        # Remove oldest log if more than 10 in logs dir
        log_files = sorted(glob.glob(os.path.join(logs_dir, "*.log")), key=os.path.getmtime)
        if len(log_files) > 10:
            os.remove(log_files[0])

    def disable_file_logging(self):
        self.log_to_file = False

    def set_enable_colors(self, enabled=True):
        """Enable/disable colors for console output"""
        self.enable_colors = enabled

    def _get_colored_level_name(self, level):
        """Get level name with appropriate color"""
        level_name = self.LEVEL_NAMES.get(level, str(level)).upper()
        level_name_padded = level_name.ljust(17)
        
        if not self.enable_colors:
            return level_name_padded, ""
            
        if level == self.CRITICAL:
            return f"{self.BOLD}{level_name_padded}{self.RESET}", f"{self.RED}{self.BOLD}"
        elif level == self.ERROR:
            return f"{self.BOLD}{level_name_padded}{self.RESET}", f"{self.MAGENTA}{self.BOLD}"
        elif level == self.WARNING:
            return f"{self.BOLD}{level_name_padded}{self.RESET}", f"{self.YELLOW}{self.BOLD}"
        else:
            return level_name_padded, ""

    def _get_level_color(self, level):
        """Get the color code for a level (for entire line coloring)"""
        if not self.enable_colors:
            return ""
            
        if level == self.CRITICAL:
            return f"{self.RED}{self.BOLD}"
        elif level == self.ERROR:
            return f"{self.MAGENTA}{self.BOLD}"
        elif level == self.WARNING:
            return f"{self.YELLOW}{self.BOLD}"
        else:
            return ""

    def _get_colored_file_path(self, file_path):
        """Get file path with color for clickability"""
        if not self.enable_colors:
            return file_path
        return f"{self.CYAN}{file_path}{self.RESET}"

    def _flush_bundled_messages(self):
        """Flush all bundled messages with their counts"""
        current_time = time.time()
        messages_to_remove = []
        
        # Create a snapshot of the dictionary to avoid RuntimeError if modified during iteration
        for msg, count in list(self._message_counts.items()):
            if count > 1:
                level = self._message_levels.get(msg)
                first_time = self._message_first_time.get(msg)
                if level is not None and first_time is not None:
                    duration = current_time - first_time
                    self._log_bundled_message(msg, level, count, duration)
            messages_to_remove.append(msg)
        
        # Clean up bundled messages
        for msg in messages_to_remove:
            self._message_counts.pop(msg, None)
            self._message_levels.pop(msg, None)
            self._message_first_time.pop(msg, None)
        
        self._last_flush_time = current_time

    def _should_flush(self):
        """Check if we should flush bundled messages"""
        current_time = time.time()
        return (current_time - self._last_flush_time >= self._bundle_window or
                any(count >= self._max_bundle_count for count in list(self._message_counts.values())))

    def _log_direct(self, msg, level):
        """Direct logging without bundling - used internally"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_name_colored, level_color = self._get_colored_level_name(level)
        
        try:
            # 4 = _log_direct() <- _flush_bundled_messages() <- log() <- user
            # 3 = _log_direct() <- log() <- user  
            frame_depth = 4 if sys._getframe(3).f_code.co_name == '_flush_bundled_messages' else 3
            frame = sys._getframe(frame_depth)
            full_filename = frame.f_code.co_filename
            filename = os.path.basename(full_filename)
            lineno = frame.f_lineno
            
            if self.clickable_links:
                # Format for clickable links in most IDEs: full_path:line_number
                fileline = f"{full_filename}:{lineno}"
                fileline_colored = self._get_colored_file_path(fileline)
                # Calculate padding based on original string length, then apply to colored version
                padding_needed = max(0, 50 - len(fileline))
                fileline_padded = fileline_colored + ' ' * padding_needed
            else:
                # Original compact format
                fileline = f"{filename}:{lineno}"
                fileline_colored = self._get_colored_file_path(fileline)
                # Calculate padding based on original string length
                padding_needed = max(0, 30 - len(fileline))
                fileline_padded = f"[{fileline_colored}" + ' ' * padding_needed + "]"
        except Exception:
            fileline = "unknown:0"
            fileline_colored = self._get_colored_file_path(fileline)
            if self.clickable_links:
                padding_needed = max(0, 50 - len(fileline))
                fileline_padded = fileline_colored + ' ' * padding_needed
            else:
                padding_needed = max(0, 30 - len(fileline))
                fileline_padded = f"[{fileline_colored}" + ' ' * padding_needed + "]"

        if level == self.USER_INFO:
            log_msg = f"[{timestamp}] {level_name_colored}: {msg}"
        else:
            log_msg = f"[{timestamp}] {level_name_colored} {fileline_padded}: {msg}"

        # Apply level color to entire line for console output
        if level_color:
            console_log_msg = f"{level_color}{log_msg}{self.RESET}"
        else:
            console_log_msg = log_msg
        
        if level == self.USER_INFO:
            console_msg = msg
        else:
            console_msg = console_log_msg
        if level >= self.console_level:
            print("SG_API: " + console_msg)
        if self.log_to_file:
            # Remove colors for file output
            level_name_plain = self.LEVEL_NAMES.get(level, str(level)).upper().ljust(17)
            if level == self.USER_INFO:
                file_log_msg = f"[{timestamp}] {level_name_plain}: {msg}"
            else:
                fileline_plain = fileline if self.clickable_links else f"[{fileline}]"
                fileline_plain_padded = f"{fileline_plain:<50}" if self.clickable_links else f"{fileline_plain:<32}"
                file_log_msg = f"[{timestamp}] {level_name_plain} {fileline_plain_padded}: {msg}"
            with open(self.log_file_path, "a") as f:
                f.write(file_log_msg + "\n")

    def _log_traceback_internal(self, msg, level):
        """Internal method to log with traceback - used by the main log() method"""
        # Get the complete stack trace, but skip more frames since this is called internally
        stack = traceback.extract_stack()
        
        # Remove logger internal frames
        filtered_stack = []
        for frame in stack:
            # Skip frames from this logger file
            if not frame.filename.endswith('SG_logger.py'):
                filtered_stack.append(frame)
        
        # Format the message with traceback
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_name_colored, level_color = self._get_colored_level_name(level)
        
        # Create a traceback-style output showing the complete call stack
        trace_lines = []
        message_line = f"[{timestamp}] {level_name_colored}: {msg}"
        if level_color:
            colored_message_line = f"{level_color}{message_line}{self.RESET}"
        else:
            colored_message_line = message_line
        trace_lines.append(colored_message_line)
        trace_lines.append(f"=== Traceback (most recent call last): ===")
        
        for frame in filtered_stack:
            file_path_colored = self._get_colored_file_path(f'"{frame.filename}"')
            trace_lines.append(f"    +- File {file_path_colored}, line {frame.lineno}, in {frame.name}")
            if frame.line:
                trace_lines.append(f"    |      {frame.line.strip()}")
        
        trace_lines.append(f"===============================================================")
        
        # Print all lines
        for line in trace_lines:
            if level >= self.console_level:
                print("SG_API: " + line)
            
        # Also write to file if enabled (without colors)
        if self.log_to_file:
            level_name_plain = self.LEVEL_NAMES.get(level, str(level)).upper().ljust(17)
            file_trace_lines = []
            file_trace_lines.append(f"[{timestamp}] {level_name_plain}: {msg}")
            file_trace_lines.append(f"=== Traceback (most recent call last): ===")
            
            for frame in filtered_stack:
                file_trace_lines.append(f'    +- File "{frame.filename}", line {frame.lineno}, in {frame.name}')
                if frame.line:
                    file_trace_lines.append(f"    |      {frame.line.strip()}")
            
            file_trace_lines.append(f"===============================================================")
            
            with open(self.log_file_path, "a") as f:
                for line in file_trace_lines:
                    f.write(line + "\n")

    def _log_bundled_message(self, msg, level, count, duration):
        """Helper method to output bundled messages with consistent formatting"""
        bundled_msg = f"(× {count} msgs in {duration:.1f} seconds): {msg}"
        
        # Use traceback format for bundled messages if level warrants it
        if self.show_traceback and level >= self.WARNING and level != self.USER_INFO:
            self._log_traceback_internal(bundled_msg, level)
        else:
            # Format with bundle info at the very front
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            level_name_colored, level_color = self._get_colored_level_name(level)
            
            if level == self.USER_INFO:
                bundled_log = f"(× {count} msgs in {duration:.1f} seconds): [{timestamp}] {level_name_colored}: {msg}"
            else:
                bundled_log = f"(× {count} msgs in {duration:.1f} seconds): [{timestamp}] {level_name_colored}: {msg}"
            
            # Apply level color to entire bundled line
            if level_color:
                colored_bundled_log = f"{level_color}{bundled_log}{self.RESET}"
            else:
                colored_bundled_log = bundled_log
            
            # Print directly
            if level >= self.console_level:
                print("SG_API: " + colored_bundled_log)
            if self.log_to_file:
                # Write to file without colors
                level_name_plain = self.LEVEL_NAMES.get(level, str(level)).upper().ljust(17)
                if level == self.USER_INFO:
                    file_bundled_log = f"(× {count} msgs in {duration:.1f} seconds): [{timestamp}] {level_name_plain}: {msg}"
                else:
                    file_bundled_log = f"(× {count} msgs in {duration:.1f} seconds): [{timestamp}] {level_name_plain}: {msg}"
                with open(self.log_file_path, "a") as f:
                    f.write(file_bundled_log + "\n")
        
        # Mark as just bundled to prevent immediate traceback
        self._just_bundled.add(msg)

    def log(self, *args, level=WARNING, category=RuntimeWarning):
        msg = ' '.join(str(a) for a in args)
        current_time = time.time()
        
        # Check if we should flush bundled messages
        if self._should_flush():
            self._flush_bundled_messages()
        
        # Check if this message is already being bundled
        if msg in self._message_counts:
            # Increment count for repeated message
            self._message_counts[msg] += 1
            
            # If we've reached max count, flush immediately
            if self._message_counts[msg] >= self._max_bundle_count:
                count = self._message_counts[msg]
                first_time = self._message_first_time[msg]
                duration = current_time - first_time
                
                self._log_bundled_message(msg, level, count, duration)
                        
                # Clean up this specific message
                del self._message_counts[msg]
                del self._message_levels[msg]
                del self._message_first_time[msg]
        else:
            # New message - check if it was just bundled
            just_bundled = msg in self._just_bundled
            if just_bundled:
                # This message was just bundled - start tracking silently (don't log)
                self._just_bundled.remove(msg)
                self._message_counts[msg] = 1
                self._message_levels[msg] = level
                self._message_first_time[msg] = current_time
            else:
                # Truly new message - log immediately and start tracking
                if (self.show_traceback and level >= self.WARNING and level != self.USER_INFO):
                    self._log_traceback_internal(msg, level)
                else:
                    self._log_direct(msg, level)
                self._message_counts[msg] = 1
                self._message_levels[msg] = level
                self._message_first_time[msg] = current_time

    def warn(self, *args, level=WARNING, category=RuntimeWarning):
        self.log(*args, level=level, category=category)

    def info(self, *args, level=INFO):
        self.log(*args, level=level)

    def flush_bundled(self):
        """Manually flush all bundled messages - useful for shutdown or debugging"""
        if self._message_counts:
            self._flush_bundled_messages()

    def log_with_traceback(self, *args, level=WARNING, skip_internal_frames=True):
        """
        Log a message with a full Python traceback for maximum clickability.
        
        Args:
            *args: Message parts to log
            level: Log level
            skip_internal_frames: If True, excludes logger internal frames from traceback
        """
        msg = ' '.join(str(a) for a in args)
        
        
        # Get the complete stack trace
        stack = traceback.extract_stack()
        
        if skip_internal_frames:
            # Remove this method and any other logger internal frames
            filtered_stack = []
            for frame in stack:
                # Skip frames from this logger file
                if not frame.filename.endswith('SG_logger.py'):
                    filtered_stack.append(frame)
            stack = filtered_stack
        else:
            # Just remove this specific method call
            stack = stack[:-1]
        
        # Format the message with traceback
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_name_colored, level_color = self._get_colored_level_name(level)
        
        # Create a traceback-style output showing the complete call stack
        trace_lines = []
        message_line = f"[{timestamp}] {level_name_colored}: {msg}"
        if level_color:
            colored_message_line = f"{level_color}{message_line}{self.RESET}"
        else:
            colored_message_line = message_line
        trace_lines.append(colored_message_line)
        trace_lines.append(f"=== Traceback (most recent call last): ===")
        
        for frame in stack:
            file_path_colored = self._get_colored_file_path(f'"{frame.filename}"')
            trace_lines.append(f"    +- File {file_path_colored}, line {frame.lineno}, in {frame.name}")
            if frame.line:
                trace_lines.append(f"    |      {frame.line.strip()}")
        
        trace_lines.append(f"===============================================================")
        
        # Print all lines
        for line in trace_lines:
            if level >= self.console_level:
                print("SG_API: " + line)
            
        # Also write to file if enabled (without colors)
        if self.log_to_file:
            level_name_plain = self.LEVEL_NAMES.get(level, str(level)).upper().ljust(17)
            file_trace_lines = []
            file_trace_lines.append(f"[{timestamp}] {level_name_plain}: {msg}")
            file_trace_lines.append(f"=== Traceback (most recent call last): ===")
            
            for frame in stack:
                file_trace_lines.append(f'    +- File "{frame.filename}", line {frame.lineno}, in {frame.name}')
                if frame.line:
                    file_trace_lines.append(f"    |      {frame.line.strip()}")
            
            file_trace_lines.append(f"===============================================================")
            
            with open(self.log_file_path, "a") as f:
                for line in file_trace_lines:
                    f.write(line + "\n")

# Singleton instance
sg_logger = Class_SGLogger_use_singleton() 
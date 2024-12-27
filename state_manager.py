from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import win32gui
import psutil
import win32api
import win32con
import logging
from datetime import datetime
import win32process
import traceback

@dataclass
class SystemState:
    active_window: dict
    window_list: list
    running_processes: list
    cursor_position: tuple
    screen_resolution: tuple
    vision_info: dict = None
    last_action: dict = None
    last_result: dict = None
    
class StateManager:
    def __init__(self, logger=None):
        self.previous_state = None
        self.current_state = None
        self.logger = logger or logging.getLogger(__name__)
        
    def capture_state(self) -> Dict[str, Any]:
        """Capture current system state"""
        try:
            active_window = self.get_active_window()
            current_state = {
                'timestamp': datetime.now().isoformat(),
                'active_window': active_window,
                'mouse_position': win32api.GetCursorPos(),
                'foreground_pid': None  # Initialize as None
            }
            
            # Get process ID if we have an active window
            if active_window and 'handle' in active_window:
                # Use win32process instead of win32gui
                _, pid = win32process.GetWindowThreadProcessId(active_window['handle'])
                current_state['foreground_pid'] = pid
            
            # Update state history
            self.previous_state = self.current_state
            self.current_state = current_state
            
            return current_state
            
        except Exception as e:
            self.logger.error(f"Failed to capture state: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def get_running_programs(self) -> List[str]:
        """Get list of running programs"""
        programs = []
        def enum_windows_callback(hwnd, programs):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and not title.startswith("_") and title != "Agent Control Panel":
                    programs.append(title)
        
        win32gui.EnumWindows(enum_windows_callback, programs)
        return programs

    def close_program(self, program_name: str) -> bool:
        """Close specified program"""
        def find_window(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if program_name.lower() in title.lower():
                    ctx.append(hwnd)
        
        handles = []
        win32gui.EnumWindows(find_window, handles)
        
        if handles:
            win32gui.PostMessage(handles[0], win32con.WM_CLOSE, 0, 0)
            return True
        return False 

    def update_vision_state(self, vision_info: Dict[str, Any]):
        """Update state with vision information"""
        if self.current_state is not None:
            if isinstance(self.current_state, dict):
                self.current_state['vision_info'] = vision_info
            else:
                self.current_state.vision_info = vision_info

    def _get_window_list(self) -> list:
        """Get list of visible windows"""
        windows = []
        
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:  # Only add windows with titles
                    windows.append({
                        'handle': hwnd,
                        'title': title,
                        'rect': win32gui.GetWindowRect(hwnd)
                    })
        
        win32gui.EnumWindows(enum_windows_callback, windows)
        return windows

    def get_window_by_title(self, title: str) -> dict:
        """Find window by title (partial match)"""
        for window in self._get_window_list():
            if title.lower() in window['title'].lower():
                return window
        return None

    def get_active_window(self) -> dict:
        """Get currently active window"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return {
                    'handle': hwnd,
                    'title': win32gui.GetWindowText(hwnd),
                    'rect': win32gui.GetWindowRect(hwnd)
                }
            return None
        except Exception as e:
            self.logger.error(f"Failed to get active window: {str(e)}")
            return None 

    def update_state(self, new_state: Dict[str, Any]):
        """Update current state with new information"""
        try:
            if self.current_state is None:
                self.current_state = {}
            
            if isinstance(self.current_state, dict):
                # Update existing state
                self.current_state.update(new_state)
                
                # Ensure timestamp is present
                if 'timestamp' not in self.current_state:
                    self.current_state['timestamp'] = datetime.now().isoformat()
                    
                # Log state update
                self.logger.debug(f"State updated: {new_state}")
                
            else:
                # Handle case where current_state is not a dict
                self.logger.warning("Current state is not a dictionary, creating new state")
                self.current_state = new_state
                
        except Exception as e:
            self.logger.error(f"Failed to update state: {str(e)}")
            self.logger.error(traceback.format_exc()) 
from dataclasses import dataclass
from typing import Dict, Any, Optional
import win32gui
import psutil

@dataclass
class SystemState:
    active_window: str
    window_list: list
    running_processes: list
    cursor_position: tuple
    screen_resolution: tuple
    
class StateManager:
    def __init__(self):
        self.previous_state = None
        self.current_state = None
        
    def capture_state(self) -> SystemState:
        """Capture current system state"""
        active_window = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        processes = [p.name() for p in psutil.process_iter(['name'])]
        
        state = SystemState(
            active_window=active_window,
            window_list=self._get_window_list(),
            running_processes=processes,
            cursor_position=win32gui.GetCursorPos(),
            screen_resolution=win32gui.GetSystemMetrics(0, 1)
        )
        
        self.previous_state = self.current_state
        self.current_state = state
        return state 
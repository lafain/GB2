import logging
from typing import Tuple
import win32gui
import win32con

class CoordinateSystem:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
    def to_screen_coords(self, x: int, y: int) -> Tuple[int, int]:
        """Convert relative coordinates to screen coordinates"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                screen_x = rect[0] + x
                screen_y = rect[1] + y
                return screen_x, screen_y
            else:
                self.logger.error("No active window for coordinate conversion")
                return x, y
        except Exception as e:
            self.logger.error(f"Coordinate conversion failed: {str(e)}")
            return x, y 
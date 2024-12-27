from typing import Dict, Any
import logging
import pyautogui
import keyboard
import mouse
import time
import win32gui
import win32con

class ActionExecutor:
    def __init__(self, logger: logging.Logger, coordinate_system, state_manager):
        self.logger = logger
        self.coordinate_system = coordinate_system
        self.state_manager = state_manager
        pyautogui.FAILSAFE = True
        
    def execute_action(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action with given parameters"""
        try:
            if action_name == "launch_program":
                return self.launch_program(params.get("name", ""))
            # ... other actions ...
            
        except Exception as e:
            self.logger.error(f"Action execution failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def launch_program(self, program_name: str) -> Dict[str, Any]:
        """Launch a program by name"""
        try:
            program_name = program_name.lower()
            
            # Common program aliases
            program_map = {
                "paint": ["mspaint.exe", "paint.exe"],
                "notepad": ["notepad.exe"],
                "calculator": ["calc.exe"],
                "explorer": ["explorer.exe"],
                # Add more as needed
            }
            
            # Get possible executable names
            possible_names = program_map.get(program_name, [program_name])
            
            # Check if already running
            import psutil
            for proc in psutil.process_iter(['name']):
                if proc.info['name'].lower() in possible_names:
                    self.logger.info(f"Program '{program_name}' is already running")
                    return {"success": True}
            
            # Try to launch program
            import subprocess
            for exe_name in possible_names:
                try:
                    subprocess.Popen(exe_name)
                    self.logger.info(f"Launched program: {exe_name}")
                    return {"success": True}
                except:
                    continue
                
            raise Exception(f"Failed to launch program: {program_name}")
            
        except Exception as e:
            self.logger.error(f"Program launch failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def _click(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute mouse click"""
        try:
            x = params.get("x", 0)
            y = params.get("y", 0)
            button = params.get("button", "left")
            
            # Convert coordinates
            screen_x, screen_y = self.coordinate_system.to_screen_coords(x, y)
            
            # Move and click
            pyautogui.moveTo(screen_x, screen_y)
            pyautogui.click(button=button)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _type(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Type text"""
        try:
            text = params.get("text", "")
            interval = params.get("interval", 0.1)
            
            pyautogui.typewrite(text, interval=interval)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _press_key(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Press keyboard key"""
        try:
            key = params.get("key", "")
            pyautogui.press(key)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _move_mouse(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Move mouse cursor"""
        try:
            x = params.get("x", 0)
            y = params.get("y", 0)
            
            screen_x, screen_y = self.coordinate_system.to_screen_coords(x, y)
            pyautogui.moveTo(screen_x, screen_y)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _drag_mouse(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Drag mouse"""
        try:
            start_x = params.get("start_x", 0)
            start_y = params.get("start_y", 0)
            end_x = params.get("end_x", 0)
            end_y = params.get("end_y", 0)
            
            # Convert coordinates
            start_screen_x, start_screen_y = self.coordinate_system.to_screen_coords(start_x, start_y)
            end_screen_x, end_screen_y = self.coordinate_system.to_screen_coords(end_x, end_y)
            
            # Execute drag
            pyautogui.moveTo(start_screen_x, start_screen_y)
            pyautogui.dragTo(end_screen_x, end_screen_y)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _wait(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wait specified time"""
        try:
            seconds = params.get("seconds", 1)
            time.sleep(seconds)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _focus_window(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Focus specified window"""
        try:
            title = params.get("title", "")
            window = self.state_manager.get_window_by_title(title)
            
            if window:
                win32gui.SetForegroundWindow(window['handle'])
                return {"success": True}
            else:
                return {"success": False, "error": f"Window not found: {title}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
  
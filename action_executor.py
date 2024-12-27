from typing import Dict, Any, Optional
import pyautogui
import keyboard
import cv2
import numpy as np
from PIL import ImageGrab
import win32gui
import win32con
import time
import os

class ActionExecutor:
    """Handles execution of all agent actions"""
    
    def __init__(self, logger):
        self.logger = logger
        self.last_screenshot = None
        self.window_info = None
        self.available_actions = {
            "click": self._click,
            "type_text": self._type_text,
            "press_keys": self._press_keys,
            "get_screen": self._get_screen,
            "find_element": self._find_element,
            "move_mouse": self._move_mouse,
            "get_window_info": self._get_window_info,
            "set_window_position": self._set_window_position,
            "launch_program": self._launch_program,
            "drag_mouse": self._drag_mouse
        }
        
        # Configure safety settings
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5
        
    def _launch_program(self, program_name: str) -> Dict[str, Any]:
        """Launch a program using Win+R"""
        try:
            if program_name.lower() == "paint":
                self.logger.info("Attempting to launch Paint...")
                
                # Press Win+R
                self.logger.debug("Opening Run dialog (Win+R)")
                pyautogui.hotkey('win', 'r')
                time.sleep(0.5)
                
                # Type mspaint and press enter
                self.logger.debug("Typing 'mspaint' in Run dialog")
                pyautogui.write('mspaint')
                pyautogui.press('enter')
                self.logger.info("Waiting for Paint to open...")
                time.sleep(2.0)
                
                # Verify Paint window
                self.logger.debug("Searching for Paint window...")
                paint_window = None
                def callback(hwnd, ctx):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd).lower()
                        if 'paint' in title:
                            ctx.append(hwnd)
                    return True
                
                paint_windows = []
                win32gui.EnumWindows(callback, paint_windows)
                
                if paint_windows:
                    # Activate Paint window
                    self.logger.info(f"Found Paint window (handle: {paint_windows[0]})")
                    win32gui.SetForegroundWindow(paint_windows[0])
                    time.sleep(0.5)
                    return {
                        "success": True, 
                        "window_handle": paint_windows[0],
                        "details": "Paint launched and activated successfully"
                    }
                    
                self.logger.error("Paint window not found after launch")
                return {
                    "success": False, 
                    "error": "Program launched but window not found",
                    "details": "Paint process may have started but window is not visible"
                }
                
            self.logger.error(f"Unsupported program: {program_name}")
            return {"success": False, "error": f"Program '{program_name}' not supported"}
            
        except Exception as e:
            self.logger.error(f"Launch program failed: {str(e)}")
            return {"success": False, "error": str(e), "details": "Exception during program launch"}

    def get_action_descriptions(self) -> str:
        """Return descriptions of available actions"""
        descriptions = {
            "launch_program": "Launch a program (params: program_name)",
            "click": "Click at coordinates (params: x, y, button='left')",
            "type_text": "Type text (params: text, enter=False)",
            "press_keys": "Press key combination (params: keys)",
            "move_mouse": "Move mouse to coordinates (params: x, y)",
            "get_window_info": "Get window information (params: title)",
            "set_window_position": "Set window position (params: title, x, y, width, height)",
            "drag_mouse": "Drag mouse from start to end coordinates (params: start_x, start_y, end_x, end_y, relative=True)"
        }
        return "\n".join([f"- {name}: {desc}" for name, desc in descriptions.items()])
        
    def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action and return the result"""
        try:
            name = action.get("function_name")
            params = action.get("function_params", {})
            
            if name not in self.available_actions:
                raise ValueError(f"Unknown action: {name}")
                
            result = self.available_actions[name](**params)
            return {"success": True, "result": result}
            
        except Exception as e:
            self.logger.error(f"Action execution failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _click(self, x: int, y: int, button: str = "left", relative: bool = True) -> Dict[str, Any]:
        """Click at coordinates (relative to window if specified)"""
        try:
            # Take screenshot before action
            self.last_screenshot = ImageGrab.grab()
            
            # Convert relative coordinates if needed
            actual_x, actual_y = x, y
            if relative and self.window_info:
                actual_x = self.window_info["position"][0] + x
                actual_y = self.window_info["position"][1] + y
                
            # Move mouse with visual feedback
            pyautogui.moveTo(actual_x, actual_y, duration=0.5)
            time.sleep(0.2)  # Brief pause to show position
            
            # Click and capture result
            pyautogui.click(button=button)
            time.sleep(0.2)
            
            # Take screenshot after action
            after_screenshot = ImageGrab.grab()
            
            # Save debug images
            debug_dir = "debug_screenshots"
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            before_path = f"{debug_dir}/before_click_{timestamp}.png"
            after_path = f"{debug_dir}/after_click_{timestamp}.png"
            
            self.last_screenshot.save(before_path)
            after_screenshot.save(after_path)
            
            # Draw click position on debug image
            debug_img = np.array(after_screenshot)
            cv2.circle(debug_img, (actual_x, actual_y), 10, (255, 0, 0), 2)
            cv2.imwrite(f"{debug_dir}/click_location_{timestamp}.png", debug_img)
            
            result = {
                "success": True,
                "relative_pos": (x, y),
                "actual_pos": (actual_x, actual_y),
                "before_image": before_path,
                "after_image": after_path,
                "debug_image": f"{debug_dir}/click_location_{timestamp}.png"
            }
            
            self.logger.info(f"Clicked at relative ({x}, {y}) -> actual ({actual_x}, {actual_y})")
            self.logger.debug(f"Debug images saved to {debug_dir}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Click failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _type_text(self, text: str, enter: bool = False) -> Dict[str, Any]:
        """Type text with optional enter press"""
        try:
            pyautogui.write(text)
            if enter:
                pyautogui.press('enter')
            self.logger.debug(f"Typed text: {text}")
            return {"success": True, "text": text}
        except Exception as e:
            self.logger.error(f"Type text failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _press_keys(self, keys: str) -> Dict[str, Any]:
        """Press key combination"""
        try:
            pyautogui.hotkey(*keys.split('+'))
            self.logger.debug(f"Pressed keys: {keys}")
            return {"success": True, "keys": keys}
        except Exception as e:
            self.logger.error(f"Key press failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _get_screen(self, region: Optional[tuple] = None) -> Dict[str, Any]:
        """Capture screenshot of region"""
        try:
            screenshot = ImageGrab.grab(bbox=region)
            self.logger.debug(f"Captured screenshot of region: {region}")
            return {"success": True, "image": screenshot}
        except Exception as e:
            self.logger.error(f"Screenshot failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _find_element(self, template_path: str) -> Dict[str, Any]:
        """Find UI element matching template"""
        try:
            screen = np.array(ImageGrab.grab())
            template = cv2.imread(template_path)
            
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            if max_val > 0.8:  # Confidence threshold
                self.logger.debug(f"Found element at {max_loc}")
                return {"success": True, "position": max_loc, "confidence": max_val}
            else:
                self.logger.debug("Element not found")
                return {"success": False, "error": "Element not found"}
                
        except Exception as e:
            self.logger.error(f"Find element failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _move_mouse(self, x: int, y: int, duration: float = 0.5) -> Dict[str, Any]:
        """Move mouse to coordinates"""
        try:
            pyautogui.moveTo(x, y, duration=duration)
            self.logger.debug(f"Moved mouse to ({x}, {y})")
            return {"success": True, "position": (x, y)}
        except Exception as e:
            self.logger.error(f"Mouse move failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _get_window_info(self, title: str) -> Dict[str, Any]:
        """Get window position and size"""
        try:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                self.window_info = {
                    "handle": hwnd,
                    "rect": rect,
                    "position": (rect[0], rect[1]),
                    "size": (rect[2] - rect[0], rect[3] - rect[1])
                }
                
                # Maximize window for consistent coordinates
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                time.sleep(0.5)  # Wait for maximize
                
                # Get updated coordinates
                new_rect = win32gui.GetWindowRect(hwnd)
                self.window_info.update({
                    "rect": new_rect,
                    "position": (new_rect[0], new_rect[1]),
                    "size": (new_rect[2] - new_rect[0], new_rect[3] - new_rect[1])
                })
                
                self.logger.info(f"Window '{title}' maximized at {new_rect}")
                return {"success": True, **self.window_info}
            else:
                self.logger.error(f"Window '{title}' not found")
                return {"success": False, "error": "Window not found"}
        except Exception as e:
            self.logger.error(f"Get window info failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _set_window_position(self, title: str, x: int, y: int, width: int, height: int) -> Dict[str, Any]:
        """Set window position and size"""
        try:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                win32gui.MoveWindow(hwnd, x, y, width, height, True)
                self.logger.debug(f"Set window '{title}' to ({x}, {y}, {width}, {height})")
                return {"success": True, "window": title, "position": (x, y), "size": (width, height)}
            else:
                self.logger.debug(f"Window '{title}' not found")
                return {"success": False, "error": "Window not found"}
        except Exception as e:
            self.logger.error(f"Set window position failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _drag_mouse(self, start_x: int, start_y: int, end_x: int, end_y: int, relative: bool = True) -> Dict[str, Any]:
        """Drag mouse from start to end coordinates"""
        try:
            # Take screenshot before action
            self.last_screenshot = ImageGrab.grab()
            
            # Convert coordinates if relative
            actual_start_x, actual_start_y = start_x, start_y
            actual_end_x, actual_end_y = end_x, end_y
            
            if relative and self.window_info:
                actual_start_x = self.window_info["position"][0] + start_x
                actual_start_y = self.window_info["position"][1] + start_y
                actual_end_x = self.window_info["position"][0] + end_x
                actual_end_y = self.window_info["position"][1] + end_y
            
            # Move to start position
            pyautogui.moveTo(actual_start_x, actual_start_y, duration=0.5)
            time.sleep(0.2)
            
            # Drag to end position
            pyautogui.mouseDown()
            pyautogui.moveTo(actual_end_x, actual_end_y, duration=0.5)
            pyautogui.mouseUp()
            time.sleep(0.2)
            
            # Take screenshot after action
            after_screenshot = ImageGrab.grab()
            
            # Save debug images
            debug_dir = "debug_screenshots"
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            before_path = f"{debug_dir}/before_drag_{timestamp}.png"
            after_path = f"{debug_dir}/after_drag_{timestamp}.png"
            
            self.last_screenshot.save(before_path)
            after_screenshot.save(after_path)
            
            # Draw drag line on debug image
            debug_img = np.array(after_screenshot)
            cv2.line(debug_img, 
                    (actual_start_x, actual_start_y),
                    (actual_end_x, actual_end_y),
                    (255, 0, 0), 2)
            cv2.imwrite(f"{debug_dir}/drag_line_{timestamp}.png", debug_img)
            
            result = {
                "success": True,
                "relative_start": (start_x, start_y),
                "relative_end": (end_x, end_y),
                "actual_start": (actual_start_x, actual_start_y),
                "actual_end": (actual_end_x, actual_end_y),
                "before_image": before_path,
                "after_image": after_path,
                "debug_image": f"{debug_dir}/drag_line_{timestamp}.png"
            }
            
            self.logger.info(f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")
            self.logger.debug(f"Debug images saved to {debug_dir}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Mouse drag failed: {str(e)}")
            return {"success": False, "error": str(e)}
  
import keyboard
import pyautogui
import time
import win32gui
import win32con
import win32api
import os
from typing import Optional, Tuple, Dict

class InputManager:
    def __init__(self, logger):
        self.logger = logger
        self.last_action_time = 0
        self.min_action_delay = 0.5
        self.key_press_delay = 0.1
        self.key_hold_time = 0.2
        self.char_delay = 0.05
        self.verification_delay = 0.5
        self.max_retries = 3
        self.retry_delay = 1.0
        self.action_history = []
        self.failed_actions = []
        
    def execute_key_combination(self, keys: str) -> bool:
        """Execute a key combination with proper delays and verification"""
        try:
            self._ensure_delay()
            
            # Track this action
            action_data = {"type": "key_combination", "keys": keys, "timestamp": time.time()}
            
            # Clean and validate input
            if not keys:
                return False
                
            # Handle special case for win+r
            if keys.lower() == 'win+r':
                success = self._execute_run_dialog()
                action_data["success"] = success
                self.action_history.append(action_data)
                return success
                
            # Map special keys
            key_map = {
                'win': 'windows',
                'windows': 'windows',
                'alt': 'alt',
                'ctrl': 'ctrl',
                'shift': 'shift',
                'enter': 'enter',
                'esc': 'escape'
            }
            
            # Split and clean key combination
            key_parts = [key_map.get(k.strip().lower(), k.strip().lower()) for k in keys.split('+')]
            
            # Try multiple methods with retries
            for attempt in range(self.max_retries):
                try:
                    # Clear any stuck keys first
                    self._emergency_key_release()
                    
                    # Method 1: pyautogui hotkey
                    try:
                        pyautogui.hotkey(*key_parts)
                        time.sleep(1.0)
                        if self._verify_keys_released(key_parts):
                            action_data["success"] = True
                            self.action_history.append(action_data)
                            return True
                    except:
                        pass
                        
                    # Method 2: keyboard direct
                    pressed_keys = []
                    try:
                        # Press all keys in order
                        for key in key_parts:
                            keyboard.press(key)
                            pressed_keys.append(key)
                            time.sleep(0.2)
                            if not keyboard.is_pressed(key):
                                raise Exception(f"Failed to press key: {key}")
                                
                        # Hold briefly
                        time.sleep(0.5)
                        
                        # Release in reverse order
                        for key in reversed(pressed_keys):
                            keyboard.release(key)
                            time.sleep(0.2)
                            
                        if self._verify_keys_released(key_parts):
                            action_data["success"] = True
                            self.action_history.append(action_data)
                            return True
                            
                    finally:
                        # Emergency cleanup
                        self._emergency_key_release()
                        
                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                        
            # All attempts failed
            action_data["success"] = False
            self.action_history.append(action_data)
            self.failed_actions.append(action_data)
            return False
            
        except Exception as e:
            self.logger.error(f"Key combination failed: {str(e)}")
            self._emergency_key_release()
            return False
            
    def _execute_run_dialog(self) -> bool:
        """Special handling for Run dialog"""
        try:
            # Try multiple methods in sequence
            methods = [
                # Method 1: pyautogui hotkey
                lambda: (pyautogui.hotkey('win', 'r'), time.sleep(1.0)),
                
                # Method 2: keyboard direct
                lambda: (keyboard.press('windows'), 
                        time.sleep(0.2),
                        keyboard.press('r'),
                        time.sleep(0.2),
                        keyboard.release('r'),
                        time.sleep(0.1),
                        keyboard.release('windows'),
                        time.sleep(1.0)),
                
                # Method 3: Shell command
                lambda: (os.system('rundll32.exe shell32.dll,#61'),
                        time.sleep(1.0)),
                        
                # Method 4: Alternative key sequence
                lambda: (keyboard.press_and_release('windows'),
                        time.sleep(0.5),
                        keyboard.write('run'),
                        time.sleep(0.2),
                        keyboard.press_and_release('enter'),
                        time.sleep(1.0))
            ]
            
            for method in methods:
                try:
                    # Clear any stuck keys first
                    self._emergency_key_release()
                    
                    # Try method
                    method()
                    
                    # Verify Run dialog is open
                    for _ in range(5):  # Check multiple times
                        if self._verify_window_title('Run'):
                            return True
                        time.sleep(0.2)
                        
                except Exception as e:
                    self.logger.error(f"Method failed: {str(e)}")
                    continue
                    
            return False
            
        except Exception as e:
            self.logger.error(f"Run dialog failed: {str(e)}")
            return False
            
    def _verify_window_title(self, expected_title: str) -> bool:
        """Verify active window title"""
        try:
            import win32gui
            current_title = win32gui.GetWindowText(win32gui.GetForegroundWindow())
            return expected_title.lower() in current_title.lower()
        except:
            return False
            
    def _emergency_key_release(self):
        """Emergency release of all potentially stuck keys"""
        try:
            common_keys = ['win', 'alt', 'ctrl', 'shift', 'r']
            for key in common_keys:
                try:
                    keyboard.release(key)
                except:
                    pass
        except:
            pass
            
    def type_text(self, text: str, verify: bool = True, press_enter: bool = True) -> bool:
        """Type text with verification and optional enter press"""
        try:
            self._ensure_delay()
            
            action_data = {"type": "type_text", "text": text, "timestamp": time.time()}
            
            # Try multiple methods with retries
            for attempt in range(self.max_retries):
                try:
                    # Clear any stuck keys
                    self._emergency_key_release()
                    
                    # Method 1: pyautogui typewrite
                    try:
                        pyautogui.typewrite(text, interval=0.1)
                        time.sleep(0.5)
                        if press_enter:
                            pyautogui.press('enter')
                            time.sleep(1.0)  # Wait longer after Enter
                        action_data["success"] = True
                        self.action_history.append(action_data)
                        return True
                    except:
                        pass
                        
                    # Method 2: keyboard write
                    try:
                        for char in text:
                            keyboard.write(char)
                            time.sleep(0.1)
                        time.sleep(0.5)
                        if press_enter:
                            keyboard.press_and_release('enter')
                            time.sleep(1.0)  # Wait longer after Enter
                        action_data["success"] = True
                        self.action_history.append(action_data)
                        return True
                    except:
                        pass
                        
                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                        
            # All attempts failed
            action_data["success"] = False
            self.action_history.append(action_data)
            self.failed_actions.append(action_data)
            return False
            
        except Exception as e:
            self.logger.error(f"Text input failed: {str(e)}")
            return False
            
    def _ensure_delay(self):
        """Ensure minimum delay between actions"""
        elapsed = time.time() - self.last_action_time
        if elapsed < self.min_action_delay:
            time.sleep(self.min_action_delay - elapsed)
            
    def _verify_keys_released(self, keys: list) -> bool:
        """Verify all keys are released"""
        try:
            time.sleep(0.2)  # Wait for key events
            for key in keys:
                if keyboard.is_pressed(key):
                    return False
            return True
        except:
            return False 

    def get_action_history(self):
        """Get history of actions performed"""
        return self.action_history

    def get_failed_actions(self):
        """Get list of failed actions"""
        return self.failed_actions

    def clear_history(self):
        """Clear action history"""
        self.action_history = []
        self.failed_actions = [] 
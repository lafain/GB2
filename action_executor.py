import time
from typing import Dict, Any
import keyboard
import pyautogui
import json
import cv2
import numpy as np
from PIL import ImageGrab
import os

class ActionExecutor:
    def __init__(self, knowledge_manager, logger):
        self.knowledge = knowledge_manager
        self.logger = logger
        self.last_action = None
        self.action_delay = 10.0  # Default 10 seconds
        self.verify_delay = 10.0  # Default 10 seconds
        self.last_screenshot = None
        
        # Initialize pyautogui settings
        pyautogui.PAUSE = 1.0  # Increased default pause
        pyautogui.FAILSAFE = True
        
    def execute(self, action):
        """Execute an action based on its type"""
        try:
            action_type = action.get('type', '').upper()
            params = action.get('params', {})
            
            # Get pre-execution state with delay
            time.sleep(4.0)  # Wait for system to stabilize
            pre_state = self.capture_state()
            self.logger.debug(f"Pre-execution state: {json.dumps(pre_state, indent=2)}")
            
            success = False
            if action_type == 'PRESS':
                keys = params.get('keys', [])
                if isinstance(keys, list):
                    for key in keys:
                        self.logger.debug(f"Pressing key combination: {key}")
                        keyboard.press_and_release(str(key))
                        time.sleep(0.5)
                else:
                    self.logger.debug(f"Pressing single key: {keys}")
                    keyboard.press_and_release(str(keys))
                success = True
                
            elif action_type == 'TYPE':
                text = str(params.get('text', ''))
                self.logger.debug(f"Typing text: {text}")
                keyboard.write(text)
                if text.endswith('\n') or params.get('enter', False):
                    time.sleep(0.1)
                    keyboard.press_and_release('enter')
                success = True
                
            # Wait after action execution
            time.sleep(4.0)  # Wait for action to take effect
            
            # Get post-action state
            post_state = self.capture_state()
            self.logger.debug(f"Post-action state: {json.dumps(post_state, indent=2)}")
            
            # Compare states
            state_changes = self._compare_states(pre_state, post_state)
            self.logger.debug(f"State changes: {json.dumps(state_changes, indent=2)}")
            
            # Verify with retries and recovery
            max_attempts = 3
            for attempt in range(max_attempts):
                verify_result = self.verify_action_result(action, pre_state, post_state)
                
                if verify_result:
                    self.logger.debug(f"Action verified on attempt {attempt + 1}")
                    return True
                    
                self.logger.debug(f"Verification attempt {attempt + 1} failed")
                
                # Try recovery if verification fails
                if attempt < max_attempts - 1:
                    self.logger.debug("Attempting recovery...")
                    if self._attempt_recovery(action, post_state):
                        time.sleep(4.0)  # Wait after recovery
                        post_state = self.capture_state()
                        continue
                        
                time.sleep(4.0)  # Wait before next attempt
                post_state = self.capture_state()
                
            return False
            
        except Exception as e:
            self.logger.error(f"Action execution failed: {str(e)}")
            return False
    
    def validate_action(self, action: Dict[str, Any]) -> bool:
        required_keys = ['type', 'params']
        if not all(k in action for k in required_keys):
            return False
            
        # Check if action is safe based on current state
        return True
    
    def perform_action(self, action: Dict[str, Any]) -> bool:
        action_type = action['type'].upper()
        params = action['params']
        
        if action_type == 'PRESS':
            keys = params.get('keys', '').lower()
            keyboard.press_and_release(keys)
            
        elif action_type == 'TYPE':
            text = params.get('text', '')
            pyautogui.write(text)
            
        elif action_type == 'CLICK':
            x = params.get('x', 0)
            y = params.get('y', 0)
            pyautogui.click(x, y)
            
        elif action_type == 'WAIT':
            duration = params.get('duration', 1)
            time.sleep(duration)
            
        else:
            return False
            
        self.last_action = action
        time.sleep(self.action_delay)
        return True
    
    def capture_state(self) -> Dict[str, Any]:
        try:
            import win32gui
            active_window = win32gui.GetForegroundWindow()
            window_title = win32gui.GetWindowText(active_window)
            
            state = {
                'timestamp': time.time(),
                'active_window': window_title,
                'cursor_position': pyautogui.position(),
                'last_action': self.last_action,
                'paint_open': 'paint' in window_title.lower()
            }
            
            self.logger.debug(f"Current state: {json.dumps(state)}")
            return state
            
        except Exception as e:
            self.logger.error(f"Error capturing state: {str(e)}")
            return {
                'timestamp': time.time(),
                'error': str(e)
            }
    
    def get_screen_info(self) -> Dict[str, Any]:
        try:
            # Get screen size
            screen_width, screen_height = pyautogui.size()
            
            # Take a small screenshot of taskbar area
            taskbar_region = {
                'left': 0,
                'top': screen_height - 100,
                'width': screen_width,
                'height': 100
            }
            
            # Check if Paint is visible in taskbar
            paint_visible = pyautogui.locateOnScreen('resources/paint_icon.png', 
                                                    region=(0, screen_height - 100, screen_width, 100),
                                                    confidence=0.8)
            
            return {
                'screen_size': {'width': screen_width, 'height': screen_height},
                'taskbar_region': taskbar_region,
                'paint_visible': bool(paint_visible)
            }
        except Exception as e:
            self.logger.error(f"Error getting screen info: {str(e)}")
            return {}
    
    def get_active_window(self) -> str:
        # Get the title of the currently active window
        try:
            import win32gui
            return win32gui.GetWindowText(win32gui.GetForegroundWindow())
        except:
            return ""
    
    def learn_transition(self, pre_state: Dict[str, Any], 
                        action: Dict[str, Any], 
                        post_state: Dict[str, Any]):
        # Store state transition in knowledge base
        transition = {
            'pre_state': pre_state,
            'action': action,
            'post_state': post_state,
            'timestamp': time.time()
        }
        self.knowledge.store_transition(transition) 
    
    def verify_action_result(self, action, pre_state, post_state):
        """Verify the result of an action"""
        try:
            # Get current window title
            current_window = self.get_active_window()
            self.logger.debug(f"Verifying window: {current_window}")
            
            # Check verification rules
            verification = action.get('verification', {})
            if verification:
                if verification.get('type') == 'window_title':
                    expected_title = verification.get('value', '')
                    self.logger.debug(f"Checking window title - Expected: {expected_title}, Current: {current_window}")
                    
                    # More flexible title matching
                    if expected_title.lower() in current_window.lower():
                        self.logger.debug("Window title verified")
                        return True
                        
                    self.logger.debug("Window title mismatch")
                    return False
                    
            # Check state changes
            if 'expected_changes' in action:
                for key, expected_value in action['expected_changes'].items():
                    current_value = post_state.get(key)
                    self.logger.debug(f"Checking state change - {key}: expected={expected_value}, current={current_value}")
                    if current_value != expected_value:
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.error(f"Action verification failed: {str(e)}")
            return False
    
    def capture_screenshot(self):
        """Capture and return the current screen state"""
        try:
            screenshot = ImageGrab.grab()
            self.last_screenshot = np.array(screenshot)
            return self.last_screenshot
        except Exception as e:
            self.logger.error(f"Screenshot capture failed: {str(e)}")
            return None
            
    def verify_visual_state(self, expected_state):
        """Verify the screen matches expected visual state"""
        try:
            current = self.capture_screenshot()
            if current is None:
                return False
                
            if 'reference_image' in expected_state:
                ref_image = cv2.imread(expected_state['reference_image'])
                # Compare current screen with reference
                similarity = self.compare_images(current, ref_image)
                return similarity > 0.8  # 80% similarity threshold
                
            if 'expected_elements' in expected_state:
                for element in expected_state['expected_elements']:
                    if not self.find_element_on_screen(element):
                        return False
                return True
                
            return True
            
        except Exception as e:
            self.logger.error(f"Visual verification failed: {str(e)}")
            return False
            
    def find_element_on_screen(self, element):
        """Look for specific UI element on screen"""
        try:
            if 'image' in element:
                return pyautogui.locateOnScreen(element['image'], confidence=0.8)
            elif 'color' in element:
                # Check for presence of specific color
                return self.check_color_presence(element['color'])
            return False
        except Exception as e:
            self.logger.error(f"Element detection failed: {str(e)}")
            return False
            
    def _verify_basic_state(self, action, post_state):
        """Basic state verification"""
        expected_window = action.get('expected_window')
        if expected_window:
            if post_state.get('active_window') != expected_window:
                return False
        return True
    
    def _verify_click_result(self, action, post_state):
        """Verify click action result"""
        expected_window = action.get('expected_window')
        if expected_window:
            if post_state.get('active_window') != expected_window:
                self.logger.debug("Window mismatch for click result")
                return False
        return True
    
    def _verify_type_result(self, action, post_state):
        """Verify type action result"""
        expected_text = action.get('expected_text')
        if expected_text:
            current_text = post_state['last_action'].get('params', {}).get('text', '')
            return current_text == expected_text
        return True
    
    def _verify_press_result(self, action, post_state):
        """Verify press action result"""
        expected_keys = action.get('expected_keys')
        if expected_keys:
            current_keys = post_state['last_action'].get('params', {}).get('keys', '')
            return current_keys == expected_keys
        return True
    
    def compare_images(self, img1, img2):
        """Compare two images and return similarity"""
        return cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED)[0][0]
    
    def check_color_presence(self, color):
        """Check for presence of specific color in the screenshot"""
        # Convert color to BGR format
        bgr_color = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        # Convert screenshot to RGB format
        rgb_screenshot = cv2.cvtColor(self.last_screenshot, cv2.COLOR_BGR2RGB)
        # Check for presence of the color
        return np.any(np.all(rgb_screenshot == bgr_color, axis=-1))
    
    def execute_action(self, action):
        """Execute a single action"""
        try:
            action_type = action.get('type', '').lower()
            
            # Get pre-execution state
            pre_state = self._get_current_state()
            
            # Execute based on action type
            if action_type == 'launch_program':
                success = self._launch_program(action)
            elif action_type == 'keyboard':
                success = self._execute_keyboard_action(action)
            elif action_type == 'mouse':
                success = self._execute_mouse_action(action)
            elif action_type == 'wait':
                success = self._execute_wait_action(action)
            else:
                self.logger.error(f"Unknown action type: {action_type}")
                return False
                
            # Get post-execution state
            post_state = self._get_current_state()
            
            # Store action result
            if success:
                self.knowledge.store_successful_action(action, pre_state, post_state)
            else:
                self.knowledge.store_failed_action(action, pre_state, post_state)
                
            return success
            
        except Exception as e:
            self.logger.error(f"Action execution failed: {str(e)}")
            return False
    
    def _launch_program(self, action):
        """Launch a program using various methods"""
        try:
            program = action.get('program', '')
            if not program:
                return False
                
            # Get program info
            program_info = self._get_program_info(program)
            if not program_info:
                return False
                
            # Try launch commands in order
            for cmd in program_info.get('launch_commands', []):
                try:
                    if cmd.startswith('win+r:'):
                        # Use Run dialog
                        keyboard.press_and_release('win+r')
                        time.sleep(0.5)
                        keyboard.write(cmd.split(':')[1])
                        keyboard.press_and_release('enter')
                    elif cmd.startswith('cmd:'):
                        # Use command prompt
                        os.system(cmd.split(':')[1])
                    else:
                        # Direct command
                        os.system(cmd)
                        
                    # Wait for program window
                    time.sleep(2)
                    if self._verify_program_window(program):
                        return True
                        
                except Exception as e:
                    self.logger.error(f"Launch command failed: {str(e)}")
                    continue
                    
            return False
            
        except Exception as e:
            self.logger.error(f"Program launch failed: {str(e)}")
            return False
    
    def _compare_states(self, pre_state, post_state):
        """Compare two states and return differences"""
        changes = {}
        for key in set(pre_state.keys()) | set(post_state.keys()):
            pre_val = pre_state.get(key)
            post_val = post_state.get(key)
            if pre_val != post_val:
                changes[key] = {
                    'before': pre_val,
                    'after': post_val
                }
        return changes
    
    def _attempt_recovery(self, action, current_state):
        """Attempt to recover from failed action"""
        try:
            action_type = action.get('type', '').upper()
            
            if action_type == 'PRESS' and 'win+r' in str(action.get('params', {}).get('keys', '')):
                # If Run dialog didn't open, try again
                if 'Run' not in current_state.get('window_titles', []):
                    self.logger.debug("Retrying Run dialog...")
                    keyboard.press_and_release('win+r')
                    return True
                    
            elif action_type == 'TYPE' and 'mspaint' in str(action.get('params', {}).get('text', '')):
                # If Paint didn't open, try alternative launch
                if not current_state.get('paint_open', False):
                    self.logger.debug("Trying alternative Paint launch...")
                    keyboard.press_and_release('win+r')
                    time.sleep(1.0)
                    keyboard.write('mspaint')
                    keyboard.press_and_release('enter')
                    return True
                    
            return False
            
        except Exception as e:
            self.logger.error(f"Recovery attempt failed: {str(e)}")
            return False
  
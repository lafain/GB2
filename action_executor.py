import time
from typing import Dict, Any
import keyboard
import pyautogui
import json
import cv2
import numpy as np
from PIL import ImageGrab

class ActionExecutor:
    def __init__(self, knowledge_manager, logger):
        self.knowledge = knowledge_manager
        self.logger = logger
        self.last_action = None
        self.action_delay = 0.5
        self.last_screenshot = None
        
        # Initialize pyautogui settings
        pyautogui.PAUSE = 0.5  # Add delay between actions
        pyautogui.FAILSAFE = True
        
    def execute(self, action: Dict[str, Any], context: Dict[str, Any] = None) -> bool:
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.logger.debug(f"Executing action (attempt {retry_count + 1}): {json.dumps(action)}")
                pre_state = self.capture_state()
                
                if not self.validate_action(action):
                    self.logger.error("Invalid action format")
                    return False
                
                success = self.perform_action(action)
                if not success:
                    retry_count += 1
                    time.sleep(1)  # Wait before retry
                    continue
                    
                time.sleep(self.action_delay)
                
                post_state = self.capture_state()
                if self.verify_action_result(action, pre_state, post_state):
                    self.knowledge.store_successful_action(action, pre_state, post_state)
                    return True
                else:
                    self.knowledge.store_failed_action(action, pre_state, post_state)
                
                retry_count += 1
                
            except Exception as e:
                self.logger.error(f"Action execution failed: {str(e)}")
                retry_count += 1
                
        self.logger.error(f"Action failed after {max_retries} attempts")
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
        """Enhanced verification of action results"""
        try:
            # Basic state verification
            if not self._verify_basic_state(action, post_state):
                return False
                
            # Visual verification if specified
            if 'visual_verification' in action:
                if not self.verify_visual_state(action['visual_verification']):
                    self.logger.error("Visual verification failed")
                    return False
                    
            # Verify specific action types
            if action['type'] == 'CLICK':
                return self._verify_click_result(action, post_state)
            elif action['type'] == 'TYPE':
                return self._verify_type_result(action, post_state)
            elif action['type'] == 'PRESS':
                return self._verify_press_result(action, post_state)
                
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
  
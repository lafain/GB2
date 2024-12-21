import psutil
import pyautogui
import time
import win32gui
import win32con
import json
import os

class ActionVerifier:
    def __init__(self, knowledge_dir="knowledge"):
        self.knowledge_dir = knowledge_dir
        
    def verify_action(self, action_type, params, context=None):
        method_name = f"verify_{action_type}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(params, context)
        return False, "Unknown verification method"
    
    def verify_program_running(self, program_name, context=None):
        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() == program_name.lower():
                return True, f"{program_name} is running"
        return False, f"{program_name} is not running"
    
    def verify_window_exists(self, window_title, context=None):
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if window_title.lower() in title.lower():
                    windows.append(hwnd)
            return True
            
        windows = []
        win32gui.EnumWindows(callback, windows)
        
        if windows:
            return True, f"Window '{window_title}' found"
        return False, f"Window '{window_title}' not found"
    
    def verify_window_active(self, window_title, context=None):
        active_window = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(active_window)
        
        if window_title.lower() in title.lower():
            return True, f"Window '{window_title}' is active"
        return False, f"Window '{window_title}' is not active"
    
    def verify_ui_element_exists(self, element_info, context=None):
        try:
            location = pyautogui.locateOnScreen(
                element_info['image_path'],
                confidence=element_info.get('confidence', 0.9)
            )
            return bool(location), f"UI element {'found' if location else 'not found'}"
        except Exception as e:
            return False, f"Error verifying UI element: {str(e)}"
    
    def verify_file_exists(self, file_path, context=None):
        exists = os.path.exists(file_path)
        return exists, f"File {'exists' if exists else 'does not exist'}"
    
    def verify_pixel_color(self, params, context=None):
        x, y = params['position']
        expected_color = params['color']
        actual_color = pyautogui.pixel(x, y)
        
        matches = all(abs(a - b) < params.get('tolerance', 5) 
                     for a, b in zip(actual_color, expected_color))
        return matches, f"Color {'matches' if matches else 'does not match'}"
    
    def log_verification(self, action_type, result, message):
        log_file = os.path.join(self.knowledge_dir, 'actions', 'verifications.json')
        log_entry = {
            "timestamp": time.time(),
            "action_type": action_type,
            "success": result,
            "message": message
        }
        
        logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = json.load(f)
                
        logs.append(log_entry)
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2) 
    
    def verify_state(self, required_state, context=None):
        """Verify all required states are met before executing an action"""
        if not required_state:
            return True, "No state requirements"
            
        for state_type, state_value in required_state.items():
            if state_type == "window_active":
                success, msg = self.verify_window_active(state_value)
                if not success:
                    return False, f"Required window '{state_value}' not active"
                    
            elif state_type == "program_running":
                success, msg = self.verify_program_running(state_value)
                if not success:
                    return False, f"Required program '{state_value}' not running"
                    
            elif state_type == "desktop_focused":
                success = win32gui.GetForegroundWindow() == win32gui.GetDesktopWindow()
                if not success and state_value:
                    return False, "Desktop is not focused"
                    
            elif state_type == "text_entered":
                success, msg = self.verify_text_entered(context.get('window'), context.get('expected_text'))
                if not success and state_value:
                    return False, msg
                    
        return True, "All state requirements met"

    def verify_text_entered(self, window_title, expected_text):
        """Verify text has been entered in a window"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if window_title.lower() not in win32gui.GetWindowText(hwnd).lower():
                return False, f"Window {window_title} not focused"
                
            # Get text from focused control
            control_text = self.get_focused_control_text(hwnd)
            return control_text == expected_text, f"Expected text '{expected_text}' not found"
            
        except Exception as e:
            return False, f"Error verifying text: {str(e)}" 
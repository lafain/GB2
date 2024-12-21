import cv2
import numpy as np
from PIL import ImageGrab
import json
import os
from datetime import datetime
import time
import pyautogui

class GoalVerifier:
    def __init__(self, logger, knowledge_dir="knowledge", llm=None):
        self.logger = logger
        self.knowledge_dir = knowledge_dir
        self.last_verification = None
        self.llm = llm
        
        # Load cached program info
        self.program_info_cache = {}
        self._load_program_cache()
        
    def _load_program_cache(self):
        """Load cached program information"""
        try:
            cache_dir = os.path.join(self.knowledge_dir, 'programs')
            if os.path.exists(cache_dir):
                for file in os.listdir(cache_dir):
                    if file.endswith('.json'):
                        program_name = file[:-5]  # Remove .json
                        with open(os.path.join(cache_dir, file), 'r') as f:
                            self.program_info_cache[program_name] = json.load(f)
                            
            # Add default Paint info if not present
            if 'paint' not in self.program_info_cache:
                self.program_info_cache['paint'] = {
                    "window_patterns": ["paint", "untitled - paint", "microsoft paint"],
                    "process_names": ["mspaint.exe"],
                    "launch_commands": ["win+r:mspaint", "cmd:mspaint"],
                    "default_state": {
                        "required_windows": ["paint", "untitled - paint"],
                        "required_processes": ["mspaint.exe"]
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Failed to load program cache: {str(e)}")

    def verify_goal_completion(self, goal, current_state, expected_state=None):
        """Comprehensive goal completion verification"""
        try:
            # Update current state
            current_state.update(self._get_current_state())
            
            # Capture current screen state
            screenshot = ImageGrab.grab()
            screen_state = np.array(screenshot)
            
            # Store verification attempt
            verification_data = {
                "goal": goal,
                "timestamp": datetime.now().isoformat(),
                "screen_capture": self._save_screenshot(screen_state),
                "current_state": current_state,
                "expected_state": expected_state
            }
            
            # Perform multi-level verification
            results = {
                "visual_check": self._verify_visual_state(screen_state, goal),
                "state_check": self._verify_state_requirements(current_state, expected_state),
                "goal_specific": self._verify_goal_specific(goal, screen_state)
            }
            
            # Calculate confidence score
            confidence = self._calculate_verification_confidence(results)
            verification_data["confidence"] = confidence
            verification_data["results"] = results
            
            # Added dynamic re-check with longer delay
            if confidence < 0.5:
                self.logger.debug("Very low confidence, waiting and re-checking...")
                time.sleep(10.0)  # Wait 10 seconds for updates
                
                # Update state again
                current_state.update(self._get_current_state())
                new_screenshot = ImageGrab.grab()
                new_screen_state = np.array(new_screenshot)
                
                results["visual_check"] = self._verify_visual_state(new_screen_state, goal)
                results["state_check"] = self._verify_state_requirements(current_state, expected_state)
                results["goal_specific"] = self._verify_goal_specific(goal, new_screen_state)
                
                confidence = self._calculate_verification_confidence(results)
                verification_data["confidence"] = confidence
                verification_data["results"] = results
            
            # Store verification results
            self._store_verification(verification_data)
            
            return confidence > 0.8, verification_data
            
        except Exception as e:
            self.logger.error(f"Goal verification failed: {str(e)}")
            return False, None
            
    def _verify_goal_specific(self, goal, screen_state):
        """Goal-specific verification logic"""
        if "draw" in goal.lower():
            # For drawing goals, check if canvas area has been modified
            return self._verify_drawing_present(screen_state)
        elif "open" in goal.lower():
            # For program launching goals, check window presence
            return self._verify_program_window(goal)
        return True
        
    def _verify_drawing_present(self, screen_state):
        """Verify that drawing exists on canvas"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(screen_state, cv2.COLOR_BGR2GRAY)
            
            # Check for non-white pixels in canvas area
            canvas_area = self._detect_canvas_area(screen_state)
            if canvas_area is None:
                return False
                
            non_white_pixels = np.sum(gray[canvas_area] < 250)
            return non_white_pixels > 1000  # Arbitrary threshold
            
        except Exception as e:
            self.logger.error(f"Drawing verification failed: {str(e)}")
            return False
            
    def _calculate_verification_confidence(self, results):
        """Calculate overall confidence score"""
        weights = {
            "visual_check": 0.4,
            "state_check": 0.3,
            "goal_specific": 0.3
        }
        
        score = 0
        for key, weight in weights.items():
            if results[key]:
                score += weight
                
        return score 

    def _save_screenshot(self, screen_state):
        """Save screenshot to verification directory"""
        try:
            # Create verification directory if it doesn't exist
            verification_dir = os.path.join(self.knowledge_dir, 'verifications')
            if not os.path.exists(verification_dir):
                os.makedirs(verification_dir)
            
            # Generate filename with timestamp
            filename = f"verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(verification_dir, filename)
            
            # Save screenshot
            cv2.imwrite(filepath, screen_state)
            return filepath
            
        except Exception as e:
            self.logger.error(f"Failed to save screenshot: {str(e)}")
            return None

    def _store_verification(self, verification_data):
        """Store verification data"""
        try:
            # Create verification directory if it doesn't exist
            verification_dir = os.path.join(self.knowledge_dir, 'verifications')
            if not os.path.exists(verification_dir):
                os.makedirs(verification_dir)
            
            # Generate filename with timestamp
            filename = f"verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(verification_dir, filename)
            
            # Save verification data
            with open(filepath, 'w') as f:
                json.dump(verification_data, f, indent=2)
            
        except Exception as e:
            self.logger.error(f"Failed to store verification: {str(e)}")

    def _verify_visual_state(self, screen_state, goal):
        """Verify the visual state matches goal requirements"""
        try:
            # Convert screen state to grayscale for processing
            gray = cv2.cvtColor(screen_state, cv2.COLOR_BGR2GRAY)
            
            # Get expected visual patterns for this goal
            expected_patterns = self._load_expected_patterns(goal)
            
            results = {}
            for pattern_name, pattern_data in expected_patterns.items():
                template = cv2.imread(pattern_data['template_path'], 0)
                if template is None:
                    continue
                    
                # Template matching
                res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                
                # Check if match exceeds threshold
                results[pattern_name] = {
                    'matched': max_val >= pattern_data.get('threshold', 0.8),
                    'confidence': max_val,
                    'location': max_loc
                }
                
            return results
            
        except Exception as e:
            self.logger.error(f"Visual state verification failed: {str(e)}")
            return None

    def _load_expected_patterns(self, goal):
        """Load expected visual patterns for goal verification"""
        try:
            patterns_file = os.path.join(self.knowledge_dir, 'patterns', 'visual_patterns.json')
            if os.path.exists(patterns_file):
                with open(patterns_file, 'r') as f:
                    all_patterns = json.load(f)
                    
                # Find patterns matching the goal
                goal_patterns = {}
                for pattern_name, pattern_data in all_patterns.items():
                    if any(keyword in goal.lower() for keyword in pattern_data.get('keywords', [])):
                        goal_patterns[pattern_name] = pattern_data
                        
                return goal_patterns
            return {}
            
        except Exception as e:
            self.logger.error(f"Failed to load patterns: {str(e)}")
            return {}

    def _verify_state_requirements(self, current_state, expected_state):
        """Verify current state meets requirements"""
        try:
            if not expected_state:
                return True
                
            all_requirements_met = True
            
            for key, expected_value in expected_state.items():
                current_value = current_state.get(key)
                self.logger.debug(f"Checking state - {key}: current={current_value}, expected={expected_value}")
                
                if expected_value is None:
                    continue
                    
                # Get program info if needed
                if key == "program_open":
                    # Don't verify program_open=False, as it's not a meaningful state
                    if expected_value is False:
                        continue
                        
                    program_info = self._get_program_info(expected_value)
                    if not program_info:
                        self.logger.error(f"No program info found for: {expected_value}")
                        return False
                        
                    window_patterns = program_info.get('window_patterns', [])
                    process_names = program_info.get('process_names', [])
                    
                    # Check windows and processes
                    window_titles = current_state.get("window_titles", [])
                    processes = current_state.get("processes", [])
                    
                    window_match = any(
                        any(pattern.lower() in title.lower() for pattern in window_patterns)
                        for title in window_titles
                    )
                    
                    process_match = any(
                        any(name.lower() in proc.lower() for name in process_names)
                        for proc in processes
                    )
                    
                    requirement_met = window_match or process_match
                    
                elif key == "window_title":
                    # Skip empty window title checks
                    if not expected_value:
                        continue
                    requirement_met = expected_value.lower() in current_value.lower() if current_value else False
                    
                else:
                    requirement_met = current_value == expected_value
                    
                if not requirement_met:
                    self.logger.debug(f"Requirement not met - {key}: expected={expected_value}")
                    all_requirements_met = False
                    
            return all_requirements_met
            
        except Exception as e:
            self.logger.error(f"State verification failed: {str(e)}")
            return False

    def _detect_canvas_area(self, screen_state):
        """Detect the Paint canvas area"""
        try:
            gray = cv2.cvtColor(screen_state, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Find largest rectangular contour
                canvas = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(canvas)
                return (slice(y, y+h), slice(x, x+w))
            return None
            
        except Exception as e:
            self.logger.error(f"Canvas detection failed: {str(e)}")
            return None

    def _verify_program_window(self, program_info):
        """Verify and position any program window"""
        try:
            import win32gui
            import win32con
            import win32api
            
            # Get program info from LLM if not provided
            if isinstance(program_info, str):
                program_info = self._get_program_info(program_info)
            
            window_patterns = program_info.get('window_patterns', [])
            process_names = program_info.get('process_names', [])
            
            # Find program window
            def find_program_window(hwnd, ctx):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).lower()
                    if any(pattern.lower() in title for pattern in window_patterns):
                        ctx.append(hwnd)
                return True
                
            program_windows = []
            win32gui.EnumWindows(find_program_window, program_windows)
            
            if program_windows:
                hwnd = program_windows[0]
                
                # Get screen dimensions
                screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                
                # Calculate 90% size
                window_width = int(screen_width * 0.9)
                window_height = int(screen_height * 0.9)
                
                # Center position
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
                
                # Position window
                win32gui.ShowWindow(hwnd, win32con.SW_NORMAL)
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    x, y,
                    window_width, window_height,
                    win32con.SWP_SHOWWINDOW
                )
                win32gui.SetForegroundWindow(hwnd)
                
                self.logger.debug(f"Window positioned: {x},{y} {window_width}x{window_height}")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Window verification failed: {str(e)}")
            return False

    def _get_program_info(self, program_name):
        """Get program-specific information"""
        try:
            program_name = program_name.lower()
            
            # Check cache first
            if program_name in self.program_info_cache:
                return self.program_info_cache[program_name]
                
            # Check file system
            program_file = os.path.join(self.knowledge_dir, 'programs', f'{program_name}.json')
            if os.path.exists(program_file):
                with open(program_file, 'r') as f:
                    info = json.load(f)
                    self.program_info_cache[program_name] = info
                    return info
                    
            # Ask LLM if available
            if self.llm:
                prompt = f"""
                Provide information about the program "{program_name}" in JSON format:
                {{
                    "window_patterns": ["list of window title patterns"],
                    "process_names": ["list of process names"],
                    "launch_commands": ["list of ways to launch"],
                    "default_state": {{
                        "required_windows": ["expected window titles"],
                        "required_processes": ["expected process names"]
                    }}
                }}
                """
                
                response = self.llm.generate(prompt)
                if response:
                    info = json.loads(response.get('response', '{}'))
                    
                    # Cache the result
                    self.program_info_cache[program_name] = info
                    os.makedirs(os.path.dirname(program_file), exist_ok=True)
                    with open(program_file, 'w') as f:
                        json.dump(info, f, indent=2)
                        
                    return info
                    
            # Use basic defaults if no other info available
            return {
                "window_patterns": [program_name],
                "process_names": [f"{program_name}.exe"],
                "launch_commands": [f"win+r:{program_name}"],
                "default_state": {
                    "required_windows": [program_name],
                    "required_processes": [f"{program_name}.exe"]
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get program info: {str(e)}")
            return {}

    def _get_current_state(self):
        """Get current system state"""
        try:
            import win32gui
            import win32process
            import psutil
            
            # Get foreground window info
            hwnd = win32gui.GetForegroundWindow()
            window_title = win32gui.GetWindowText(hwnd)
            
            # Get all window titles and handle Paint specifically
            window_titles = []
            paint_hwnd = None
            
            def enum_callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        results.append(title)
                        if any(paint_title in title.lower() for paint_title in ["paint", "untitled", "microsoft paint"]):
                            nonlocal paint_hwnd
                            paint_hwnd = hwnd
                return True
                
            win32gui.EnumWindows(enum_callback, window_titles)
            self.logger.debug(f"Active windows: {window_titles}")
            
            # Position Paint window if found
            if paint_hwnd:
                self._verify_program_window("paint")
            
            state = {
                "active_window": window_title,
                "window_titles": window_titles,
                "timestamp": datetime.now().timestamp(),
                "cursor_position": pyautogui.position()
            }
            
            # Check if Paint is running
            paint_found = False
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    if proc.name().lower() in ['mspaint.exe']:
                        paint_found = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            state["paint_open"] = paint_found
            
            return state
            
        except Exception as e:
            self.logger.error(f"Failed to get current state: {str(e)}")
            return {}

    def _enum_windows(self):
        """Enumerate all windows"""
        try:
            import win32gui
            def callback(hwnd, hwnds):
                if win32gui.IsWindowVisible(hwnd):
                    hwnds.append(hwnd)
                return True
                
            hwnds = []
            win32gui.EnumWindows(callback, hwnds)
            return hwnds
            
        except Exception as e:
            self.logger.error(f"Failed to enumerate windows: {str(e)}")
            return []
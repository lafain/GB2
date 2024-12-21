import cv2
import numpy as np
from PIL import ImageGrab
import json
import os
from datetime import datetime

class GoalVerifier:
    def __init__(self, logger, knowledge_dir="knowledge"):
        self.logger = logger
        self.knowledge_dir = knowledge_dir
        self.last_verification = None
        
    def verify_goal_completion(self, goal, current_state, expected_state=None):
        """Comprehensive goal completion verification"""
        try:
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
            
            # Added dynamic re-check
            if confidence < 0.5:
                self.logger.debug("Very low confidence, forcing re-check with new screenshot")
                new_screenshot = ImageGrab.grab()
                new_screen_state = np.array(new_screenshot)
                results["visual_check"] = self._verify_visual_state(new_screen_state, goal)
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
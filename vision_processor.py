import logging
from typing import Dict, Any
from PIL import Image
import base64
from io import BytesIO
from datetime import datetime
import traceback
import time
import ollama  # Add ollama library
import io
from PIL import ImageGrab

class VisionProcessor:
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.model = "llama3.2-vision"  # Always use this model
        self.client = ollama.Client(host='http://localhost:11434')
        self.is_test_mode = False  # Flag to control validation behavior
        self.last_screenshot = None
        self.last_screenshot_time = 0
        
    def _check_model(self) -> bool:
        """Check if vision model is available"""
        try:
            # First try direct model check
            try:
                self.client.pull(self.model, stream=False)
                self.logger.info(f"Model {self.model} is available")
                return True
            except Exception as pull_e:
                self.logger.debug(f"Pull check failed: {str(pull_e)}")
                
            # Fallback to listing models
            models = self.client.list()
            self.logger.debug(f"Raw models response: {models}")
            
            # Try different ways to extract model names
            model_names = []
            
            if isinstance(models, dict):
                if 'models' in models:
                    models = models['models']
                elif 'name' in models:
                    models = [models['name']]
                    
            if isinstance(models, list):
                for model in models:
                    if isinstance(model, str):
                        model_names.append(model.lower())
                    elif isinstance(model, dict) and 'name' in model:
                        model_names.append(model['name'].lower())
                    elif isinstance(model, (list, tuple)) and len(model) > 0:
                        model_names.append(str(model[0]).lower())
                        
            self.logger.debug(f"Extracted model names: {model_names}")
            
            # Check for our model name (flexible matching)
            target = self.model.lower()
            target_simple = ''.join(c for c in target if c.isalnum())
            
            for name in model_names:
                name_simple = ''.join(c for c in name if c.isalnum())
                if target_simple in name_simple:
                    self.logger.info(f"Found matching model: {name}")
                    self.model = name  # Update to actual model name
                    return True
                    
            self.logger.warning(f"Model {self.model} not found in available models: {model_names}")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to check model availability: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
            
    def _test_model_response(self) -> bool:
        """Test if model gives valid responses"""
        try:
            # Simple test request
            response = self.client.chat(
                model=self.model,
                messages=[{
                    'role': 'user',
                    'content': 'test'
                }]
            )
            
            # Verify response format
            if not response or not hasattr(response, 'message'):
                self.logger.error("Invalid model response format")
                return False
                
            self.logger.debug(f"Test response: {response.message.content[:100]}")
            return True
            
        except Exception as e:
            self.logger.error(f"Model response test failed: {str(e)}")
            return False

    def analyze_screen(self, screenshot: Image.Image, is_test: bool = False, test_string: str = None) -> Dict[str, Any]:
        """Analyze screenshot with vision model"""
        try:
            # Convert screenshot to base64
            img_byte_arr = io.BytesIO()
            screenshot.save(img_byte_arr, format='JPEG')
            img_str = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
            
            # Save debug screenshot with timestamp only during testing
            if is_test:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_file = f"debug_vision_test_{timestamp}.jpg"
                screenshot.save(debug_file)
                self.logger.info(f"Saved debug screenshot to {debug_file}")
                
                # Model verification only during testing
                self.logger.info("Checking if llama3.2-vision is available...")
                if not self._check_model():
                    raise Exception("Vision model not available")
                
                self.logger.info("Testing model response...")
                if not self._test_model_response():
                    raise Exception("Model response test failed")
                    
                self.logger.info("Model check successful")

            # Main vision request
            start_time = time.time()
            try:
                # Use different prompts for test vs regular operation
                if is_test:
                    prompt = '''Look at this screenshot carefully. There is a window with a large text string.
1. What is the exact text string you see in the large font? (Preserve exact case)
2. List all characters you can see, maintaining their exact case.
Just provide the text string and characters, no other description.'''
                else:
                    prompt = '''Look at this screenshot carefully and describe:
1. What windows and applications are open?
2. What is the title of each window?
3. What UI elements (buttons, menus, etc) are visible?
Focus on window titles and interactive elements, not the text content.'''

                response = self.client.chat(
                    model=self.model,
                    messages=[{
                        'role': 'user',
                        'content': prompt,
                        'images': [img_str]
                    }]
                )
                
                elapsed_time = time.time() - start_time
                self.logger.info(f"Got response in {elapsed_time:.1f} seconds")
                
                if not response or not hasattr(response, 'message'):
                    raise Exception("Invalid response from vision model")
                
                description = response.message.content.strip()
                if not description:
                    raise Exception("Empty response from vision model")
                
                # Log raw response for debugging
                self.logger.debug(f"Raw vision response: {description}")
                
                # For test mode, improve string matching
                if is_test and test_string:
                    # Look for exact string matches (case insensitive)
                    import re
                    description_lower = description.lower()
                    test_strings = re.findall(r'[A-Za-z0-9]{10}', description)
                    test_strings_lower = [s.lower() for s in test_strings]
                    
                    self.logger.debug(f"Found strings: {test_strings}")
                    self.logger.debug(f"Found strings (lowercase): {test_strings_lower}")
                    
                    # Check for exact matches and near matches
                    matches = []
                    near_matches = []
                    for s in test_strings:
                        if s == test_string:  # Exact match
                            matches.append(s)
                        elif s.lower() == test_string.lower():  # Case-insensitive match
                            near_matches.append(s)
                    
                    self.logger.debug(f"Exact matches: {matches}")
                    self.logger.debug(f"Case-insensitive matches: {near_matches}")
                    
                    if matches or near_matches:
                        self.logger.info(f"Found matches - Exact: {matches}, Case-insensitive: {near_matches}")
                        # Update description to prioritize the found strings
                        description = f"Test strings found: {', '.join(matches or near_matches)}\n\nFull response: {description}"
                
                analysis = {
                    "description": description,
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                    "screen_size": screenshot.size,
                    "test_results": {
                        "exact_matches": matches,
                        "case_insensitive_matches": near_matches
                    } if is_test else None
                }
                
                self.logger.info("Screen analysis completed")
                self.logger.info(f"Vision analysis: {description[:200]}...")
                
                return analysis
                
            except Exception as e:
                elapsed_time = time.time() - start_time
                self.logger.error(f"Vision analysis failed after {elapsed_time:.1f} seconds: {str(e)}")
                self.logger.error(traceback.format_exc())
                return {
                    "error": str(e),
                    "success": False,
                    "timestamp": datetime.now().isoformat(),
                    "screen_size": screenshot.size
                }
            
        except Exception as e:
            self.logger.error(f"Screen analysis failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {
                "error": str(e),
                "success": False,
                "timestamp": datetime.now().isoformat(),
                "screen_size": screenshot.size if screenshot else None
            }

    def _format_prompt(self, text: str) -> str:
        """Format prompt for vision model"""
        return f"""
        You are a computer vision system analyzing a screenshot.
        Focus on identifying:
        - Window titles and positions
        - UI elements (buttons, menus, etc)
        - Text content
        - Interactive elements
        - Current application state
        
        Question: {text}
        """ 

    def capture_screen(self) -> Dict[str, Any]:
        """Capture screen and analyze with vision model"""
        try:
            # Take screenshot
            screenshot = ImageGrab.grab()
            self.last_screenshot = screenshot
            
            # Check if image needs resizing
            if screenshot.size[0] > 800 or screenshot.size[1] > 600:
                self.logger.info("Resizing large image for better performance")
                screenshot.thumbnail((800, 600), Image.Resampling.LANCZOS)
            
            # Analyze with vision model (no testing)
            start_time = time.time()
            analysis = self.analyze_screen(screenshot, is_test=False)
            
            elapsed = time.time() - start_time
            self.logger.info(f"Got vision response in {elapsed:.1f} seconds")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Screen capture failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"Failed to capture screen: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "screenshot": self.last_screenshot
            } 
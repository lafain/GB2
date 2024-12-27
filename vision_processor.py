import logging
from typing import Dict, Any
from PIL import Image
import base64
from io import BytesIO
from datetime import datetime
import traceback
import time
import ollama  # Add ollama library

class VisionProcessor:
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.model = "llama3.2-vision"  # Always use this model
        self.client = ollama.Client(host='http://localhost:11434')
        self.is_test_mode = False  # Flag to control validation behavior
        
    def analyze_screen(self, screenshot: Image.Image, is_test: bool = False) -> Dict[str, Any]:
        """Analyze screenshot using vision model"""
        try:
            # Save debug image
            debug_path = "debug_vision_test_original.jpg"
            screenshot.save(debug_path)
            self.logger.info(f"Saved original screenshot to {debug_path}")
            
            # Only do validation during tests
            if is_test:
                try:
                    # Quick model check - pull doesn't support timeout
                    self.logger.info(f"Checking if {self.model} is available...")
                    self.client.pull(self.model, stream=False)
                    
                    # Test model with quick chat request
                    self.logger.info("Testing model response...")
                    test = self.client.chat(
                        model=self.model,
                        messages=[{"role": "user", "content": "test"}]
                    )
                    if test and hasattr(test, 'message'):
                        self.logger.info(f"Model check successful")
                    else:
                        raise Exception("Invalid model response")
                        
                except Exception as e:
                    self.logger.error(f"Failed to verify model: {str(e)}")
                    self.logger.error(traceback.format_exc())
                    return {
                        "error": "Failed to access Ollama model",
                        "success": False,
                        "timestamp": datetime.now().isoformat(),
                        "screen_size": screenshot.size
                    }

            # Convert image to base64
            img_buffer = BytesIO()
            screenshot.save(img_buffer, format="JPEG", quality=95)
            img_str = base64.b64encode(img_buffer.getvalue()).decode()
            
            # Log image details
            self.logger.debug(f"Image size: {screenshot.size}")
            
            # Only do basic vision test during test mode
            if is_test:
                try:
                    self.logger.info("Testing basic vision capability...")
                    test_response = self.client.chat(
                        model=self.model,
                        messages=[{
                            'role': 'user',
                            'content': 'Can you see and read any text in this screenshot? Just answer yes or no.',
                            'images': [img_str]
                        }]
                    )
                    self.logger.info(f"Basic vision test response: {test_response.message.content}")
                    
                    if "no" in test_response.message.content.lower():
                        self.logger.warning("Basic vision test failed with original size, trying resized...")
                        img_size = screenshot.size
                        if img_size[0] > 800 or img_size[1] > 600:
                            self.logger.info("Resizing large image for better performance")
                            aspect = img_size[0] / img_size[1]
                            new_width = min(800, img_size[0])
                            new_height = int(new_width / aspect)
                            resized = screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            
                            resized.save("debug_vision_test_resized.jpg")
                            self.logger.info(f"Saved resized debug image (new size: {resized.size})")
                            
                            img_buffer = BytesIO()
                            resized.save(img_buffer, format="JPEG", quality=95)
                            img_str = base64.b64encode(img_buffer.getvalue()).decode()
                
                except Exception as e:
                    self.logger.error(f"Basic vision test failed: {str(e)}")
                    self.logger.error(traceback.format_exc())

            # Main vision request
            start_time = time.time()
            try:
                self.logger.info("Sending vision request...")
                response = self.client.chat(
                    model=self.model,
                    messages=[{
                        'role': 'user',
                        'content': 'What text and UI elements do you see in this image? Describe the interface and any important details.',
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
                
                analysis = {
                    "description": description,
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                    "screen_size": screenshot.size
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
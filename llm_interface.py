import requests
import json
import base64
import os
from debug_logger import DebugLogger

class LLMInterface:
    def __init__(self, base_url=None, model=None):
        self.base_url = base_url or os.getenv("LLM_API_URL", "http://localhost:11434/api/generate")
        self.model = model or os.getenv("LLM_MODEL", "llama3.2-vision:latest")
        self.logger = DebugLogger("llm")
        self.timeout = 300  # 5 minutes timeout
        self.max_retries = 3
        
    def get_response(self, prompt, image_path=None):
        """Backwards compatible method that calls generate"""
        try:
            context = {}
            if image_path:
                self.logger.debug(f"Including image: {image_path}")
                with open(image_path, "rb") as img_file:
                    base64_image = base64.b64encode(img_file.read()).decode('utf-8')
                    context["images"] = [base64_image]
                    
            response = self.generate(prompt, context)
            if response:
                return response.get('response'), None
            return None, "Failed to generate response"
            
        except Exception as e:
            self.logger.error(f"Error in get_response: {str(e)}")
            return None, str(e)

    def generate(self, prompt, context=None, timeout=None):
        """Generate response from LLM with timeout"""
        self.logger.debug(f"Preparing request to {self.base_url}")
        self.logger.debug(f"Using model: {self.model}")
        self.logger.debug(f"Prompt: {prompt[:200]}...")
        
        timeout = timeout or self.timeout
        
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            
            if context:
                payload.update(context)
                
            response = requests.post(
                self.base_url,
                json=payload,
                timeout=timeout
            )
            
            self.logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    self.logger.error(f"LLM error: {result['error']}")
                    return None
                self.logger.debug(f"Response received: {str(result)[:200]}...")
                return result
            else:
                self.logger.error(f"Request failed with status {response.status_code}")
                return None
                
        except requests.Timeout:
            self.logger.error(f"Request timed out after {timeout} seconds")
            return None
        except Exception as e:
            self.logger.error(f"Request failed: {str(e)}")
            return None
    
    def parse_json_response(self, response):
        try:
            # First try to find JSON block in markdown
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_str = re.search(r'\{.*\}', response, re.DOTALL).group()
                
            parsed = json.loads(json_str)
            self.logger.debug(f"Successfully parsed JSON: {str(parsed)[:200]}...")
            return parsed
        except (json.JSONDecodeError, AttributeError) as e:
            self.logger.error(f"JSON parsing error: {str(e)}")
            self.logger.error(f"Raw response: {response}")
            return None
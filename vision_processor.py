import logging
from typing import Dict, Any
from PIL import Image
import base64
from io import BytesIO
import requests
import json
from datetime import datetime

class VisionProcessor:
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.model = config.get("model", "llama3.2-vision")
        self.api_url = config.get("api_url", "http://localhost:11434/api/generate")
        
    def analyze_screen(self, screenshot: Image.Image) -> Dict[str, Any]:
        """Analyze screenshot using vision model"""
        try:
            # Convert image to base64
            img_buffer = BytesIO()
            screenshot.save(img_buffer, format="JPEG")
            img_str = base64.b64encode(img_buffer.getvalue()).decode()
            
            # Prepare prompt with proper format for Ollama
            system_prompt = """You are a computer vision system analyzing screenshots to help an AI agent control the computer.
Your role is to provide detailed, actionable descriptions of what you see."""

            vision_prompt = """Analyze this screenshot and describe what you see.
Focus on:
1. Window titles and their locations
2. UI elements (buttons, menus, toolbars)
3. Mouse cursor position if visible
4. Any text content
5. Interactive elements and their locations
6. Current application state

Describe locations using pixel coordinates when possible.
Be specific about positions and sizes.

Format your response as a clear, structured description that the agent can use to make decisions."""

            # Make API request
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": vision_prompt},
                        {"role": "user", "content": "<image>", "images": [img_str]}
                    ],
                    "stream": False
                },
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            description = result.get("response", "").strip()
            
            analysis = {
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "success": True,
                "screen_size": screenshot.size,
                "elements": []  # List of detected UI elements
            }
            
            self.logger.info("Screen analysis completed")
            self.logger.info(f"Vision analysis: {description[:200]}...")
            self.logger.debug(f"Screen size: {analysis['screen_size']}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Screen analysis failed: {str(e)}")
            if isinstance(e, requests.exceptions.RequestException):
                self.logger.error(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response'}")
            return {
                "error": str(e),
                "success": False,
                "timestamp": datetime.now().isoformat(),
                "screen_size": screenshot.size if screenshot else None,
                "elements": []
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
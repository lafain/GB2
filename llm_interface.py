from typing import Dict, Any, Tuple, Optional
import json
import requests
import base64
from PIL import Image
import io
import logging
from io import BytesIO

class LLMInterface:
    """Handles all LLM interactions with Ollama's Llama 3.2 Vision API"""
    
    def __init__(self, logger: logging.Logger, vision_processor):
        self.logger = logger
        self.vision_processor = vision_processor
        self.conversation_history = []
        self.api_url = "http://localhost:11434/api/generate"
        self.model = "llama3.2-vision"

    def get_next_action(self, goal: str, state: Dict[str, Any], vision_info: Dict[str, Any]) -> Dict[str, Any]:
        """Get next action based on current state and vision info"""
        try:
            # Format prompt as single string for /generate endpoint
            prompt = f"""You are an AI agent that can control the computer to achieve goals.
Your role is to analyze the current state and decide on the next action to take.

Current goal: {goal}

Current screen state:
{vision_info.get('description', 'No screen description available')}

Current system state:
- Active window: {state.get('active_window', {}).get('title', 'Unknown')}
- Mouse position: {state.get('mouse_position', 'Unknown')}
- Screen size: {vision_info.get('screen_size', 'Unknown')}

Based on this information, what action should I take next?

Available actions:
1. click (x, y) - Click at coordinates
2. type (text) - Type text
3. press (key) - Press a keyboard key
4. move (x, y) - Move mouse
5. drag (start_x, start_y, end_x, end_y) - Drag mouse
6. wait (seconds) - Wait
7. focus_window (title) - Focus window
8. stop - Stop if goal complete

Respond with ONLY the action in this format:
<action_name>
param1: value1
param2: value2

Example:
click
x: 100
y: 200

Your response:"""

            self.logger.debug(f"Sending prompt to LLM...")
            
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get("response", "").strip()
            self.logger.debug(f"Raw LLM response: {response_text}")
            
            if not response_text:
                self.logger.error("Empty response from LLM")
                return {"function_name": "stop", "error": "Empty response from LLM"}
                
            action = self._parse_action(response_text)
            self.logger.debug(f"Parsed action: {action}")
            
            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant", 
                "content": response_text
            })
            
            return action
            
        except Exception as e:
            self.logger.error(f"Failed to get next action: {str(e)}")
            return {"error": str(e), "success": False}

    def _parse_action(self, content: str) -> Dict[str, Any]:
        """Parse LLM response into action dictionary"""
        try:
            if not content or "ERROR" in content.upper() or "FAIL" in content.upper():
                return {"function_name": "stop", "error": content or "Empty response"}
                
            # Split into lines and remove empty lines
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            if not lines:
                return {"function_name": "stop", "error": "No action specified"}
                
            # First non-empty line is the action name
            action = {
                "function_name": lines[0].strip(),
                "parameters": {}
            }
            
            # Parse parameters from remaining lines
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    # Convert numeric values
                    value = value.strip()
                    try:
                        if "." in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass  # Keep as string if not numeric
                    action["parameters"][key.strip()] = value
                    
            self.logger.debug(f"Parsed action: {action}")
            return action
            
        except Exception as e:
            self.logger.error(f"Failed to parse action: {str(e)}")
            return {"function_name": "stop", "error": f"Failed to parse action: {str(e)}"}

    def add_action_result(self, result: dict):
        """Add action result to conversation history"""
        if result:
            self.conversation_history.append({
                "role": "system",
                "content": f"Action result: {json.dumps(result, indent=2)}"
            })

    def cleanup(self):
        """Clean up resources"""
        self.conversation_history.clear()

    def _format_prompt(self, context: Dict[str, Any]) -> str:
        """Format context into prompt for LLM"""
        return f"""You are an AI agent that can see and interact with the computer screen.
Current goal: {context['goal']}

Current state:
- Active window: {context['current_state'].get('active_window', {}).get('title', 'None')}
- Mouse position: {context['current_state'].get('mouse_position', 'Unknown')}
- Time: {context['current_state'].get('timestamp', 'Unknown')}

Screen analysis:
{context['vision_info'].get('description', 'No screen analysis available')}

Screen size: {context['vision_info'].get('screen_size', 'Unknown')}
UI elements detected: {len(context['vision_info'].get('elements', []))}

Based on this information, what action should I take next?
Respond with an action in this format:
<action_name>
param1: value1
param2: value2

Available actions:
- click (x, y)
- type (text)
- press (key)
- move (x, y)
- drag (start_x, start_y, end_x, end_y)
- wait (seconds)
- focus_window (title)
- stop (if goal is complete or impossible)

Example response:
click
x: 100
y: 200

Your response:
"""

    def get_initial_action(self, goal: str) -> Dict[str, Any]:
        """Get initial action based on goal"""
        if "paint" in goal.lower():
            return {
                "function_name": "press",
                "parameters": {
                    "key": "win+r"  # Open Run dialog
                }
            }
        return None
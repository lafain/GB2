from typing import Dict, Any, Tuple, Optional
import json
import requests
import base64
from PIL import Image
import io
import logging
from io import BytesIO
import traceback
import ollama

class LLMInterface:
    """Handles all LLM interactions with Ollama's Llama 3.2 Vision API"""
    
    def __init__(self, logger: logging.Logger, vision_processor):
        self.logger = logger
        self.vision_processor = vision_processor
        self.conversation_history = []
        self.api_url = "http://localhost:11434/api/generate"
        self.model = "llama3.2-vision"
        self.client = ollama.Client(host='http://localhost:11434')  # Initialize client

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

    def _parse_action(self, action_text: str) -> Dict[str, Any]:
        """Parse action text into structured format"""
        try:
            lines = action_text.strip().split('\n')
            if not lines:
                return {"error": "Empty action text"}
            
            # First line is the function name
            function_name = lines[0].strip().lower()
            
            # Parse parameters
            parameters = {}
            for line in lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    # Convert numeric values
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass
                    parameters[key] = value
                    
            self.logger.debug(f"Parsed action: {function_name} with params: {parameters}")
            
            return {
                "function_name": function_name,
                "parameters": parameters
            }
            
        except Exception as e:
            self.logger.error(f"Action parsing failed: {str(e)}")
            return {"error": f"Failed to parse action: {str(e)}"}

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

    def analyze_and_plan(self, vision_output: str, goal: str) -> Dict[str, Any]:
        """Analyze vision output and plan next action"""
        try:
            prompt = f"""You are an AI agent that controls a computer to accomplish tasks.
Current goal: "{goal}"

Latest screen analysis:
{vision_output}

Available actions:
- focus_window(title): Focus a window with given title
- launch_program(name): Launch a program by name
- type_text(text): Type text
- press_key(key): Press a keyboard key
- click_element(element): Click on a UI element
- move_mouse(x, y): Move mouse to coordinates

Think through this step by step:
1. What program(s) do you need for this task?
2. Are those programs open (visible in the screen analysis)?
3. If not, you need to launch them first
4. What action will make the most progress toward the goal?

Return a JSON response with:
{
    "reasoning": "Your step-by-step thought process",
    "required_programs": ["list", "of", "needed", "programs"],
    "next_action": {
        "action": "action_name",
        "params": {"param1": "value1"}
    }
}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            try:
                result = json.loads(response.choices[0].message.content)
                self.logger.debug(f"Planning result: {result}")
                return result
            except json.JSONDecodeError:
                self.logger.error("Failed to parse LLM response as JSON")
                return None

        except Exception as e:
            self.logger.error(f"Planning failed: {str(e)}")
            return None

    def plan_action(self, goal: str, vision_description: str) -> Dict[str, Any]:
        """Plan next action based on goal and current screen state"""
        try:
            prompt = f"""You are an AI agent controlling a computer to achieve a goal.
Current goal: {goal}

Current screen state:
{vision_description}

Think through this step by step:
1. What program(s) do you need for this task?
2. Are those programs open (visible in the screen analysis)?
3. If not, you need to launch them first using launch_program
4. What SINGLE action will make the most progress toward the goal?

Available actions:
1. click (x: int, y: int) - Click at coordinates
2. type (text: str) - Type text
3. press (key: str) - Press a keyboard key (e.g., "win+r" to open Run dialog)
4. move (x: int, y: int) - Move mouse
5. drag (start_x: int, start_y: int, end_x: int, end_y: int) - Drag mouse
6. wait (seconds: int) - Wait
7. focus_window (title: str) - Focus window
8. launch_program (name: str) - Launch program
9. stop - Stop if goal complete

Respond with ONLY the action in this format:
<action_name>
param1: value1
param2: value2

Example responses:
launch_program
name: paint

press
key: win+r

type
text: paint

click
x: 100
y: 200"""

            self.logger.debug(f"Sending action planning request to LLM at {self.api_url}")
            
            # Fixed URL construction - using self.api_url directly since it already contains /api/generate
            response = requests.post(
                self.api_url,  # Already contains /api/generate
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            self.logger.debug(f"Got response with status code: {response.status_code}")
            response.raise_for_status()
            
            result = response.json()
            self.logger.debug(f"Raw response: {result}")
            
            action_text = result.get("response", "").strip()
            if not action_text:
                self.logger.error("Empty response from LLM")
                return {"error": "Empty response from LLM"}
            
            self.logger.debug(f"Raw action response:\n{action_text}")
            action = self._parse_action(action_text)
            self.logger.debug(f"Parsed action: {action}")
            
            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": action_text
            })
            
            return action

        except Exception as e:
            self.logger.error(f"Action planning failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {"error": str(e)}
from typing import Dict, Any, Tuple, Optional
import json

class LLMInterface:
    """Handles all LLM interactions"""
    
    def __init__(self, model="gpt-4-vision-preview", logger=None):
        self.model = model
        self.conversation_history = []
        self.system_prompt = None
        self.current_step = 0
        self.logger = logger
        
        # Test sequence for drawing a house
        self.test_actions = [
            {
                "thought": "First, I need to open Paint and maximize it for consistent coordinates",
                "action": {
                    "function_name": "launch_program",
                    "function_params": {
                        "program_name": "paint"
                    }
                }
            },
            {
                "thought": "Now I need to verify the window is active and maximize it",
                "action": {
                    "function_name": "get_window_info",
                    "function_params": {
                        "title": "Untitled - Paint"
                    }
                }
            },
            {
                "thought": "I need to select the pencil tool from the Brushes section",
                "action": {
                    "function_name": "click",
                    "function_params": {
                        "x": 250,  # Adjusted for Brushes section
                        "y": 80,
                        "relative": True
                    }
                }
            },
            {
                "thought": "Starting to draw the base of the house - bottom left corner",
                "action": {
                    "function_name": "click",
                    "function_params": {
                        "x": 400,
                        "y": 500,
                        "relative": True
                    }
                }
            },
            {
                "thought": "Drawing the bottom line of the house",
                "action": {
                    "function_name": "drag_mouse",
                    "function_params": {
                        "start_x": 400,
                        "start_y": 500,
                        "end_x": 600,
                        "end_y": 500,
                        "relative": True
                    }
                }
            },
            {
                "thought": "Drawing the right wall",
                "action": {
                    "function_name": "drag_mouse",
                    "function_params": {
                        "start_x": 600,
                        "start_y": 500,
                        "end_x": 600,
                        "end_y": 300,
                        "relative": True
                    }
                }
            },
            {
                "thought": "Drawing the left wall",
                "action": {
                    "function_name": "drag_mouse",
                    "function_params": {
                        "start_x": 400,
                        "start_y": 500,
                        "end_x": 400,
                        "end_y": 300,
                        "relative": True
                    }
                }
            },
            {
                "thought": "Drawing the roof - left side",
                "action": {
                    "function_name": "drag_mouse",
                    "function_params": {
                        "start_x": 400,
                        "start_y": 300,
                        "end_x": 500,
                        "end_y": 200,
                        "relative": True
                    }
                }
            },
            {
                "thought": "Drawing the roof - right side",
                "action": {
                    "function_name": "drag_mouse",
                    "function_params": {
                        "start_x": 500,
                        "start_y": 200,
                        "end_x": 600,
                        "end_y": 300,
                        "relative": True
                    }
                }
            }
        ]

    def start_conversation(self, system_prompt: str, initial_goal: str) -> bool:
        """Initialize conversation with system prompt and goal"""
        self.system_prompt = system_prompt
        self.conversation_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_goal}
        ]
        return True
        
    def _generate_response(self) -> str:
        """Generate response from LLM"""
        try:
            if self.current_step < len(self.test_actions):
                response = self.test_actions[self.current_step]
                self.current_step += 1
                if self.logger:
                    self.logger.debug(f"Generated action {self.current_step}/{len(self.test_actions)}")
                return response
                
            if self.logger:
                self.logger.info("House drawing sequence completed")
            return None
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error generating response: {str(e)}")
            return None

    def get_next_action(self):
        """Get next thought and action from LLM"""
        try:
            response = self._generate_response()
            if response:
                return response["thought"], response["action"]
            return None, None
            
        except Exception as e:
            print(f"Error getting next action: {str(e)}")
            return None, None
            
    def add_action_result(self, result: Dict[str, Any]):
        """Add action result to conversation history"""
        self.conversation_history.append({
            "role": "user", 
            "content": f"Action_Response: {json.dumps(result)}"
        })
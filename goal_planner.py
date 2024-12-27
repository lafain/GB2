import json
import os
from datetime import datetime
from llm_interface import LLMInterface
from debug_logger import DebugLogger
from context_manager import ContextManager
from typing import List, Dict, Any, Optional

class GoalPlanner:
    def __init__(self, knowledge_dir="knowledge"):
        self.knowledge_dir = knowledge_dir
        self.ensure_knowledge_structure()
        self.logger = DebugLogger("goal_planner")
        self.llm = LLMInterface()
        self.current_plan = None
        self.current_step = 0
        self.retries = 0
        self.max_retries = 3
        self.context_manager = ContextManager(knowledge_dir)

    def ensure_knowledge_structure(self):
        # Create main knowledge directory
        if not os.path.exists(self.knowledge_dir):
            os.makedirs(self.knowledge_dir)
            
        # Create subdirectories for different types of knowledge
        subdirs = ['goals', 'actions', 'errors', 'context', 'success_patterns']
        for subdir in subdirs:
            path = os.path.join(self.knowledge_dir, subdir)
            if not os.path.exists(path):
                os.makedirs(path)
    
    def break_down_goal(self, goal):
        """Break down a goal into executable steps with retry logic and fallback"""
        try:
            # Reset state
            self.reset_plan()
            self.retries = 0
            
            while self.retries < self.max_retries:
                try:
                    prompt = self._create_planning_prompt(goal)
                    print(f"Planning prompt: {prompt}")  # Debug print
                    response = self.llm.generate(prompt)
                    print(f"LLM response: {response}")  # Debug print
                    
                    if response and isinstance(response, dict) and 'steps' in response:
                        steps = self._validate_steps(response['steps'])
                        if steps:
                            self.current_plan = steps
                            self.current_step = 0
                            self.logger.info(f"Successfully created plan with {len(steps)} steps")
                            return steps
                            
                    self.retries += 1
                    self.logger.warning(f"Invalid response from LLM (attempt {self.retries}/{self.max_retries})")
                    
                except Exception as e:
                    self.retries += 1
                    self.logger.error(f"Error in plan generation (attempt {self.retries}/{self.max_retries}): {str(e)}")
                    
            # If all retries failed, use fallback
            self.logger.warning("All attempts failed, using fallback plan")
            fallback_plan = self.create_fallback_steps(goal)
            print(f"Fallback plan: {fallback_plan}")  # Debug print
            if fallback_plan:
                self.current_plan = fallback_plan
                self.current_step = 0
                self.logger.info(f"Created fallback plan with {len(fallback_plan)} steps")
                return fallback_plan
            else:
                self.logger.error("Failed to create fallback plan")
                return None
            
        except Exception as e:
            self.logger.error(f"Critical error in break_down_goal: {str(e)}")
            return None

    def create_fallback_steps(self, goal: str) -> List[Dict[str, Any]]:
        """Create a simple fallback plan based on keywords in the goal."""
        fallback_steps = []
        
        if "paint" in goal.lower():
            fallback_steps.extend([
                {
                    "description": "Open the Run dialog",
                    "action": {"type": "PRESS", "params": {"keys": "win+r"}},
                    "verification": {"type": "check_window", "params": {"title": "Run"}}
                },
                {
                    "description": "Type 'mspaint' and press Enter",
                    "action": {"type": "TYPE", "params": {"text": "mspaint", "enter": True}},
                    "verification": {"type": "check_window", "params": {"title": "Paint"}}
                }
            ])
            
            if "draw" in goal.lower():
                fallback_steps.append(
                    {
                        "description": "Draw on the canvas",
                        "action": {"type": "DRAW", "params": {}},
                        "verification": {"type": "check_drawing", "params": {}}
                    }
                )
                
        elif "notepad" in goal.lower():
            fallback_steps.extend([
                {
                    "description": "Open the Run dialog",
                    "action": {"type": "PRESS", "params": {"keys": "win+r"}},
                    "verification": {"type": "check_window", "params": {"title": "Run"}}
                },
                {
                    "description": "Type 'notepad' and press Enter",
                    "action": {"type": "TYPE", "params": {"text": "notepad", "enter": True}},
                    "verification": {"type": "check_window", "params": {"title": "Notepad"}}
                }
            ])
            
        else:
            fallback_steps.append(
                {
                    "description": "Generic action",
                    "action": {"type": "WAIT", "params": {"duration": 1}},
                    "verification": {}
                }
            )
            
        return fallback_steps
    
    def store_goal_breakdown(self, goal, steps):
        # Store in knowledge base for future reference
        breakdown_file = os.path.join(self.knowledge_dir, 'goals', 'breakdowns.json')
        entry = {
            "goal": goal,
            "steps": steps,
            "timestamp": datetime.now().isoformat(),
            "success": None  # To be updated when goal completes
        }
        
        breakdowns = []
        if os.path.exists(breakdown_file):
            with open(breakdown_file, 'r') as f:
                breakdowns = json.load(f)
                
        breakdowns.append(entry)
        
        with open(breakdown_file, 'w') as f:
            json.dump(breakdowns, f, indent=2)
    
    def log_error(self, error_info):
        errors_file = os.path.join(self.knowledge_dir, 'errors', 'error_log.json')
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error": str(error_info.get('error')),
            "context": error_info.get('context'),
            "solution": error_info.get('solution'),
            "goal": error_info.get('goal')
        }
        
        errors = []
        if os.path.exists(errors_file):
            with open(errors_file, 'r') as f:
                errors = json.load(f)
                
        errors.append(error_entry)
        
        with open(errors_file, 'w') as f:
            json.dump(errors, f, indent=2)
    
    def log_success(self, success_info):
        success_file = os.path.join(self.knowledge_dir, 'success_patterns', 'successes.json')
        success_entry = {
            "timestamp": datetime.now().isoformat(),
            "goal": success_info.get('goal'),
            "steps_taken": success_info.get('steps'),
            "verification_method": success_info.get('verification'),
            "context": success_info.get('context')
        }
        
        successes = []
        if os.path.exists(success_file):
            with open(success_file, 'r') as f:
                successes = json.load(f)
                
        successes.append(success_entry)
        
        with open(success_file, 'w') as f:
            json.dump(successes, f, indent=2)
    
    def extract_keywords(self, text):
        # Use ContextManager's keyword extraction
        from context_manager import ContextManager
        cm = ContextManager(self.knowledge_dir)
        return cm.extract_keywords(text)
    
    def adapt_pattern_to_goal(self, pattern_steps, goal):
        # Customize pattern steps for this specific goal
        adapted_steps = []
        for step in pattern_steps:
            adapted_step = step.copy()
            adapted_step['description'] = adapted_step['description'].replace(
                '{goal}', goal
            )
            adapted_steps.append(adapted_step)
        return adapted_steps 
    
    def log_message(self, message):
        if hasattr(self, 'logger'):
            self.logger.info(message)
        else:
            print(f"GoalPlanner: {message}")  # Fallback if logger not initialized
    
    def load_goal_context(self, goal):
        """Load relevant context files based on goal keywords"""
        context = {}
        try:
            keywords = self.extract_keywords(goal)
            for keyword in keywords:
                context_file = os.path.join(self.knowledge_dir, 'context', f'{keyword}.json')
                if os.path.exists(context_file):
                    with open(context_file, 'r') as f:
                        context[keyword] = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading context: {str(e)}")
        return context
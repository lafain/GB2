import json
import os
from datetime import datetime
from llm_interface import LLMInterface

class GoalPlanner:
    def __init__(self, knowledge_dir="knowledge"):
        self.knowledge_dir = knowledge_dir
        self.ensure_knowledge_structure()
        # Initialize logger
        from debug_logger import DebugLogger
        self.logger = DebugLogger("goal_planner")
        self.llm = LLMInterface()
        
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
        try:
            # Load context for the goal
            context = self.load_goal_context(goal)
            
            prompt = f"""You are an AI agent that controls a computer to accomplish tasks.
Your goal: "{goal}"

Context about available actions:
- You can launch programs using keyboard shortcuts
- You can type text
- You can move and click the mouse
- You can wait for specific durations

Return ONLY a JSON object with this exact structure:
{{
    "steps": [
        {{
            "name": "descriptive_name",
            "description": "what this step does",
            "actions": [
                {{
                    "type": "PRESS|TYPE|CLICK|WAIT",
                    "params": {{
                        // Parameters specific to action type
                    }},
                    "expected_result": "what should happen"
                }}
            ],
            "verification": "how to verify step completed",
            "required_state": {{
                "program_open": "name of required program",
                "window_title": "expected window title"
            }}
        }}
    ]
}}
Do not include ANY explanatory text - ONLY the JSON object."""

            response, error = self.llm.get_response(prompt)
            if error:
                self.logger.error(f"LLM Error: {error}")
                return None

            plan = self.llm.parse_json_response(response)
            if not plan or 'steps' not in plan:
                self.logger.error("Invalid response from LLM")
                return None

            # Add current_step_index to plan
            plan['current_step_index'] = 0
            
            self.store_goal_breakdown(goal, plan)
            return plan

        except Exception as e:
            self.logger.error(f"Error breaking down goal: {str(e)}")
            return None
    
    def create_fallback_steps(self, goal):
        return [
            {
                "name": "analyze_goal",
                "description": f"Analyze requirements for: {goal}",
                "verification": "requirements_understood"
            }
        ]
    
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
import json
import os
from datetime import datetime
import shutil

class KnowledgeManager:
    def __init__(self, knowledge_dir="knowledge"):
        self.knowledge_dir = knowledge_dir
        self.ensure_knowledge_structure()
        
    def store_successful_action(self, action, pre_state, post_state):
        """Store successful action and its state transition"""
        try:
            success_file = os.path.join(self.knowledge_dir, 'actions', 'successful_actions.json')
            entry = {
                "action": action,
                "pre_state": pre_state,
                "post_state": post_state,
                "timestamp": datetime.now().isoformat()
            }
            
            successes = []
            if os.path.exists(success_file):
                with open(success_file, 'r') as f:
                    successes = json.load(f)
                    
            successes.append(entry)
            
            with open(success_file, 'w') as f:
                json.dump(successes, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to store successful action: {str(e)}")
    
    def store_failed_action(self, action, pre_state, post_state):
        """Store failed action attempt"""
        try:
            failures_file = os.path.join(self.knowledge_dir, 'actions', 'failed_actions.json')
            entry = {
                "action": action,
                "pre_state": pre_state,
                "post_state": post_state,
                "timestamp": datetime.now().isoformat()
            }
            
            failures = []
            if os.path.exists(failures_file):
                with open(failures_file, 'r') as f:
                    failures = json.load(f)
                    
            failures.append(entry)
            
            with open(failures_file, 'w') as f:
                json.dump(failures, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to store failed action: {str(e)}")
    
    def get_alternative_actions(self, failed_action, current_state):
        """Get alternative actions based on similar past situations"""
        try:
            # Load successful actions
            success_file = os.path.join(self.knowledge_dir, 'actions', 'successful_actions.json')
            if not os.path.exists(success_file):
                return []
                
            with open(success_file, 'r') as f:
                successes = json.load(f)
                
            # Find similar situations
            alternatives = []
            for entry in successes:
                if self._similar_states(entry['pre_state'], current_state):
                    alternatives.append(entry['action'])
                    
            return alternatives
            
        except Exception as e:
            self.logger.error(f"Failed to get alternatives: {str(e)}")
            return []
    
    def store_state_transition(self, state):
        """Store state transition for learning"""
        try:
            transitions_file = os.path.join(self.knowledge_dir, 'states', 'transitions.json')
            entry = {
                "state": state,
                "timestamp": datetime.now().isoformat()
            }
            
            transitions = []
            if os.path.exists(transitions_file):
                with open(transitions_file, 'r') as f:
                    transitions = json.load(f)
                    
            transitions.append(entry)
            
            with open(transitions_file, 'w') as f:
                json.dump(transitions, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to store state transition: {str(e)}")
    
    def store_verification_failure(self, action, state):
        """Store verification failure for learning"""
        try:
            failures_file = os.path.join(self.knowledge_dir, 'verifications', 'failures.json')
            entry = {
                "action": action,
                "state": state,
                "timestamp": datetime.now().isoformat()
            }
            
            failures = []
            if os.path.exists(failures_file):
                with open(failures_file, 'r') as f:
                    failures = json.load(f)
                    
            failures.append(entry)
            
            with open(failures_file, 'w') as f:
                json.dump(failures, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to store verification failure: {str(e)}")
    
    def store_failed_attempt(self, goal, verification_data):
        """Store failed goal attempt"""
        try:
            attempts_file = os.path.join(self.knowledge_dir, 'goals', 'failed_attempts.json')
            entry = {
                "goal": goal,
                "verification": verification_data,
                "timestamp": datetime.now().isoformat()
            }
            
            attempts = []
            if os.path.exists(attempts_file):
                with open(attempts_file, 'r') as f:
                    attempts = json.load(f)
                    
            attempts.append(entry)
            
            with open(attempts_file, 'w') as f:
                json.dump(attempts, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to store failed attempt: {str(e)}")
    
    def _similar_states(self, state1, state2):
        """Check if two states are similar enough to be considered equivalent"""
        key_attrs = ['active_window', 'paint_open', 'paint_ready']
        return all(state1.get(attr) == state2.get(attr) for attr in key_attrs)
    
    def ensure_knowledge_structure(self):
        """Ensure knowledge directory structure exists"""
        subdirs = ['actions', 'states', 'goals', 'verifications']
        for subdir in subdirs:
            path = os.path.join(self.knowledge_dir, subdir)
            if not os.path.exists(path):
                os.makedirs(path)
    
    def store_goal_attempt(self, goal, steps, success=None):
        attempt = {
            'timestamp': datetime.now().isoformat(),
            'goal': goal,
            'steps': steps,
            'success': success,
            'context': {}
        }
        
        file_path = os.path.join(self.base_dir, 'goals', 'history.json')
        history = self.load_json(file_path, [])
        history.append(attempt)
        self.save_json(file_path, history)
        
        if success:
            self.learn_from_success(attempt)
    
    def learn_from_success(self, attempt):
        patterns_file = os.path.join(self.base_dir, 'goals', 'patterns.json')
        patterns = self.load_json(patterns_file, {})
        
        # Extract key elements from successful attempt
        pattern = {
            'goal_type': self.categorize_goal(attempt['goal']),
            'steps': self.generalize_steps(attempt['steps']),
            'context': attempt['context'],
            'last_success': datetime.now().isoformat(),
            'success_count': 1
        }
        
        # Update existing or add new pattern
        goal_type = pattern['goal_type']
        if goal_type in patterns:
            patterns[goal_type]['success_count'] += 1
            patterns[goal_type]['last_success'] = pattern['last_success']
            self.merge_steps(patterns[goal_type]['steps'], pattern['steps'])
        else:
            patterns[goal_type] = pattern
            
        self.save_json(patterns_file, patterns)
    
    def categorize_goal(self, goal):
        # Ask LLM to categorize the goal
        prompt = f"""Categorize this goal into a general type: {goal}
        Return just the category name, like:
        - open_program
        - create_document
        - system_operation
        etc."""
        
        # TODO: Get response from LLM
        return "general_task"  # Placeholder
    
    def generalize_steps(self, steps):
        # Remove specific details while keeping the structure
        generalized = []
        for step in steps:
            gen_step = {
                'type': step.get('verification', 'action'),
                'description': self.generalize_description(step['description']),
                'required_states': step.get('required_state', {}),
                'success_pattern': step.get('success_pattern', {})
            }
            generalized.append(gen_step)
        return generalized
    
    def generalize_description(self, description):
        # Ask LLM to generalize the description
        prompt = f"""Generalize this step description by removing specific details but keeping the essential action:
        {description}
        
        Example:
        "Click the Save button in Microsoft Word" -> "Click save button in application"
        """
        
        # TODO: Get response from LLM
        return description  # Placeholder
    
    def merge_steps(self, existing_steps, new_steps):
        # Intelligently merge steps, keeping the most reliable patterns
        # TODO: Implement smart merging logic
        pass
    
    def load_json(self, file_path, default=None):
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
        return default if default is not None else {}
    
    def save_json(self, file_path, data):
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving {file_path}: {e}") 
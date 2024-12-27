from typing import Dict, Any, List, Optional
import json
from datetime import datetime
import threading
import queue

class AgentCore:
    """Core agent functionality implementing ReAct pattern"""
    
    def __init__(self, llm_interface, action_executor, logger):
        self.llm = llm_interface
        self.executor = action_executor
        self.logger = logger
        self.running = False
        self.action_queue = queue.Queue()
        self.thought_history = []
        self.max_retries = 3
        
    def set_goal(self, goal: str) -> bool:
        """Initialize agent with a goal"""
        try:
            # Format system prompt with available actions
            system_prompt = f"""
            You run in a loop of Thought, Action, PAUSE, Action_Response.
            At the end of the loop you output an Answer.
            
            Use Thought to understand the question and current state.
            Use Action to run one of the actions available to you - then return PAUSE.
            Action_Response will be the result of running those actions.
            
            Your available actions are:
            {self.executor.get_action_descriptions()}
            
            Always return actions in this JSON format:
            {{
                "function_name": "action_name",
                "function_params": {{
                    "param1": "value1"
                }}
            }}
            """
            
            self.current_goal = goal
            self.thought_history = []
            self.action_queue = queue.Queue()
            
            # Initialize conversation with LLM
            response = self.llm.start_conversation(system_prompt, goal)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set goal: {str(e)}")
            return False

    def run(self):
        """Main agent loop implementing ReAct pattern"""
        self.running = True
        retry_count = 0
        
        try:
            self.logger.info(f"Starting agent with goal: '{self.current_goal}'")
            self.logger.info("Initializing agent state and planning...")
            
            while self.running and retry_count < self.max_retries:
                try:
                    # Get next action from LLM
                    thought, action = self.llm.get_next_action()
                    
                    if thought:
                        self.logger.info(f"Agent thought: {thought}")
                        self.thought_history.append(thought)
                    
                    if not action:
                        self.logger.info("No more actions needed - goal appears complete")
                        break
                        
                    # Log planned action
                    self.logger.info(f"Planning to execute: {action['function_name']}")
                    self.logger.debug(f"Action parameters: {action['function_params']}")
                    
                    # Execute action
                    result = self.executor.execute_action(action)
                    
                    # Log result
                    if result["success"]:
                        self.logger.info(f"Action succeeded: {action['function_name']}")
                        self.logger.debug(f"Result details: {result}")
                    else:
                        self.logger.warning(f"Action failed: {action['function_name']}")
                        self.logger.error(f"Error details: {result.get('error', 'Unknown error')}")
                    
                    # Feed result back to LLM
                    self.llm.add_action_result(result)
                    retry_count = 0
                    
                except Exception as e:
                    retry_count += 1
                    self.logger.error(f"Error in agent loop (attempt {retry_count}/{self.max_retries}): {str(e)}")
                    
            # Log completion status
            if len(self.thought_history) > 0:
                self.logger.info("Agent run completed")
                self.logger.info(f"Total thoughts/actions: {len(self.thought_history)}")
                self.logger.info("Final state: Success" if retry_count < self.max_retries else "Final state: Failed")
            else:
                self.logger.warning("Agent run completed without any actions taken")
                
            return len(self.thought_history) > 0
            
        finally:
            self.running = False 
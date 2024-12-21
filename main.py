import customtkinter as ctk
from rich.console import Console
import threading
import os
import time
from typing import Optional, Dict, Any
import json

from llm_interface import LLMInterface
from knowledge_manager import KnowledgeManager
from action_executor import ActionExecutor
from schema_validator import SchemaValidator
from debug_logger import DebugLogger
from input_control import InputController
from goal_planner import GoalPlanner
from goal_verifier import GoalVerifier

class Agent:
    def __init__(self, gui):
        self.gui = gui
        self.logger = DebugLogger("agent")
        self.knowledge = KnowledgeManager()
        self.llm = LLMInterface()
        self.executor = ActionExecutor(self.knowledge, self.logger)
        self.goal_planner = GoalPlanner()
        
        self.goal = None
        self.running = False
        self.current_task = None
        self.current_plan = None
        self.state = {
            "paint_launched": False,
            "paint_ready": False,
            "current_tool": None,
            "current_color": None
        }
        
        self.error_count = 0
        self.max_errors = 10  # Maximum consecutive errors before stopping
        self.last_error_time = 0
        self.error_window = 1.0  # Time window in seconds to count errors
        
        # Add input controller
        self.input_controller = InputController(self.logger)
        
        # Verify permissions before starting
        if not self.input_controller.verify_input_permissions():
            self.logger.error("Failed to verify input permissions")
            gui.log_message("Error: Input permissions check failed")
            return
    
    def set_goal(self, goal: str) -> bool:
        try:
            self.goal = goal
            self.logger.info(f"Setting goal: {goal}")
            self.current_plan = self.goal_planner.break_down_goal(goal)
            if self.current_plan and 'steps' in self.current_plan:
                self.current_plan['current_step_index'] = 0
            if not self.current_plan or 'steps' not in self.current_plan:
                self.logger.error("Failed to generate plan for the goal")
                return False
            self.gui.log_message(f"Goal broken down into {len(self.current_plan['steps'])} steps:")
            for i, step in enumerate(self.current_plan['steps']):
                self.gui.log_message(f"Step {i+1}: {step['description']}")
            return True
        except Exception as e:
            self.logger.error(f"Error in set_goal: {str(e)}")
            return False
    
    def run(self):
        try:
            self.running = True
            self.error_count = 0
            self.gui.log_message("Creating plan...")
            
            # Split plan creation into background thread
            def create_plan_thread():
                self.current_plan = self.create_plan(self.goal)
                self.gui.log_message(f"Plan created with {len(self.current_plan['steps'])} steps")
                
            threading.Thread(target=create_plan_thread).start()
            
            while self.running:
                if not self.current_plan:
                    self.gui.log_message("Waiting for plan...")
                    time.sleep(0.5)
                    continue
                    
                if not self.current_plan.get('steps'):
                    self.logger.debug("No steps to run, stopping.")
                    self.gui.log_message("No steps were found. Stopping agent.")
                    break
                
                step = self.get_next_step()
                if not step:
                    self.gui.log_message("Checking goal completion...")
                    if self.check_goal_completion():
                        self.logger.info("Goal completed successfully") 
                        self.gui.log_message("Goal completed successfully")
                        break
                    else:
                        self.gui.log_message("Replanning...")
                        # Split replanning into background thread
                        def replan_thread():
                            self.replan()
                        threading.Thread(target=replan_thread).start()
                        continue

                self.gui.log_message(f"Executing: {step.get('name', 'unnamed_step')}")
                
                if not self.verify_prerequisites(step):
                    self.gui.log_message("Prerequisites not met, adjusting...")
                    self.handle_missing_prerequisites(step)
                    continue
                    
                for action in step.get('actions', []):
                    if not self.running:
                        break
                    
                    self.gui.log_message(f"Action: {action.get('description', 'unnamed_action')}")
                    pre_state = self.executor.capture_state()
                    action_success = self.executor.execute(action)
                    
                    if not action_success:
                        self.gui.log_message("Action failed, handling failure...")
                        failure_state = self.executor.capture_state()
                        self.handle_failure(action, failure_state)
                        if self.detect_unexpected_state_change(pre_state, failure_state):
                            self.gui.log_message("Unexpected state change detected")
                            self.handle_unexpected_state()
                        self.error_count += 1
                        if self.error_count >= self.max_errors:
                            self.logger.error("Too many errors, stopping")
                            self.gui.log_message("Too many errors, stopping agent")
                            self.running = False
                            break
                        else:
                            self.gui.log_message("Trying alternative approach...")
                            if not self.try_alternative_approach(action, failure_state):
                                self.gui.log_message("No alternative found, replanning...")
                                # Split replanning into background thread
                                def replan_thread():
                                    self.replan()
                                threading.Thread(target=replan_thread).start()
                            break
                    
                    post_state = self.executor.capture_state()
                    if not self.verify_action_result(action, pre_state, post_state):
                        self.gui.log_message("Action verification failed")
                        self.handle_verification_failure(action, post_state)
                        continue
                    
                    time.sleep(0.1)  # Small delay to prevent UI lockup
                
                if self.running:
                    self.gui.log_message("Checking goal completion...")
                    if self.check_goal_completion():
                        self.logger.info("Goal completed successfully")
                        self.gui.log_message("Goal completed successfully")
                        break

        except Exception as e:
            self.logger.error(f"Error in run loop: {str(e)}")
            self.gui.log_message(f"Error: {str(e)}")
        finally:
            self.running = False
            self.gui.log_message("Agent stopped")
    
    def get_next_action(self, current_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            current_step = self.current_plan['steps'][self.current_plan['current_step_index']]
            
            # If Paint isn't open, execute launch sequence
            if not current_state.get('paint_open'):
                # If Run dialog is already open, type mspaint
                if current_state['active_window'] == 'Run':
                    return {
                        "type": "TYPE",
                        "params": {"text": "mspaint\n"},  # \n to auto-press enter
                        "description": "Type mspaint command and press enter"
                    }
                # Otherwise open Run dialog
                return {
                    "type": "PRESS",
                    "params": {"keys": "win+r"},
                    "description": "Open Run dialog to launch Paint"
                }
            
            # If we get here, Paint should be open
            if current_step['name'] == "draw_house":
                # Drawing logic here
                pass
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in get_next_action: {str(e)}")
            return None
    
    def handle_failure(self, failed_action: Dict[str, Any], state: Dict[str, Any]):
        self.logger.error(f"Action failed: {failed_action}")
        self.gui.log_message(f"Action failed: {failed_action.get('description', '')}")
        self.gui.log_message("Retrying with alternative approach...")
    
    def check_goal_completion(self) -> bool:
        if not self.current_plan:
            return False
        
        try:
            # Get current state
            current_state = self.executor.capture_state()
            
            # Use GoalVerifier for comprehensive check
            verifier = GoalVerifier(self.logger)
            success, verification_data = verifier.verify_goal_completion(
                self.goal,
                current_state,
                self.current_plan.get('expected_final_state')
            )
            
            if not success:
                self.logger.debug(f"Goal verification failed: {json.dumps(verification_data)}")
                
                # Check if we need to continue or restart
                if verification_data['confidence'] > 0.5:
                    # Partial success - continue with remaining steps
                    self.logger.info("Partial success detected, continuing execution")
                    return False
                else:
                    # Low confidence - consider restarting
                    self.logger.warning("Low confidence in current progress, considering restart")
                    self.handle_low_confidence_state(verification_data)
                    return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error in goal completion check: {str(e)}")
            return False
        
    def handle_low_confidence_state(self, verification_data):
        """Handle cases where goal completion confidence is low"""
        try:
            # Store the failed attempt for learning
            self.knowledge.store_failed_attempt(self.goal, verification_data)
            
            # Check if we should restart
            if self.error_count < self.max_errors:
                self.logger.info("Restarting goal execution with adjusted plan")
                self.replan()
            else:
                self.logger.error("Too many failed attempts, stopping execution")
                self.running = False
                
        except Exception as e:
            self.logger.error(f"Error handling low confidence state: {str(e)}")
    
    def stop(self):
        self.running = False
        if self.current_task:
            self.current_task.join(timeout=5)
    
    def update_gui(self, thought: str = None, state: Dict = None, progress: float = None):
        if thought:
            self.gui.update_thought_process(thought)
        if state:
            self.gui.update_state(state)
        if progress is not None:
            status = "Running" if self.running else "Stopped"
            self.gui.update_progress(progress, status)
    
    def update_state(self, key: str, value: Any):
        self.state[key] = value
        self.gui.update_state(self.state)
    
    def replan(self):
        self.logger.info("Replanning the current goal")
        self.current_plan = self.goal_planner.break_down_goal(self.goal)
        if not self.current_plan:
            self.logger.error("Failed to replan the goal")
            self.gui.log_message("Failed to replan the goal")
            self.running = False
    
    def create_plan(self, goal):
        plan = self.goal_planner.break_down_goal(goal)
        if plan and 'steps' in plan:
            plan['current_step_index'] = 0
        return plan
    
    def verify_prerequisites(self, step):
        required_state = step.get('required_state', {})
        current_state = self.executor.capture_state()
        
        for key, value in required_state.items():
            if current_state.get(key) != value:
                self.logger.debug(f"Prerequisite not met: {key} = {value}")
                return False
        return True
    
    def handle_missing_prerequisites(self, step):
        required_state = step.get('required_state', {})
        current_state = self.executor.capture_state()
        
        for key, value in required_state.items():
            if current_state.get(key) != value:
                # Create intermediate step to achieve required state
                intermediate_step = self.create_intermediate_step(key, value)
                if intermediate_step:
                    self.current_plan['steps'].insert(
                        self.current_plan['current_step_index'],
                        intermediate_step
                    )
    
    def detect_unexpected_state_change(self, pre_state, post_state):
        # Compare relevant state attributes
        key_attributes = ['active_window', 'paint_open', 'paint_ready']
        for attr in key_attributes:
            if pre_state.get(attr) != post_state.get(attr):
                self.logger.debug(f"Unexpected change in {attr}")
                return True
        return False
    
    def handle_unexpected_state(self):
        current_state = self.executor.capture_state()
        self.knowledge.store_state_transition(current_state)
        
        # Try to recover known good state
        recovery_plan = self.create_recovery_plan(current_state)
        if recovery_plan:
            self.execute_recovery_plan(recovery_plan)
        else:
            self.replan()
    
    def try_alternative_approach(self, failed_action, failure_state):
        alternatives = self.knowledge.get_alternative_actions(failed_action, failure_state)
        
        for alt_action in alternatives:
            self.logger.debug(f"Trying alternative action: {alt_action}")
            if self.executor.execute(alt_action):
                self.knowledge.store_successful_alternative(failed_action, alt_action)
                return True
                
        return False
    
    def verify_action_result(self, action, pre_state, post_state):
        expected_result = action.get('expected_result')
        if not expected_result:
            return True
            
        verifier = GoalVerifier(self.logger)
        success, _ = verifier.verify_goal_completion(
            expected_result,
            post_state,
            action.get('expected_state')
        )
        return success
    
    def handle_verification_failure(self, action, current_state):
        self.knowledge.store_verification_failure(action, current_state)
        
        # Check if we need to add recovery steps
        recovery_steps = self.create_recovery_steps(action, current_state)
        if recovery_steps:
            self.current_plan['steps'][self.current_plan['current_step_index']:self.current_plan['current_step_index']] = recovery_steps
    
    def create_intermediate_step(self, requirement_key, target_value):
        # Create step to achieve specific prerequisite
        if requirement_key == 'paint_open' and target_value:
            return {
                'name': 'launch_paint',
                'description': 'Launch MS Paint',
                'actions': [
                    {
                        'type': 'PRESS',
                        'params': {'keys': 'win+r'},
                        'description': 'Open Run dialog'
                    },
                    {
                        'type': 'TYPE',
                        'params': {'text': 'mspaint\n'},
                        'description': 'Launch Paint'
                    }
                ]
            }
        return None
    
    def create_recovery_plan(self, current_state):
        # Query knowledge base for successful recovery patterns
        recovery_patterns = self.knowledge.get_recovery_patterns(current_state)
        if recovery_patterns:
            return self.adapt_recovery_pattern(recovery_patterns[0], current_state)
        return None
    
    def execute_recovery_plan(self, recovery_plan):
        self.logger.info("Executing recovery plan")
        for action in recovery_plan['actions']:
            if not self.executor.execute(action):
                self.logger.warning("Recovery action failed")
                return False
        return True
    
    def create_recovery_steps(self, failed_action, current_state):
        # Create steps to recover from verification failure
        recovery_steps = []
        
        if 'paint_ready' in current_state and not current_state['paint_ready']:
            recovery_steps.append({
                'name': 'restore_paint_window',
                'description': 'Restore Paint window',
                'actions': [
                    {
                        'type': 'PRESS',
                        'params': {'keys': 'alt+tab'},
                        'description': 'Switch to Paint window'
                    }
                ]
            })
            
        return recovery_steps
    
    def get_next_step(self):
        """Get the next step to execute from the current plan"""
        try:
            if not self.current_plan or 'steps' not in self.current_plan:
                return None
            
            # Get current step index
            current_index = self.current_plan.get('current_step_index', 0)
            
            # Check if we've completed all steps
            if current_index >= len(self.current_plan['steps']):
                return None
            
            # Get the next step
            step = self.current_plan['steps'][current_index]
            
            # Increment step counter for next time
            self.current_plan['current_step_index'] = current_index + 1
            
            # Log step information
            self.logger.debug(f"Getting step {current_index + 1}: {step.get('name', 'unnamed_step')}")
            
            # Validate step format
            if not self.validate_step(step):
                self.logger.error(f"Invalid step format: {step}")
                return None
            
            return step
            
        except Exception as e:
            self.logger.error(f"Error getting next step: {str(e)}")
            return None
    
    def validate_step(self, step: Dict) -> bool:
        """Validate step has required fields"""
        required_fields = ['name', 'description', 'actions']
        return all(field in step for field in required_fields)
    
    def get_step_progress(self) -> float:
        """Calculate current progress through steps"""
        if not self.current_plan or 'steps' not in self.current_plan:
            return 0.0
        current = self.current_plan.get('current_step_index', 0)
        total = len(self.current_plan['steps'])
        return current / total if total > 0 else 0.0
    
    def reset_step_index(self):
        """Reset step index to beginning"""
        if self.current_plan:
            self.current_plan['current_step_index'] = 0

class AgentGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("LLM Vision Agent")
        self.geometry("1200x800")
        
        # Create main container with two columns
        self.grid_columnconfigure(0, weight=2)  # Control column
        self.grid_columnconfigure(1, weight=3)  # Status column
        self.grid_rowconfigure(0, weight=1)
        
        # Left column - Controls
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.setup_control_frame()
        
        # Right column - Status and Thought Process
        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.setup_status_frame()
        
        # Initialize agent
        self.agent = Agent(self)
        
        # Set up cleanup on close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_control_frame(self):
        self.control_frame.grid_columnconfigure(0, weight=1)
        
        # Goal Setting
        goal_frame = ctk.CTkFrame(self.control_frame)
        goal_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(goal_frame, text="Goal:").grid(row=0, column=0, padx=5, pady=5)
        self.goal_entry = ctk.CTkEntry(goal_frame, width=300)
        self.goal_entry.grid(row=0, column=1, padx=5, pady=5)
        
        button_frame = ctk.CTkFrame(goal_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=5)
        
        self.set_goal_btn = ctk.CTkButton(button_frame, text="Set Goal", command=self.set_goal)
        self.set_goal_btn.grid(row=0, column=0, padx=5)
        
        self.start_btn = ctk.CTkButton(button_frame, text="Start", command=self.start_agent, state="disabled")
        self.start_btn.grid(row=0, column=1, padx=5)
        
        self.stop_btn = ctk.CTkButton(button_frame, text="Stop", command=self.stop_agent, state="disabled")
        self.stop_btn.grid(row=0, column=2, padx=5)
        
        # Log Frame
        log_label = ctk.CTkLabel(self.control_frame, text="Agent Log")
        log_label.grid(row=1, column=0, padx=10, pady=(10,0), sticky="w")
        
        self.log_text = ctk.CTkTextbox(self.control_frame, wrap="word", height=400)
        self.log_text.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        
        # Control buttons
        control_frame = ctk.CTkFrame(self.control_frame)
        control_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        control_frame.grid_columnconfigure((0,1,2), weight=1)
        
        self.copy_log_btn = ctk.CTkButton(control_frame, text="Copy Log", command=self.copy_log)
        self.copy_log_btn.grid(row=0, column=0, padx=5)
        
        self.clear_log_btn = ctk.CTkButton(control_frame, text="Clear Log", command=self.clear_log)
        self.clear_log_btn.grid(row=0, column=1, padx=5)
        
        self.copy_all_btn = ctk.CTkButton(control_frame, text="Copy All Logs", command=self.copy_all_logs)
        self.copy_all_btn.grid(row=0, column=2, padx=5)
        
        self.debug_btn = ctk.CTkButton(control_frame, text="Show Debug Log", command=self.show_debug_log)
        self.debug_btn.grid(row=1, column=0, columnspan=3, padx=5, pady=(5,0))
    
    def setup_status_frame(self):
        self.status_frame.grid_columnconfigure(0, weight=1)
        
        # Current Plan
        plan_label = ctk.CTkLabel(self.status_frame, text="Current Plan")
        plan_label.grid(row=0, column=0, padx=10, pady=(10,0), sticky="w")
        
        self.plan_text = ctk.CTkTextbox(self.status_frame, wrap="word", height=150)
        self.plan_text.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        # Current State
        state_label = ctk.CTkLabel(self.status_frame, text="Current State")
        state_label.grid(row=2, column=0, padx=10, pady=(10,0), sticky="w")
        
        self.state_text = ctk.CTkTextbox(self.status_frame, wrap="word", height=150)
        self.state_text.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        
        # Thought Process
        thought_label = ctk.CTkLabel(self.status_frame, text="Agent Thoughts")
        thought_label.grid(row=4, column=0, padx=10, pady=(10,0), sticky="w")
        
        self.thought_text = ctk.CTkTextbox(self.status_frame, wrap="word", height=200)
        self.thought_text.grid(row=5, column=0, padx=10, pady=10, sticky="ew")
        
        # Progress
        progress_frame = ctk.CTkFrame(self.status_frame)
        progress_frame.grid(row=6, column=0, padx=10, pady=10, sticky="ew")
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(progress_frame, text="Status: Idle")
        self.status_label.grid(row=1, column=0, padx=10, pady=5)
    
    def update_plan(self, plan_text):
        self.plan_text.delete("1.0", "end")
        if isinstance(plan_text, dict) and 'steps' in plan_text:
            plan_str = "Current Plan:\n"
            for i, step in enumerate(plan_text['steps']):
                status = "✓" if step.get('completed') else "□"
                plan_str += f"{status} {i+1}. {step['description']}\n"
                if step.get('sub_steps'):
                    for sub_step in step['sub_steps']:
                        plan_str += f"  - {sub_step.get('description', '')}\n"
        else:
            plan_str = str(plan_text)
        self.plan_text.insert("end", plan_str)
    
    def update_state(self, state_dict):
        self.state_text.delete("1.0", "end")
        state_text = "\n".join([f"{k}: {v}" for k, v in state_dict.items()])
        self.state_text.insert("end", state_text)
    
    def update_thought_process(self, thought):
        self.thought_text.insert("end", f"{thought}\n")
        self.thought_text.see("end")
    
    def update_progress(self, progress: float, status: str):
        self.progress_bar.set(progress)
        self.status_label.configure(text=f"Status: {status}")
    
    def log_message(self, message):
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
    
    def set_goal(self):
        goal = self.goal_entry.get()
        if goal:
            if self.agent.set_goal(goal):
                self.log_message(f"Goal set: {goal}")
                self.start_btn.configure(state="normal")
                self.update_progress(0, "Ready")
            else:
                self.log_message("Failed to set goal")
        else:
            self.log_message("Please enter a goal")
    
    def start_agent(self):
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.goal_entry.configure(state="disabled")
        self.set_goal_btn.configure(state="disabled")
        
        # Start agent in separate thread
        self.agent_thread = threading.Thread(target=self.run_agent)
        self.agent_thread.daemon = True
        self.agent_thread.start()
    
    def run_agent(self):
        self.update_progress(0.1, "Starting")
        self.agent.run()
    
    def stop_agent(self):
        self.agent.stop()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.goal_entry.configure(state="normal")
        self.set_goal_btn.configure(state="normal")
        self.update_progress(0, "Stopped")
        # Clear current task
        self.agent_thread = None
    
    def copy_log(self):
        log_content = self.log_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(log_content)
        self.log_message("Log copied to clipboard")
    
    def clear_log(self):
        self.log_text.delete("1.0", "end")
    
    def on_closing(self):
        self.agent.stop()
        self.quit()
    
    def copy_all_logs(self):
        # Get agent log
        agent_log = self.log_text.get("1.0", "end-1c")
        
        # Get debug log
        debug_log = "Debug log not available"
        try:
            log_file = self.agent.logger.get_log_file()
            with open(log_file, 'r') as f:
                debug_log = f.read()
        except Exception as e:
            debug_log = f"Error reading debug log: {str(e)}"
        
        # Combine logs with headers
        combined_logs = f"""Agent Log:
{'-' * 80}
{agent_log}

Debug Log:
{'-' * 80}
{debug_log}
"""
        
        self.clipboard_clear()
        self.clipboard_append(combined_logs)
        self.log_message("All logs copied to clipboard")
    
    def show_debug_log(self):
        debug_window = ctk.CTkToplevel(self)
        debug_window.title("Debug Log")
        debug_window.geometry("800x600")
        
        debug_text = ctk.CTkTextbox(debug_window, wrap="word")
        debug_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Load and display debug log
        try:
            log_file = self.agent.logger.get_log_file()
            with open(log_file, 'r') as f:
                debug_text.insert("end", f.read())
        except Exception as e:
            debug_text.insert("end", f"Error loading debug log: {str(e)}")

if __name__ == "__main__":
    app = AgentGUI()
    app.mainloop()

import customtkinter as ctk
from rich.console import Console
import threading
import os
import time
from typing import Optional, Dict, Any
import json
import keyboard
import pyautogui
from PIL import ImageGrab
from datetime import datetime

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
        self.goal_verifier = GoalVerifier(self.logger, llm=self.llm)
        
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
        
        self.user_available = True
    
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
            
            # Get LLM feedback on communication
            self._get_llm_feedback()
            
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
                    break
                    
                self.gui.log_message(f"Executing: {step.get('name', 'unnamed_step')}")
                
                # Add timeout for prerequisite resolution
                start_time = time.time()
                max_prereq_time = 10  # 10 seconds timeout
                prereq_attempts = 0
                max_prereq_attempts = 3
                
                while self.running and not self.verify_prerequisites(step):
                    if time.time() - start_time > max_prereq_time:
                        self.gui.log_message("Prerequisite resolution timed out")
                        return False
                        
                    prereq_attempts += 1
                    if prereq_attempts > max_prereq_attempts:
                        self.gui.log_message("Max prerequisite attempts exceeded")
                        return False
                        
                    self.gui.log_message(f"Prerequisites not met, attempt {prereq_attempts}/{max_prereq_attempts}...")
                    if not self.handle_missing_prerequisites(step):
                        self.gui.log_message("Failed to resolve prerequisites")
                        return False
                    time.sleep(0.5)  # Prevent tight loop
                    
                if not self.running:
                    self.gui.log_message("Agent stopped during prerequisite resolution")
                    return False
                    
                # Now execute the step's actions
                for action in step.get('actions', []):
                    if not self.running:
                        self.gui.log_message("Agent stopped during action execution")
                        return False
                        
                    self.gui.log_message(f"Action: {action.get('description', 'unnamed_action')}")
                    
                    pre_state = self.executor.capture_state()
                    action_success = self.executor.execute(action)
                    
                    if not action_success:
                        self.gui.log_message("Action failed, handling failure...")
                        failure_state = self.executor.capture_state()
                        self.handle_failure(action, failure_state)
                        
                        if self.error_count >= self.max_errors:
                            self.logger.error("Too many errors, stopping")
                            self.gui.log_message("Too many errors, stopping agent")
                            return False
                            
                        self.gui.log_message("Trying alternative approach...")
                        if not self.try_alternative_approach(action, failure_state):
                            self.gui.log_message("No alternative found, replanning...")
                            return self.replan()
                        continue
                        
                    post_state = self.executor.capture_state()
                    if not self.verify_action_result(action, pre_state, post_state):
                        self.gui.log_message("Action verification failed")
                        self.handle_verification_failure(action, post_state)
                        continue
                        
                    time.sleep(0.1)  # Small delay to prevent UI lockup
                
                # Only move to next step if current step completed successfully
                self.current_plan['current_step_index'] += 1
                
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
        """Verify all prerequisites are met for a step"""
        try:
            self.gui.log_debug("Starting prerequisite verification")
            current_state = self.executor.capture_state()
            required_state = step.get('required_state', {})
            
            self.gui.log_debug(f"Current state: {json.dumps(current_state, indent=2)}")
            self.gui.log_debug(f"Required state: {json.dumps(required_state, indent=2)}")
            
            for state_name, expected_value in required_state.items():
                self.gui.log_debug(f"Checking prerequisite: {state_name} = {expected_value}")
                
                if not self._check_prerequisite(state_name, expected_value):
                    self.gui.log_debug(f"Prerequisite not met: {state_name}")
                    return False
                    
                time.sleep(self.executor.verify_delay)
                
            self.gui.log_debug("All prerequisites met")
            return True
            
        except Exception as e:
            self.gui.log_debug(f"Error verifying prerequisites: {str(e)}", "ERROR")
            return False
    
    def _check_prerequisite(self, prereq_name, expected_value):
        """Check if a specific prerequisite is met"""
        try:
            current_state = self.executor.capture_state()
            
            # Log the check
            self.logger.debug(f"Checking {prereq_name}: current={current_state.get(prereq_name)}, expected={expected_value}")
            
            if prereq_name == "program_open":
                result = current_state.get("paint_open", False) == expected_value
                self.gui.log_message(f"Paint open check: {'Success' if result else 'Failed'}")
                return result
            
            elif prereq_name == "tool_selected":
                result = current_state.get("current_tool") == expected_value
                self.gui.log_message(f"Tool selection check: {'Success' if result else 'Failed'}")
                return result
            
            elif prereq_name == "color_selected":
                result = current_state.get("current_color") == expected_value
                self.gui.log_message(f"Color selection check: {'Success' if result else 'Failed'}")
                return result
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in prerequisite check: {str(e)}")
            return False
    
    def handle_missing_prerequisites(self, step):
        """Handle missing prerequisites for a step"""
        try:
            required_state = step.get('required_state', {})
            for state_name, expected_value in required_state.items():
                if not self._check_prerequisite(state_name, expected_value):
                    resolution_actions = self._get_prerequisite_resolution(state_name)
                    if not resolution_actions:
                        self.logger.error(f"No resolution found for state: {state_name}")
                        return False
                        
                    # Execute each resolution action in sequence
                    for action in resolution_actions:
                        # Log what we're about to do
                        self.gui.log_message(f"Executing resolution: {action.get('type')} - {action.get('expected_result')}")
                        
                        pre_state = self.executor.capture_state()
                        if not self.executor.execute(action):
                            self.logger.error(f"Failed to execute resolution action: {action}")
                            return False
                            
                        # Wait for action to take effect
                        time.sleep(1.0)  # Full second wait after action
                        
                        # Verify the action worked
                        post_state = self.executor.capture_state()
                        if not self.verify_action_result(action, pre_state, post_state):
                            self.logger.error("Resolution action verification failed")
                            self.gui.log_message("Verification failed - retrying...")
                            time.sleep(1.0)  # Wait before retry
                            continue
                            
                        self.gui.log_message("Resolution step completed successfully")
                        time.sleep(0.5)  # Small delay between steps
                        
                    # After all resolution actions, verify final state
                    time.sleep(1.0)  # Wait before final check
                    if not self._check_prerequisite(state_name, expected_value):
                        self.logger.error(f"State still not met after resolution: {state_name}")
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling prerequisites: {str(e)}")
            return False
        
    def _get_prerequisite_resolution(self, prereq_name):
        """Get action to resolve a missing prerequisite"""
        if prereq_name == "program_open":
            return [
                # First action - open run dialog
                {
                    "type": "PRESS",
                    "params": {"keys": "win+r"},  # Single string instead of list
                    "expected_result": "Run dialog opens",
                    "verification": {
                        "type": "window_title",
                        "value": "Run"
                    }
                },
                # Second action - type mspaint and press enter
                {
                    "type": "TYPE",
                    "params": {
                        "text": "mspaint",
                        "enter": True  # Use enter param instead of \n
                    },
                    "expected_result": "Paint opens",
                    "verification": {
                        "type": "window_title",
                        "value": "Paint"
                    }
                }
            ]
        elif prereq_name == "tool_selected":
            return {
                "type": "CLICK",
                "params": {"target": "tool_button"},
                "expected_result": "Tool selected"
            }
        elif prereq_name == "color_selected":
            return {
                "type": "CLICK", 
                "params": {"target": "color_picker"},
                "expected_result": "Color selected"
            }
        
        return None
    
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
    
    def set_user_available(self, available: bool):
        """Set whether user is available for questions"""
        self.user_available = available
        
    def handle_user_message(self, message: str):
        """Handle incoming message from user"""
        try:
            # Format prompt to maintain context
            prompt = f"""User message: {message}
            Current goal: {self.goal}
            Current state: {json.dumps(self.state, indent=2)}
            
            Respond appropriately and adjust your plan if needed.
            """
            
            response = self.llm.generate(prompt)
            if response:
                self.gui.chat_display.insert("end", f"Agent: {response.get('response', '')}\n")
                self.gui.chat_display.see("end")
                
        except Exception as e:
            self.logger.error(f"Error handling user message: {str(e)}")
            
    def ask_user(self, question: str) -> Optional[str]:
        """Ask user a question if available"""
        if not self.user_available:
            self.logger.info("User not available for questions, proceeding with best guess")
            return None
            
        self.gui.chat_display.insert("end", f"Agent: {question}\n")
        self.gui.chat_display.see("end")
        
        # Note: This is async - response will come through handle_user_message
        return None

    def log_action(self, action, result, details=None):
        """Log action execution with details"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = {
            "timestamp": timestamp,
            "action": action,
            "result": result,
            "details": details,
            "state": self.executor.capture_state()
        }
        
        # Format for display
        message = (
            f"Action: {action.get('type')} - {action.get('description', 'No description')}\n"
            f"Result: {'Success' if result else 'Failed'}\n"
        )
        if details:
            message += f"Details: {details}\n"
        
        # Log to GUI and debug
        self.gui.log_debug(message)
        
        # Store in knowledge base
        self.knowledge.store_action_log(log_entry)

    def _get_llm_feedback(self):
        """Get LLM feedback on communication and execution"""
        try:
            prompt = """
            You are an AI agent working with a programmer to improve our interaction.
            
            Current Context:
            - Goal: {self.goal}
            - Last Action: {self.executor.last_action}
            - Current State: {json.dumps(self.executor.capture_state(), indent=2)}
            
            System Limitations:
            1. We cannot modify the UI layout or add new UI elements
            2. We cannot add new input methods beyond keyboard and mouse
            3. We cannot access system APIs beyond what's available through win32gui/win32api
            4. We cannot modify program windows beyond size/position
            5. We cannot add real-time monitoring or streaming data
            6. We work with discrete state captures, not continuous monitoring
            
            What we CAN improve:
            1. The information we exchange
            2. The timing of our actions
            3. The way we handle errors
            4. The state verification process
            5. The recovery strategies
            
            Please analyze our interaction and provide feedback on:
            1. What additional information would help you make better decisions?
            2. What patterns in the current state would be useful to track?
            3. What error conditions should we watch for?
            4. How can we improve our state verification?
            5. What recovery strategies would be most effective?
            
            Format your response focusing on actionable improvements within our limitations.
            """
            
            response = self.llm.generate(prompt)
            if response:
                feedback = response.get('response', '')
                self.logger.debug(f"LLM Feedback:\n{feedback}")
                
                # Parse feedback for actionable items
                try:
                    feedback_lines = feedback.split('\n')
                    actionable_items = []
                    for line in feedback_lines:
                        if line.strip().startswith('-') or line.strip().startswith('*'):
                            actionable_items.append(line.strip())
                    if actionable_items:
                        self.logger.debug("Actionable Feedback Items:")
                        for item in actionable_items:
                            self.logger.debug(f"  {item}")
                except Exception as e:
                    self.logger.error(f"Failed to parse feedback items: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"Failed to get LLM feedback: {str(e)}")

class AgentGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Set up window management
        self.setup_window()
        
        # Define color schemes
        self.normal_colors = {
            "bg": "#2b2b2b",
            "fg": "#ffffff",
            "button": "#1f538d",
            "button_hover": "#14375e",
            "text_bg": "white",  # Always white
            "text_fg": "black"   # Always black
        }
        
        self.running_colors = {
            "bg": "#1e3d59",
            "fg": "#17b978",
            "button": "#ff9a3c",
            "button_hover": "#ff6e40",
            "text_bg": "white",  # Always white
            "text_fg": "black"   # Always black
        }
        
        # Set initial color scheme
        self.set_color_scheme(self.normal_colors)
        
        # Initialize thread tracking
        self.active_threads = []
        
        # Safety settings for pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5
        
        self.title("LLM Vision Agent")
        self.geometry("1200x800")
        
        # Add error display first
        self.error_label = ctk.CTkLabel(self, text="", text_color="red")
        self.error_label.pack(pady=5)
        
        # Initialize agent
        try:
            self.agent = Agent(self)
            self.agent.logger = DebugLogger("agent", "logs", self)  # Pass GUI to logger
        except Exception as e:
            self.show_error("Failed to initialize agent", str(e))
            self.agent = None
            
        # Create tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Add tabs
        self.tab_main = self.tabview.add("Main")
        self.tab_test = self.tabview.add("Testing")
        self.tab_debug = self.tabview.add("Debug")
        self.tab_settings = self.tabview.add("Settings")
        
        # Configure tab grids
        for tab in [self.tab_main, self.tab_test, self.tab_debug, self.tab_settings]:
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_columnconfigure(1, weight=1)
            tab.grid_rowconfigure(0, weight=1)
        
        # Set up each tab
        self.setup_main_tab()
        self.setup_test_tab()
        self.setup_debug_tab()
        self.setup_settings_tab()
        
        # Set up cleanup on close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_window(self):
        """Configure window size and position"""
        try:
            import win32gui
            import win32con
            import win32api
            
            # Get screen dimensions
            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            
            # Calculate 90% size
            window_width = int(screen_width * 0.9)
            window_height = int(screen_height * 0.9)
            
            # Center position
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            # Set geometry
            self.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Set window state
            self.state('normal')
            self.lift()
            self.focus_force()
            
        except Exception as e:
            print(f"Failed to setup window: {str(e)}")

    def show_error(self, title, message):
        """Display error message to user"""
        try:
            error_text = f"{title}: {message}"
            if hasattr(self, 'error_label'):
                self.error_label.configure(text=error_text)
            print(f"Error: {error_text}")  # Backup console output
        except Exception as e:
            print(f"Error showing error message: {str(e)}")
            print(f"Original error: {title} - {message}")

    def safe_keyboard_write(self, text):
        """Safely execute keyboard write with error handling"""
        try:
            if not text:
                raise ValueError("Empty text input")
            
            self.test_output.insert("end", f"Attempting to write: '{text}'\n")
            
            # Check if keyboard module is properly imported
            if not 'keyboard' in globals():
                raise ImportError("Keyboard module not properly imported")
            
            # Check if we have keyboard permissions
            try:
                # Test keyboard access with a harmless key
                keyboard.is_pressed('shift')
            except Exception as e:
                raise PermissionError(f"No keyboard access: {str(e)}")
            
            # Try writing with delay between characters
            for char in text:
                keyboard.write(char)
                time.sleep(0.05)  # Small delay between characters
                self.test_output.insert("end", f"Wrote character: '{char}'\n")
            
            self.test_output.insert("end", "Write operation completed\n")
            return True
            
        except Exception as e:
            error_msg = f"Keyboard write failed: {str(e)}\n"
            error_msg += f"Error type: {type(e).__name__}\n"
            error_msg += f"Text attempted: '{text}'\n"
            
            self.test_output.insert("end", error_msg)
            self.show_error("Keyboard write failed", str(e))
            return False

    def safe_keyboard_press(self, shortcut):
        """Safely execute keyboard shortcut with error handling"""
        try:
            if not shortcut:
                raise ValueError("Empty shortcut input")
            
            self.test_output.insert("end", f"Attempting to press: '{shortcut}'\n")
            
            # Check if keyboard module is properly imported
            if not 'keyboard' in globals():
                raise ImportError("Keyboard module not properly imported")
            
            # Check if we have keyboard permissions
            try:
                keyboard.is_pressed('shift')
            except Exception as e:
                raise PermissionError(f"No keyboard access: {str(e)}")
            
            # Validate shortcut format
            if '+' in shortcut:
                keys = shortcut.split('+')
                self.test_output.insert("end", f"Parsed keys: {keys}\n")
            
            # Execute the shortcut
            keyboard.press_and_release(shortcut)
            self.test_output.insert("end", f"Pressed shortcut: '{shortcut}'\n")
            return True
            
        except Exception as e:
            error_msg = f"Keyboard shortcut failed: {str(e)}\n"
            error_msg += f"Error type: {type(e).__name__}\n"
            error_msg += f"Shortcut attempted: '{shortcut}'\n"
            
            self.test_output.insert("end", error_msg)
            self.show_error("Keyboard shortcut failed", str(e))
            return False

    def test_typing(self, text):
        """Test typing with safety checks"""
        self.test_output.delete("1.0", "end")
        self.test_output.insert("1.0", "Testing typing...\n")
        
        # Add keyboard module check
        self.test_output.insert("end", "Checking keyboard module...\n")
        if not 'keyboard' in globals():
            self.test_output.insert("end", "Error: Keyboard module not available\n")
            return
        
        # Add permission check
        self.test_output.insert("end", "Checking keyboard permissions...\n")
        try:
            keyboard.is_pressed('shift')
            self.test_output.insert("end", "Keyboard permissions OK\n")
        except Exception as e:
            self.test_output.insert("end", f"Keyboard permission error: {str(e)}\n")
            return
        
        if not self.safe_keyboard_write(text):
            self.test_output.insert("end", "Typing test failed\n")
            return
        
        self.test_output.insert("end", f"Typed: {text}\n")

    def test_shortcut(self, shortcut):
        """Test shortcut with safety checks"""
        self.test_output.delete("1.0", "end")
        self.test_output.insert("1.0", f"Testing shortcut: {shortcut}\n")
        
        if not self.safe_keyboard_press(shortcut):
            self.test_output.insert("end", "Shortcut test failed\n")
            return
            
        self.test_output.insert("end", "Shortcut executed\n")

    def test_launch_paint(self):
        """Test Paint launch with safety checks"""
        self.test_output.delete("1.0", "end")
        self.test_output.insert("1.0", "Launching Paint...\n")
        
        # Execute each step with safety checks
        if not self.safe_keyboard_press("win+r"):
            return
            
        time.sleep(0.5)
        
        if not self.safe_keyboard_write("mspaint"):
            return
            
        if not self.safe_keyboard_press("enter"):
            return
            
        self.test_output.insert("end", "Paint launch sequence completed\n")

    def test_llm_connection(self):
        """Test LLM connection with proper error handling"""
        self.test_output.delete("1.0", "end")
        self.test_output.insert("1.0", "Testing LLM connection...\n")
        
        if not self.agent:
            self.test_output.insert("end", "Error: Agent not initialized\n")
            return
            
        try:
            response = self.agent.llm.generate("Say 'Hello World'")
            if response:
                # Extract and format relevant information
                message = response.get('response', 'No response text')
                model = response.get('model', 'Unknown model')
                duration = response.get('total_duration', 0) / 1e9  # Convert nanoseconds to seconds
                
                # Format the output
                output = (
                    f"Response received:\n"
                    f"  Message: {message}\n"
                    f"  Model: {model}\n"
                    f"  Response time: {duration:.2f} seconds\n"
                )
                
                self.test_output.insert("end", output)
            else:
                self.test_output.insert("end", "Error: Empty response from LLM\n")
        except Exception as e:
            self.test_output.insert("end", f"Error: {str(e)}\n")
            self.show_error("LLM test failed", str(e))

    def on_closing(self):
        """Clean up resources before closing"""
        try:
            # Stop agent if running
            if hasattr(self, 'agent') and self.agent:
                self.agent.stop()
                
            # Wait for threads to finish
            for thread in self.active_threads:
                if thread.is_alive():
                    thread.join(timeout=1.0)
            
            # Destroy window
            self.quit()
            
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
            self.quit()

    def setup_main_tab(self):
        # Left column - Controls
        control_frame = ctk.CTkFrame(self.tab_main)
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Goal input
        goal_label = ctk.CTkLabel(control_frame, text="Goal:")
        goal_label.pack(pady=5)
        
        self.goal_entry = ctk.CTkEntry(control_frame, width=300)
        self.goal_entry.pack(pady=5)
        self.goal_entry.insert(0, "draw a house in paint")  # Default goal
        
        # Control buttons
        self.start_button = ctk.CTkButton(control_frame, text="Start", command=self.start_agent)
        self.start_button.pack(pady=5)
        
        self.stop_button = ctk.CTkButton(control_frame, text="Stop", command=self.stop_agent)
        self.stop_button.pack(pady=5)
        
        # User availability toggle
        self.user_available = ctk.CTkCheckBox(control_frame, text="Available for questions",
                                            command=self.toggle_user_availability)
        self.user_available.pack(pady=10)
        self.user_available.select()  # Default to available
        
        # Right column - Status and Chat
        status_frame = ctk.CTkFrame(self.tab_main)
        status_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        status_frame.grid_rowconfigure(1, weight=1)  # Make chat expand
        
        # Status display
        status_label = ctk.CTkLabel(status_frame, text="Status Log:")
        status_label.pack(pady=(0, 5))
        
        self.status_text = ctk.CTkTextbox(status_frame, width=400, height=200)
        self.status_text.pack(pady=5, fill="x")
        
        # Chat interface
        chat_label = ctk.CTkLabel(status_frame, text="Agent Chat:")
        chat_label.pack(pady=(10, 5))
        
        self.chat_display = ctk.CTkTextbox(status_frame, width=400, height=200)
        self.chat_display.pack(pady=5, fill="both", expand=True)
        
        # Chat input area
        chat_input_frame = ctk.CTkFrame(status_frame)
        chat_input_frame.pack(fill="x", pady=5)
        
        self.chat_input = ctk.CTkTextbox(chat_input_frame, height=60, width=300)
        self.chat_input.pack(side="left", padx=5, fill="x", expand=True)
        
        send_button = ctk.CTkButton(chat_input_frame, text="Send",
                                   command=self.send_chat_message)
        send_button.pack(side="right", padx=5)
        
        # Bind Enter and Shift+Enter
        self.chat_input.bind("<Return>", self.handle_chat_return)
        self.chat_input.bind("<Shift-Return>", self.handle_chat_shift_return)

    def handle_chat_return(self, event):
        """Handle Enter key in chat input"""
        if not event.state & 0x1:  # No Shift pressed
            self.send_chat_message()
            return "break"  # Prevent default newline

    def handle_chat_shift_return(self, event):
        """Handle Shift+Enter in chat input"""
        self.chat_input.insert("insert", "\n")
        return "break"  # Prevent default behavior

    def send_chat_message(self):
        """Send chat message to agent"""
        message = self.chat_input.get("1.0", "end-1c").strip()
        if message:
            # Display user message
            self.chat_display.insert("end", f"You: {message}\n")
            self.chat_display.see("end")
            
            # Clear input
            self.chat_input.delete("1.0", "end")
            
            # Send to agent if it exists
            if self.agent:
                self.agent.handle_user_message(message)

    def toggle_user_availability(self):
        """Update user availability status"""
        is_available = self.user_available.get()
        if self.agent:
            self.agent.set_user_available(is_available)
        status = "available" if is_available else "unavailable"
        self.log_message(f"User marked as {status} for questions")

    def setup_test_tab(self):
        # Left column - Input Tests
        input_frame = ctk.CTkFrame(self.tab_test)
        input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Test Mode Section
        test_mode_label = ctk.CTkLabel(input_frame, text="AI-Assisted Testing", font=("Arial", 16, "bold"))
        test_mode_label.pack(pady=10)
        
        # Test Mode Controls
        test_controls = ctk.CTkFrame(input_frame)
        test_controls.pack(fill="x", padx=5, pady=5)
        
        self.test_input = ctk.CTkTextbox(test_controls, height=100, width=300)
        self.test_input.pack(pady=5)
        self.test_input.insert("1.0", "Type test instructions here...\nE.g., 'Test typing Hello World' or 'Test opening Paint'")
        
        test_button = ctk.CTkButton(test_controls, text="Run Test",
                                   command=self.run_ai_test)
        test_button.pack(pady=5)
        
        # Manual Test Section
        manual_label = ctk.CTkLabel(input_frame, text="Manual Testing", font=("Arial", 16, "bold"))
        manual_label.pack(pady=(20, 10))
        
        # Quick Tests
        quick_label = ctk.CTkLabel(input_frame, text="Quick Tests")
        quick_label.pack(pady=5)
        
        run_dialog_btn = ctk.CTkButton(input_frame, text="Test Run Dialog (Win+R)",
                                     command=lambda: self.test_shortcut("win+r"))
        run_dialog_btn.pack(pady=2)
        
        paint_btn = ctk.CTkButton(input_frame, text="Launch Paint",
                                command=self.test_launch_paint)
        paint_btn.pack(pady=2)
        
        # Right column - Output and Status
        output_frame = ctk.CTkFrame(self.tab_test)
        output_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        # Test Output
        output_label = ctk.CTkLabel(output_frame, text="Test Output", font=("Arial", 16, "bold"))
        output_label.pack(pady=10)
        
        self.test_output = ctk.CTkTextbox(output_frame, width=400, height=300)
        self.test_output.pack(pady=5)
        
        # LLM Status
        llm_frame = ctk.CTkFrame(output_frame)
        llm_frame.pack(fill="x", padx=5, pady=5)
        
        test_llm_btn = ctk.CTkButton(llm_frame, text="Check LLM Connection",
                                   command=self.test_llm_connection)
        test_llm_btn.pack(side="left", padx=5)
        
        self.llm_status = ctk.CTkLabel(llm_frame, text="LLM Status: Unknown")
        self.llm_status.pack(side="left", padx=5)

    def setup_debug_tab(self):
        # Debug controls
        debug_frame = ctk.CTkFrame(self.tab_debug)
        debug_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Log controls
        controls_frame = ctk.CTkFrame(debug_frame)
        controls_frame.pack(fill="x", pady=5)
        
        clear_btn = ctk.CTkButton(controls_frame, text="Clear Log",
                                command=self.clear_debug_log)
        clear_btn.pack(side="left", padx=5)
        
        copy_btn = ctk.CTkButton(controls_frame, text="Copy All Logs",
                               command=self.copy_all_logs)
        copy_btn.pack(side="left", padx=5)
        
        save_btn = ctk.CTkButton(controls_frame, text="Save All Logs",
                               command=self.save_all_logs)
        save_btn.pack(side="left", padx=5)
        
        # Auto-scroll toggle
        self.auto_scroll = ctk.CTkCheckBox(debug_frame, text="Auto-scroll")
        self.auto_scroll.pack(pady=5)
        self.auto_scroll.select()
        
        # Debug log display
        self.debug_text = ctk.CTkTextbox(self.tab_debug, width=800, height=500)
        self.debug_text.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

    def copy_all_logs(self):
        """Copy all logs to clipboard"""
        try:
            all_logs = []
            
            # Get debug log
            debug_log = self.debug_text.get("1.0", "end-1c")
            if debug_log:
                all_logs.append("=== DEBUG LOG ===")
                all_logs.append(debug_log)
            
            # Get agent log
            if hasattr(self, 'agent') and self.agent:
                agent_log = self.get_file_contents(self.agent.logger.get_log_file())
                if agent_log:
                    all_logs.append("\n=== AGENT LOG ===")
                    all_logs.append(agent_log)
            
            # Get all other logs from logs directory
            logs_dir = "logs"
            if os.path.exists(logs_dir):
                for log_file in os.listdir(logs_dir):
                    if log_file.endswith(".log"):
                        log_path = os.path.join(logs_dir, log_file)
                        log_content = self.get_file_contents(log_path)
                        if log_content:
                            all_logs.append(f"\n=== {log_file} ===")
                            all_logs.append(log_content)
            
            # Copy to clipboard
            combined_logs = "\n".join(all_logs)
            self.clipboard_clear()
            self.clipboard_append(combined_logs)
            self.log_debug("All logs copied to clipboard", "INFO")
            
        except Exception as e:
            self.show_error("Failed to copy logs", str(e))

    def get_file_contents(self, file_path):
        """Safely read file contents"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return f.read()
        except Exception as e:
            self.log_debug(f"Error reading {file_path}: {str(e)}", "ERROR")
        return None

    def save_all_logs(self):
        """Save all logs to a single file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"combined_logs_{timestamp}.txt"
            
            with open(filename, "w") as f:
                # Write debug log
                f.write("=== DEBUG LOG ===\n")
                f.write(self.debug_text.get("1.0", "end-1c"))
                
                # Write agent log
                if hasattr(self, 'agent') and self.agent:
                    agent_log = self.get_file_contents(self.agent.logger.get_log_file())
                    if agent_log:
                        f.write("\n\n=== AGENT LOG ===\n")
                        f.write(agent_log)
                
                # Write all other logs
                logs_dir = "logs"
                if os.path.exists(logs_dir):
                    for log_file in os.listdir(logs_dir):
                        if log_file.endswith(".log"):
                            log_path = os.path.join(logs_dir, log_file)
                            log_content = self.get_file_contents(log_path)
                            if log_content:
                                f.write(f"\n\n=== {log_file} ===\n")
                                f.write(log_content)
            
            self.log_debug(f"All logs saved to {filename}", "INFO")
            
        except Exception as e:
            self.show_error("Failed to save logs", str(e))

    def clear_debug_log(self):
        """Clear the debug log display"""
        self.debug_text.delete("1.0", "end")

    def copy_debug_log(self):
        """Copy debug log to clipboard"""
        log_text = self.debug_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(log_text)
        self.log_debug("Debug log copied to clipboard", "INFO")

    def save_debug_log(self):
        """Save debug log to file"""
        try:
            filename = f"debug_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, "w") as f:
                f.write(self.debug_text.get("1.0", "end-1c"))
            self.log_debug(f"Debug log saved to {filename}", "INFO")
        except Exception as e:
            self.log_debug(f"Failed to save debug log: {str(e)}", "ERROR")

    def toggle_auto_scroll(self):
        """Toggle auto-scroll behavior"""
        is_auto_scroll = self.auto_scroll.get()
        if is_auto_scroll:
            self.debug_text.see("end")

    def setup_settings_tab(self):
        settings_frame = ctk.CTkFrame(self.tab_settings)
        settings_frame.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Timing Settings Section
        timing_label = ctk.CTkLabel(settings_frame, text="Timing Settings", font=("Arial", 16, "bold"))
        timing_label.pack(pady=10)
        
        # Action Delay
        action_frame = ctk.CTkFrame(settings_frame)
        action_frame.pack(fill="x", padx=5, pady=5)
        
        action_label = ctk.CTkLabel(action_frame, text="Action Delay (seconds):")
        action_label.pack(side="left", padx=5)
        
        self.action_delay = ctk.CTkEntry(action_frame, width=100)
        self.action_delay.pack(side="left", padx=5)
        self.action_delay.insert(0, "10.0")  # Default 10 seconds
        
        # Verification Delay
        verify_frame = ctk.CTkFrame(settings_frame)
        verify_frame.pack(fill="x", padx=5, pady=5)
        
        verify_label = ctk.CTkLabel(verify_frame, text="Verification Delay (seconds):")
        verify_label.pack(side="left", padx=5)
        
        self.verify_delay = ctk.CTkEntry(verify_frame, width=100)
        self.verify_delay.pack(side="left", padx=5)
        self.verify_delay.insert(0, "10.0")  # Default 10 seconds
        
        # LLM Settings Section
        llm_label = ctk.CTkLabel(settings_frame, text="LLM Settings", font=("Arial", 16, "bold"))
        llm_label.pack(pady=(20, 10))
        
        # API URL
        url_frame = ctk.CTkFrame(settings_frame)
        url_frame.pack(fill="x", padx=5, pady=5)
        
        url_label = ctk.CTkLabel(url_frame, text="API URL:")
        url_label.pack(side="left", padx=5)
        
        self.api_url = ctk.CTkEntry(url_frame, width=300)
        self.api_url.pack(side="left", padx=5)
        self.api_url.insert(0, "http://localhost:11434/api/generate")
        
        # Model Selection
        model_frame = ctk.CTkFrame(settings_frame)
        model_frame.pack(fill="x", padx=5, pady=5)
        
        model_label = ctk.CTkLabel(model_frame, text="Model:")
        model_label.pack(side="left", padx=5)
        
        self.model_select = ctk.CTkComboBox(model_frame, 
                                          values=["llama3.2-vision:latest"])
        self.model_select.pack(side="left", padx=5)
        
        # Save Button
        save_btn = ctk.CTkButton(settings_frame, text="Save Settings",
                               command=self.save_settings)
        save_btn.pack(pady=20)
        
        # Apply initial settings
        self.save_settings()

    def save_settings(self):
        """Save current settings"""
        try:
            # Parse delay values
            action_delay = float(self.action_delay.get())
            verify_delay = float(self.verify_delay.get())
            
            # Update delays
            self.agent.executor.action_delay = action_delay
            self.agent.executor.verify_delay = verify_delay
            
            # Update other settings
            # ... (API URL, model, etc.)
            
            self.show_error("Success", "Settings saved")  # Use error label as status
        except ValueError as e:
            self.show_error("Error", "Invalid delay value")
        except Exception as e:
            self.show_error("Error", f"Failed to save settings: {str(e)}")

    def start_agent(self):
        """Start the agent with current goal"""
        try:
            if not self.agent:
                self.show_error("Error", "Agent not initialized")
                return
                
            goal = self.goal_entry.get()
            if not goal:
                self.show_error("Error", "Please enter a goal")
                return
                
            # Change to running colors
            self.set_color_scheme(self.running_colors)
            
            if self.agent.set_goal(goal):
                self.log_message("Goal set: " + goal)
                # Run agent in background thread
                agent_thread = threading.Thread(target=self._run_agent_with_color_reset)
                agent_thread.daemon = True
                self.active_threads.append(agent_thread)
                agent_thread.start()
            else:
                self.show_error("Error", "Failed to set goal")
                self.set_color_scheme(self.normal_colors)  # Reset colors on failure
                
        except Exception as e:
            self.show_error("Error starting agent", str(e))
            self.set_color_scheme(self.normal_colors)  # Reset colors on error

    def _run_agent_with_color_reset(self):
        """Run agent and ensure colors are reset when done"""
        try:
            self.agent.run()
        finally:
            # Always reset colors when agent stops
            self.after(0, self.set_color_scheme, self.normal_colors)

    def stop_agent(self):
        """Stop the running agent"""
        try:
            if self.agent:
                self.agent.stop()
                self.log_message("Agent stopped")
                
                # Wait for threads to finish
                for thread in self.active_threads:
                    if thread.is_alive():
                        thread.join(timeout=1.0)
                self.active_threads.clear()
                
                # Reset to normal colors
                self.set_color_scheme(self.normal_colors)
            else:
                self.show_error("Error", "No agent running")
                
        except Exception as e:
            self.show_error("Error stopping agent", str(e))
            self.set_color_scheme(self.normal_colors)  # Reset colors on error

    def log_message(self, message):
        """Add message to status display"""
        try:
            self.status_text.insert("end", message + "\n")
            self.status_text.see("end")  # Scroll to bottom
        except Exception as e:
            print(f"Error logging message: {str(e)}")

    def update_thought_process(self, thought):
        """Update thought process display"""
        try:
            self.status_text.insert("end", "Thinking: " + thought + "\n")
            self.status_text.see("end")
        except Exception as e:
            print(f"Error updating thought process: {str(e)}")

    def update_state(self, state):
        """Update state display"""
        try:
            state_text = "Current State:\n"
            for key, value in state.items():
                state_text += f"  {key}: {value}\n"
            self.status_text.insert("end", state_text)
            self.status_text.see("end")
        except Exception as e:
            print(f"Error updating state: {str(e)}")

    def update_progress(self, progress, status):
        """Update progress display"""
        try:
            progress_text = f"Progress: {progress*100:.1f}% - Status: {status}\n"
            self.status_text.insert("end", progress_text)
            self.status_text.see("end")
        except Exception as e:
            print(f"Error updating progress: {str(e)}")

    def run_ai_test(self):
        """Run test using AI assistance"""
        self.test_output.delete("1.0", "end")
        self.test_output.insert("1.0", "Starting AI-assisted test...\n")
        
        test_instruction = self.test_input.get("1.0", "end").strip()
        if not test_instruction:
            self.test_output.insert("end", "Error: Please enter test instructions\n")
            return
        
        try:
            # Create test-specific prompt with explicit available actions
            prompt = f"""You are a testing assistant. Create a test plan for: {test_instruction}

            Available actions:
            1. Keyboard shortcuts:
               - "win+r" to open Run dialog
               - "enter" to confirm
            2. Typing:
               - Type "mspaint" to launch Paint
               
            To launch Paint, you MUST:
            1. Press "win+r" to open Run dialog
            2. Type "mspaint"
            3. Press "enter"
            
            Respond with a SINGLE JSON object in this exact format:
            {{
                "steps": [
                    {{
                        "type": "shortcut|type",
                        "text": "exact text or shortcut to use",
                        "description": "human readable description"
                    }}
                ],
                "verifications": [
                    {{
                        "type": "window_title|text_present",
                        "expected": "what to expect",
                        "description": "what we're checking"
                    }}
                ]
            }}
            
            Do not include any explanations or multiple versions - just the single JSON object.
            """
            
            # Get test plan from LLM
            response = self.agent.llm.generate(prompt)
            if not response:
                self.test_output.insert("end", "Error: Failed to generate test plan\n")
                return
            
            # Extract JSON from response
            try:
                response_text = response.get('response', '')
                # Find JSON block between curly braces
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if not json_match:
                    raise ValueError("No JSON found in response")
                    
                test_plan = json.loads(json_match.group())
                
                # Format test plan for display
                formatted_plan = json.dumps(test_plan, indent=2)
                self.test_output.insert("end", f"Generated test plan:\n{formatted_plan}\n\n")
                
                # Execute test plan
                self.test_output.insert("end", "Executing test plan...\n")
                
                # Execute steps
                for step in test_plan.get('steps', []):
                    self.test_output.insert("end", f"\nStep: {step.get('description', '')}\n")
                    
                    step_type = step.get('type', '').lower()
                    if step_type == 'type':
                        if not self.safe_keyboard_write(step.get('text', '')):
                            raise Exception(f"Failed to type: {step.get('text')}")
                    elif step_type == 'shortcut':
                        if not self.safe_keyboard_press(step.get('text', '')):
                            raise Exception(f"Failed to press: {step.get('text')}")
                    elif step_type == 'click':
                        # TODO: Implement click handling
                        self.test_output.insert("end", "Click actions not yet implemented\n")
                    else:
                        self.test_output.insert("end", f"Unknown step type: {step_type}\n")
                        
                    time.sleep(0.5)  # Delay between steps
                
                # Run verifications
                self.test_output.insert("end", "\nRunning verifications...\n")
                for verify in test_plan.get('verifications', []):
                    self.test_output.insert("end", f"Checking: {verify.get('description', '')}\n")
                    # TODO: Implement verifications
                    
                self.test_output.insert("end", "\nTest completed\n")
                
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in response: {str(e)}")
                
        except Exception as e:
            self.test_output.insert("end", f"\nTest failed: {str(e)}\n")
            self.show_error("Test failed", str(e))

    def log_debug(self, message, level="DEBUG"):
        """Add timestamped message to debug log"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            log_entry = f"[{timestamp}] [{level}] {message}\n"
            
            # Add to debug log
            self.debug_text.insert("end", log_entry)
            if hasattr(self, 'auto_scroll') and self.auto_scroll.get():
                self.debug_text.see("end")
            
            # Also print to console
            print(log_entry.strip())
            
            # Write to file
            log_file = f"logs/debug_{datetime.now().strftime('%Y%m%d')}.log"
            os.makedirs("logs", exist_ok=True)
            with open(log_file, "a") as f:
                f.write(log_entry)
            
        except Exception as e:
            print(f"Error in log_debug: {str(e)}")
            print(f"Original message: [{level}] {message}")

    def set_color_scheme(self, colors):
        """Apply color scheme to all widgets"""
        self.configure(fg_color=colors["bg"])
        
        # Update tab colors
        if hasattr(self, 'tabview'):
            self.tabview.configure(fg_color=colors["bg"])
            for tab in [self.tab_main, self.tab_test, self.tab_debug, self.tab_settings]:
                tab.configure(fg_color=colors["bg"])
        
        # Update buttons
        if hasattr(self, 'start_button'):
            self.start_button.configure(
                fg_color=colors["button"],
                hover_color=colors["button_hover"],
                text_color=colors["fg"]
            )
            self.stop_button.configure(
                fg_color=colors["button"],
                hover_color=colors["button_hover"],
                text_color=colors["fg"]
            )
        
        # Update text areas - always black on white
        if hasattr(self, 'status_text'):
            self.status_text.configure(
                fg_color=colors["text_bg"],
                text_color=colors["text_fg"]
            )
        
        if hasattr(self, 'debug_text'):
            self.debug_text.configure(
                fg_color=colors["text_bg"],
                text_color=colors["text_fg"]
            )
        
        if hasattr(self, 'test_output'):
            self.test_output.configure(
                fg_color=colors["text_bg"],
                text_color=colors["text_fg"]
            )

if __name__ == "__main__":
    app = AgentGUI()
    app.mainloop()

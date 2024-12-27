import logging
from typing import Optional, Dict, Any
from PIL import ImageGrab
import time
import traceback
from datetime import datetime

class AgentCore:
    def __init__(self, llm, executor, logger, state_manager):
        self.llm = llm
        self.executor = executor
        self.logger = logger
        self.state_manager = state_manager
        self.running = False
        self.last_screenshot = None
        self.screenshot_interval = 0.5  # Time between auto-screenshots
        self.action_delay = 0.5  # Time between actions

    def run(self, goal: str):
        """Run agent with specified goal"""
        try:
            self.running = True
            self.logger.info(f"Starting agent execution with goal: {goal}")
            
            while self.running:
                try:
                    # 1. Capture current state including screen
                    state = self.state_manager.capture_state()
                    if state.get('error'):
                        self.logger.error(f"State capture failed: {state['error']}")
                        time.sleep(1)
                        continue
                    
                    self.logger.debug(f"Current state: Active window={state.get('active_window', {}).get('title')}, Mouse={state.get('mouse_position')}")
                    
                    # 2. Get screen analysis
                    screen_info = self.capture_screen()
                    if not screen_info.get('success'):
                        self.logger.error(f"Screen capture failed: {screen_info.get('error')}")
                        time.sleep(1)
                        continue
                    
                    self.logger.info("Getting next action based on screen analysis...")
                    
                    # 3. Get next action from LLM
                    action = self.llm.get_next_action(
                        goal=goal,
                        state=state,
                        vision_info=screen_info
                    )
                    
                    if not action:
                        self.logger.warning("No action returned from LLM")
                        break
                    
                    if action.get("error"):
                        self.logger.error(f"Failed to get next action: {action.get('error')}")
                        break
                    
                    self.logger.info(f"Planned action: {action.get('function_name')} with params: {action.get('parameters', {})}")
                    
                    # 4. Execute action
                    result = self.executor.execute_action(action)
                    self.logger.info(f"Action result: {result.get('success', False)}")
                    if not result.get('success'):
                        self.logger.error(f"Action failed: {result.get('error')}")
                    
                    # 5. Update state with result
                    self.state_manager.update_state({
                        "last_action": action,
                        "last_result": result,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # 6. Small delay to prevent overwhelming system
                    time.sleep(self.action_delay)
                    
                except Exception as e:
                    self.logger.error(f"Error in agent loop: {str(e)}")
                    self.logger.error(traceback.format_exc())
                    time.sleep(1)
                    
        except Exception as e:
            self.logger.error(f"Agent execution failed: {str(e)}")
            self.logger.error(traceback.format_exc())
        finally:
            self.running = False
            self.logger.info("Agent completed goal")

    def stop(self):
        """Stop agent execution"""
        self.running = False
        self.logger.info("Agent stopping...")

    def capture_screen(self) -> Dict[str, Any]:
        """Capture and analyze current screen"""
        try:
            # Use PIL for screenshot
            screenshot = ImageGrab.grab()
            self.last_screenshot = screenshot
            
            # Get vision analysis
            analysis = self.llm.vision_processor.analyze_screen(screenshot)
            
            # Update state with vision info if successful
            if analysis.get("success"):
                self.state_manager.update_vision_state(analysis)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Screen capture failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "screenshot": self.last_screenshot  # Include last screenshot if available
            } 
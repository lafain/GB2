import logging
from typing import Optional, Dict, Any
from PIL import ImageGrab
import time
import traceback
from datetime import datetime

class AgentCore:
    def __init__(self, llm, executor, logger, state_manager, vision_processor):
        self.llm = llm
        self.executor = executor
        self.logger = logger
        self.state_manager = state_manager
        self.vision_processor = vision_processor
        self.running = False
        self.last_screenshot = None
        self.screenshot_interval = 0.5  # Time between auto-screenshots
        self.action_delay = 0.5  # Time between actions

    def run(self, goal: str):
        """Run agent with given goal"""
        self.running = True
        failures = 0
        MAX_FAILURES = 3
        
        try:
            while self.running:
                # Get vision analysis
                analysis = self.capture_screen()
                
                if not analysis.get("success"):
                    failures += 1
                    self.logger.error(f"Agent execution error: {analysis.get('error')}")
                    
                    if failures >= MAX_FAILURES:
                        self.logger.error("Too many consecutive failures, stopping agent")
                        break
                        
                    continue  # Try again
                    
                # Reset failure counter on success
                failures = 0
                
                # Plan next action based on vision analysis
                action = self.llm.plan_action(goal, analysis["description"])
                
                # Execute planned action
                if not action or action.get("error"):
                    self.logger.error(f"Action planning failed: {action.get('error')}")
                    failures += 1
                elif not self.executor.execute_action(action["function_name"], action.get("parameters", {})):
                    failures += 1
                    
                if failures >= MAX_FAILURES:
                    self.logger.error("Too many consecutive failures, stopping agent")
                    break
                
                # Small delay between actions
                time.sleep(self.action_delay)
                
        except Exception as e:
            self.logger.error(f"Agent execution error: {str(e)}")
            self.running = False

    def stop(self):
        """Stop agent execution"""
        self.running = False
        self.logger.info("Agent stopping...")

    def capture_screen(self) -> Dict[str, Any]:
        """Capture and analyze current screen"""
        try:
            # Use vision processor's capture_screen method
            analysis = self.vision_processor.capture_screen()
            
            # Update state with vision info if successful
            if analysis.get("success"):
                self.state_manager.update_vision_state(analysis)
                return analysis
            else:
                self.logger.error(f"Vision analysis failed: {analysis.get('error')}")
                return analysis
            
        except Exception as e:
            self.logger.error(f"Screen capture failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "screenshot": self.last_screenshot  # Include last screenshot if available
            } 
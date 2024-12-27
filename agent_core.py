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
        self.goal = goal
        self.running = True
        consecutive_failures = 0
        max_failures = 3
        
        while self.running:
            try:
                # Take screenshot
                screenshot = self.vision_processor.capture_screen()
                if not screenshot:
                    raise Exception("Failed to capture screen")
                    
                # Analyze screen
                analysis = self.vision_processor.analyze_screen(screenshot)
                if not analysis.get("success"):
                    raise Exception(f"Vision analysis failed: {analysis.get('error')}")
                    
                # Execute next action
                success = self.execute_next_action(analysis.get("description", ""))
                
                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        self.logger.error("Too many consecutive failures, stopping agent")
                        break
                    
                # Small delay between actions
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Agent execution error: {str(e)}")
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    self.logger.error("Too many consecutive failures, stopping agent")
                    break
                time.sleep(1)  # Longer delay after error

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
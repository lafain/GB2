import traceback
import time

def execute_next_action(self, vision_output: str) -> bool:
    """Execute next action based on vision analysis"""
    try:
        # Get next action from LLM
        action = self.llm.plan_action(self.goal, vision_output)
        if not action or action.get("error"):
            self.logger.error(f"Action planning failed: {action.get('error', 'Unknown error')}")
            # Don't return False here - force a default action instead
            action = {
                "function_name": "press",
                "parameters": {"key": "esc"}  # Default action to try to get out of menus/dialogs
            }
            
        self.logger.debug(f"Planned action: {action}")
        
        # Execute the planned action
        function_name = action.get("function_name")
        parameters = action.get("parameters", {})
        
        if not function_name:
            self.logger.error("No action function specified")
            # Again, force a default action
            function_name = "press"
            parameters = {"key": "esc"}
            
        self.logger.info(f"Executing action: {function_name} with params: {parameters}")
        result = self.action_executor.execute_action(function_name, parameters)
        
        # Add result to LLM conversation history for context
        self.llm.add_action_result({
            "action": function_name,
            "parameters": parameters,
            "success": result.get("success", False),
            "error": result.get("error")
        })
        
        # Add small delay between actions
        time.sleep(0.5)
        
        return True  # Always return True to prevent screenshot loop
        
    except Exception as e:
        self.logger.error(f"Action execution failed: {str(e)}")
        self.logger.error(traceback.format_exc())
        # Even on error, return True to prevent screenshot loop
        return True
        
def is_program_open(self, program: str, vision_output: str) -> bool:
    """Check if a program appears to be open based on vision output"""
    program = program.lower()
    vision_output = vision_output.lower()
    
    # Look for program name in window titles
    return f"window: {program}" in vision_output or f"title: {program}" in vision_output 
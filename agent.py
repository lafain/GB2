import traceback

def execute_next_action(self, vision_output: str) -> bool:
    """Execute next action based on vision analysis"""
    try:
        # Get next action from LLM
        action = self.llm.plan_action(self.goal, vision_output)
        if not action or action.get("error"):
            self.logger.error(f"Action planning failed: {action.get('error', 'Unknown error')}")
            return False
            
        self.logger.debug(f"Planned action: {action}")
        
        # Execute the planned action
        function_name = action.get("function_name")
        parameters = action.get("parameters", {})
        
        if not function_name:
            self.logger.error("No action function specified")
            return False
            
        self.logger.info(f"Executing action: {function_name} with params: {parameters}")
        result = self.action_executor.execute_action(function_name, parameters)
        
        if not result.get("success"):
            self.logger.error(f"Action failed: {result.get('error')}")
            
        return result.get("success", False)
        
    except Exception as e:
        self.logger.error(f"Action execution failed: {str(e)}")
        self.logger.error(traceback.format_exc())
        return False
        
def is_program_open(self, program: str, vision_output: str) -> bool:
    """Check if a program appears to be open based on vision output"""
    program = program.lower()
    vision_output = vision_output.lower()
    
    # Look for program name in window titles
    return f"window: {program}" in vision_output or f"title: {program}" in vision_output 
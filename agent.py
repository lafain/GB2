def execute_next_action(self, vision_output: str) -> bool:
    """Execute next action based on vision analysis"""
    try:
        # Get next action plan
        plan = self.llm.analyze_and_plan(vision_output, self.goal)
        if not plan:
            return False
            
        self.logger.debug(f"Action plan: {plan}")
        
        # Check if required programs are open
        required_programs = plan.get("required_programs", [])
        for program in required_programs:
            if not self.is_program_open(program, vision_output):
                self.logger.info(f"Program '{program}' not found, launching it...")
                self.action_executor.execute_action("launch_program", {"name": program})
                return True  # Let next iteration verify program launched
                
        # Execute planned action
        action = plan.get("next_action", {})
        action_name = action.get("action")
        params = action.get("params", {})
        
        if not action_name:
            self.logger.error("No action specified in plan")
            return False
            
        self.logger.info(f"Planned action: {action_name} with params: {params}")
        result = self.action_executor.execute_action(action_name, params)
        self.logger.info(f"Action result: {result.get('success', False)}")
        
        if not result.get("success"):
            self.logger.error(f"Action failed: {result.get('error')}")
            
        return result.get("success", False)
        
    except Exception as e:
        self.logger.error(f"Action execution failed: {str(e)}")
        return False
        
def is_program_open(self, program: str, vision_output: str) -> bool:
    """Check if a program appears to be open based on vision output"""
    program = program.lower()
    vision_output = vision_output.lower()
    
    # Look for program name in window titles
    return f"window: {program}" in vision_output or f"title: {program}" in vision_output 
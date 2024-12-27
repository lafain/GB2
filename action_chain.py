from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class ActionStep:
    action: str
    params: Dict[str, Any]
    verification: Dict[str, Any]
    retry_strategy: Dict[str, Any]

class ActionChain:
    def __init__(self):
        self.steps: List[ActionStep] = []
        self.current_step = 0
        
    def add_step(self, step: ActionStep):
        self.steps.append(step)
        
    def execute_chain(self, executor):
        """Execute full chain of actions"""
        results = []
        for step in self.steps:
            result = executor.execute_action(step.action, step.params)
            if not result["success"] and step.retry_strategy:
                result = self._handle_retry(step, executor)
            results.append(result)
            if not result["success"]:
                break
        return results 
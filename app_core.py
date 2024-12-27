"""
Core application logic and initialization
"""
import logging
import sys
import requests
from datetime import datetime
import os
import traceback

from agent_core import AgentCore
from llm_interface import LLMInterface
from action_executor import ActionExecutor
from coordinate_system import CoordinateSystem
from state_manager import StateManager
from debug_manager import DebugManager
from vision_processor import VisionProcessor

class AppCore:
    def __init__(self, logger):
        self.logger = logger
        # Don't initialize components here - they will be set by AgentGUI
        self.state_manager = None
        self.vision_processor = None
        self.llm = None
        self.executor = None
        self.coord_system = None
        self.agent = None

    def initialize_components(self):
        """Verify all components are properly initialized"""
        try:
            # Check all required components exist
            required = [
                'state_manager',
                'vision_processor', 
                'llm',
                'executor',
                'coord_system',
                'agent'
            ]
            
            missing = [c for c in required if not hasattr(self, c) or getattr(self, c) is None]
            
            if missing:
                raise Exception(f"Missing required components: {missing}")
                
            self.logger.info("All core components verified")
            return True
            
        except Exception as e:
            self.logger.error(f"Component verification failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False

    def run_system_tests(self):
        """Run system startup tests"""
        test_results = {
            "imports": self._test_imports(),
            "display": self._test_display(),
            "coordinates": self._test_coordinates(),
            "vision": self._test_vision()
        }
        
        return test_results

    def _test_imports(self) -> bool:
        required = ['tkinter', 'PIL', 'win32gui', 'win32con', 'win32api']
        for module in required:
            try:
                __import__(module)
            except ImportError:
                self.logger.error(f"Failed to import {module}")
                return False
        return True

    def _test_display(self) -> bool:
        try:
            from win32api import GetSystemMetrics
            from win32con import SM_CXSCREEN, SM_CYSCREEN
            screen_width = GetSystemMetrics(SM_CXSCREEN)
            screen_height = GetSystemMetrics(SM_CYSCREEN)
            return screen_width > 0 and screen_height > 0
        except Exception as e:
            self.logger.error(f"Display test failed: {str(e)}")
            return False

    def _test_coordinates(self) -> bool:
        try:
            test_system = CoordinateSystem(self.logger)
            return True
        except Exception as e:
            self.logger.error(f"Coordinate system test failed: {str(e)}")
            return False

    def _test_vision(self) -> bool:
        """Test llama3.2-vision model availability"""
        try:
            response = requests.get("http://localhost:11434/api/tags")
            response.raise_for_status()
            models = response.json()
            
            # Parse models list
            if isinstance(models, dict):
                models = models.get('models', [])
            
            available_models = [
                model.get('name', '').split(':')[0] 
                for model in models 
                if isinstance(model, dict)
            ]
            
            self.logger.info(f"Available models: {available_models}")
            
            if 'llama3.2-vision' in available_models:
                self.vision_model = 'llama3.2-vision'
                self.logger.info("Found llama3.2-vision model")
                return True
            
            self.logger.error("Required model llama3.2-vision not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Vision system test failed: {str(e)}")
            return False

    def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'agent'):
            self.agent.stop() 
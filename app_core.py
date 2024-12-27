"""
Core application logic and initialization
"""
import logging
import sys
import requests
from datetime import datetime
import os

from agent_core import AgentCore
from llm_interface import LLMInterface
from action_executor import ActionExecutor
from coordinate_system import CoordinateSystem
from state_manager import StateManager
from debug_manager import DebugManager
from vision_processor import VisionProcessor

class AppCore:
    def __init__(self, logger=None):
        # Initialize logger if not provided
        self.logger = logger or self._setup_logging()
        self.debug_manager = DebugManager(self.logger)
        
    def _setup_logging(self):
        """Initialize logging system"""
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        logger = logging.getLogger('AppCore')
        logger.setLevel(logging.DEBUG)
        
        # File handler
        log_file = os.path.join('logs', f'agent_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger

    def initialize_components(self):
        """Initialize all core components"""
        try:
            self.logger.info("Initializing core components...")
            self.logger.info(f"Python version: {sys.version}")
            self.logger.info(f"Platform: {sys.platform}")
            
            # Initialize state manager with logger
            self.state_manager = StateManager(logger=self.logger)
            
            # Initialize vision system with detected model
            vision_config = {
                "model": getattr(self, 'vision_model', 'llama2'),
                "api_url": "http://localhost:11434/api/chat"
            }
            self.vision_processor = VisionProcessor(config=vision_config, logger=self.logger)
            
            # Initialize coordinate system
            self.coord_system = CoordinateSystem(self.logger)
            
            # Initialize LLM interface
            self.llm = LLMInterface(logger=self.logger, vision_processor=self.vision_processor)
            
            # Initialize action executor
            self.executor = ActionExecutor(
                logger=self.logger,
                coordinate_system=self.coord_system,
                state_manager=self.state_manager
            )
            
            # Initialize agent core
            self.agent = AgentCore(
                llm=self.llm,
                executor=self.executor,
                logger=self.logger,
                state_manager=self.state_manager
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {str(e)}")
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
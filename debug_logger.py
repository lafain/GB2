import logging
import os
from datetime import datetime

class DebugLogger:
    def __init__(self, name="agent", log_dir="logs", gui=None):
        self.log_dir = log_dir
        self.gui = gui
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_file = os.path.join(log_dir, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        # Configure file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        # Configure console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(levelname)s: %(message)s'
        ))
        
        # Configure root logger
        self.logger = logging.getLogger(name)  # Use named logger instead of root
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Store latest log file path
        self.latest_log_file = log_file
    
    def _forward_to_gui(self, level, msg):
        """Forward log message to GUI if available"""
        if self.gui:
            try:
                self.gui.log_debug(f"[{level}] {msg}")
            except Exception:
                pass  # Fail silently if GUI logging fails
    
    def debug(self, msg):
        self.logger.debug(msg)
        self._forward_to_gui("DEBUG", msg)
        
    def info(self, msg):
        self.logger.info(msg)
        self._forward_to_gui("INFO", msg)
        
    def warning(self, msg):
        self.logger.warning(msg)
        self._forward_to_gui("WARNING", msg)
        
    def error(self, msg):
        self.logger.error(msg)
        self._forward_to_gui("ERROR", msg)
    
    def get_log_file(self): return self.latest_log_file 
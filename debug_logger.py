import logging
import os
import sys
from datetime import datetime
from typing import Optional

class DebugLogger:
    def __init__(self, name: str, log_dir: str = "logs", gui = None):
        self.name = name
        self.gui = gui
        
        # Create logs directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Set up file handler
        log_file = os.path.join(log_dir, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        )
        
        # Set up console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        )
        
        # Configure logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
    def _log_to_gui(self, level: str, message: str):
        """Log message to GUI if available"""
        if self.gui and hasattr(self.gui, 'debug_text'):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] [{level}] {message}\n"
            
            try:
                self.gui.debug_text.insert("end", log_entry)
                if hasattr(self.gui, 'auto_scroll') and self.gui.auto_scroll.get():
                    self.gui.debug_text.see("end")
            except Exception as e:
                print(f"Failed to log to GUI: {str(e)}")

    def debug(self, message: str):
        self.logger.debug(message)
        self._log_to_gui("DEBUG", message)

    def info(self, message: str):
        self.logger.info(message)
        self._log_to_gui("INFO", message)

    def warning(self, message: str):
        self.logger.warning(message)
        self._log_to_gui("WARNING", message)

    def error(self, message: str):
        self.logger.error(message)
        self._log_to_gui("ERROR", message)

    def critical(self, message: str):
        self.logger.critical(message)
        self._log_to_gui("CRITICAL", message) 
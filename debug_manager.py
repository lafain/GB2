import logging
import queue
import threading
import tkinter as tk
from datetime import datetime
from typing import Optional

class DebugManager:
    def __init__(self, logger):
        self.logger = logger
        self.message_queue = queue.Queue()
        self.running = True
        
    def start_logging(self, debug_text: Optional[tk.Text] = None):
        """Start debug logging thread"""
        self.debug_text = debug_text
        self.log_thread = threading.Thread(target=self._process_logs)
        self.log_thread.daemon = True
        self.log_thread.start()
        
    def _process_logs(self):
        """Process queued log messages"""
        while self.running:
            try:
                message = self.message_queue.get(timeout=0.1)
                if self.debug_text:
                    self.debug_text.after(0, self._update_debug_text, message)
            except queue.Empty:
                continue
                
    def _update_debug_text(self, message: str):
        """Thread-safe update of debug text"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.debug_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.debug_text.see(tk.END)
        
    def log(self, message: str, level: str = "INFO"):
        """Add message to debug log"""
        self.message_queue.put(f"[{level}] {message}")
        
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if hasattr(self, 'log_thread'):
            self.log_thread.join(timeout=1.0) 
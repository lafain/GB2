"""
Agent Overview:
- GUI Components:
  - Main tab with goal configuration and agent controls
  - Debug tab with logging
  - Test tab for system tests
  - Settings tab for configuration
  - Chat interface for agent communication

- Core Components:
  - Vision System: 
    - Uses Ollama's llama3.2-vision model via official Python client
    - Image preprocessing and resizing
    - Text recognition and scene analysis
    - Automatic model verification
  - LLM Interface: Uses same llama3.2-vision model for decision making
  - Action Executor: Performs system actions
  - State Manager: Tracks system state
  - Coordinate System: Handles window/screen coordinates
  - Debug Manager: Logging and debugging
  - Test Manager: System testing

- Features:
  - Continuous vision monitoring
  - Dynamic action planning
  - Error recovery
  - State tracking
  - Debug logging
  - System testing
  - Settings configuration
  - Chat interface
  - Progress tracking
  - Resource cleanup

- Dependencies:
  - Ollama API (llama3.2-vision model) for vision and LLM
    - Uses official ollama Python client
    - Supports both chat and generate endpoints
    - Handles image encoding and model responses
  - PyAutoGUI for actions
  - Win32 API for system interaction
  - Tkinter for GUI
  - PIL for image processing
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import traceback
from datetime import datetime
import threading
import logging

from app_core import AppCore
from vision_test import VisionTestWindow

class AgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Agent Control")
        
        # Initialize logger
        self.logger = self._setup_logging()
        
        # Initialize core application
        self.app = AppCore(logger=self.logger)
        
        # Run startup tests
        self.run_startup_tests()
        
        # Setup GUI components
        self.setup_gui()
        
        # Initialize debug manager
        if hasattr(self.app, 'debug_manager'):
            self.app.debug_manager.start_logging(self.debug_text)
            
    def _setup_logging(self):
        """Setup logging for GUI"""
        logger = logging.getLogger('AgentGUI')
        logger.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        )
        logger.addHandler(console_handler)
        
        return logger
        
    def run_startup_tests(self):
        """Run system startup tests"""
        try:
            self.logger.info("\n=== Running Startup Tests ===")
            
            # First run system tests that don't require initialized components
            results = self.app.run_system_tests()
            
            # Initialize components if basic tests pass
            if all(results.values()):
                self.logger.info("Basic tests passed, initializing components...")
                if not self.app.initialize_components():
                    self.logger.error("Failed to initialize components")
                    return
            else:
                failed = [k for k, v in results.items() if not v]
                self.logger.error(f"Basic tests failed: {failed}")
                return
            
            # Now run vision test since components are initialized
            vision_test = VisionTestWindow(self.app.vision_processor, self.logger)
            vision_result = vision_test.run_test()
            
            if not vision_result:
                self.logger.warning("Vision test failed - limited functionality may be available")
            else:
                self.logger.info("Vision test passed")
                
            # Final status
            if all(results.values()) and vision_result:
                self.logger.info("All startup tests passed")
            else:
                failed = [k for k, v in results.items() if not v]
                if not vision_result:
                    failed.append("vision_test")
                self.logger.warning(f"Some startup tests failed: {failed}")
                
        except Exception as e:
            self.logger.error(f"Startup tests failed: {str(e)}")
            self.logger.error(traceback.format_exc())

    def setup_gui(self):
        """Setup main GUI components"""
        # Add main container with scrollbar
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tabs
        self.main_tab = ttk.Frame(self.notebook)
        self.debug_tab = ttk.Frame(self.notebook)
        self.test_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.main_tab, text="Main")
        self.notebook.add(self.debug_tab, text="Debug")
        self.notebook.add(self.test_tab, text="Testing")
        self.notebook.add(self.settings_tab, text="Settings")
        
        # Setup individual tabs
        self.setup_main_tab()
        self.setup_debug_tab()
        self.setup_test_tab()
        self.setup_settings_tab()

    def setup_agent(self):
        """Initialize agent components"""
        try:
            if self.app.initialize_components():
                # Update GUI state
                self.status_var = tk.StringVar(value="Agent initialized")
                self.start_button.configure(state=tk.NORMAL)
                self.stop_button.configure(state=tk.DISABLED)
                self.progress_bar['value'] = 0
                self.add_chat_message("System", "Agent initialized and ready.")
            else:
                raise Exception("Failed to initialize components")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {str(e)}")
            self.logger.error(traceback.format_exc())
            if hasattr(self, 'status_var'):
                self.status_var.set("Initialization failed")
            if hasattr(self, 'start_button'):
                self.start_button.configure(state=tk.DISABLED)
            self.add_chat_message("System", f"Initialization failed: {str(e)}")

    def add_chat_message(self, sender: str, message: str):
        """Add message to chat display"""
        if hasattr(self, 'chat_display'):
            self.chat_display.insert(tk.END, f"{sender}: {message}\n")
            self.chat_display.see(tk.END)

    def setup_main_tab(self):
        """Setup main control tab"""
        # Goal configuration
        goal_frame = ttk.LabelFrame(self.main_tab, text="Goal Configuration")
        goal_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.goal_var = tk.StringVar(value="Draw a simple house in Paint")
        goal_entry = ttk.Entry(
            goal_frame, 
            textvariable=self.goal_var,
            width=50
        )
        goal_entry.pack(fill=tk.X, padx=5, pady=5)
        
        # Control buttons
        button_frame = ttk.Frame(self.main_tab)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_button = ttk.Button(
            button_frame,
            text="Start Agent",
            command=self.start_agent
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Agent",
            command=self.stop_agent,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(self.main_tab, text="Progress")
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode='determinate',
            variable=self.progress_var,
            length=300
        )
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        # Chat interface
        chat_frame = ttk.LabelFrame(self.main_tab, text="Agent Chat")
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            height=10
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_debug_tab(self):
        """Setup debug tab"""
        log_frame = ttk.LabelFrame(self.debug_tab, text="Debug Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.debug_text = scrolledtext.ScrolledText(log_frame, height=20)
        self.debug_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Control buttons
        button_frame = ttk.Frame(self.debug_tab)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        clear_button = ttk.Button(
            button_frame,
            text="Clear Log",
            command=lambda: self.debug_text.delete(1.0, tk.END)
        )
        clear_button.pack(side=tk.LEFT, padx=5)

    def setup_test_tab(self):
        """Setup test tab"""
        results_frame = ttk.LabelFrame(self.test_tab, text="Test Results")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.test_display = scrolledtext.ScrolledText(results_frame, height=20)
        self.test_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_settings_tab(self):
        """Setup settings tab"""
        # Vision settings
        vision_frame = ttk.LabelFrame(self.settings_tab, text="Vision Settings")
        vision_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Model selection
        model_frame = ttk.Frame(vision_frame)
        model_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(model_frame, text="Vision Model:").pack(side=tk.LEFT)
        
        self.model_var = tk.StringVar(value="llama2")  # Default to llama2 if vision not available
        model_menu = ttk.OptionMenu(
            model_frame,
            self.model_var,
            "llama2",
            "llama2",
            "llama2-vision",
            command=self.update_model
        )
        model_menu.pack(side=tk.LEFT, padx=5)

    def start_agent(self):
        """Start agent execution"""
        try:
            self.start_button.configure(state=tk.DISABLED)
            self.stop_button.configure(state=tk.NORMAL)
            goal = self.goal_var.get()
            
            self.logger.info(f"Starting agent with goal: {goal}")
            
            # Start agent in separate thread
            if hasattr(self.app, 'agent'):
                self.agent_thread = threading.Thread(
                    target=self.app.agent.run,
                    args=(goal,),
                    daemon=True
                )
                self.agent_thread.start()
                self.add_chat_message("System", f"Started agent with goal: {goal}")
            else:
                raise Exception("Agent not properly initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to start agent: {str(e)}")
            self.add_chat_message("System", f"Failed to start: {str(e)}")
            self.start_button.configure(state=tk.NORMAL)
            self.stop_button.configure(state=tk.DISABLED)

    def stop_agent(self):
        """Stop agent execution"""
        try:
            if hasattr(self.app, 'agent'):
                self.app.agent.stop()
            
            self.start_button.configure(state=tk.NORMAL)
            self.stop_button.configure(state=tk.DISABLED)
            self.add_chat_message("System", "Agent stopped")
            
        except Exception as e:
            self.logger.error(f"Failed to stop agent: {str(e)}")
            self.add_chat_message("System", f"Failed to stop: {str(e)}")

    def update_model(self, *args):
        """Update model selection - disabled since we only use llama3.2-vision"""
        self.model_var.set("llama3.2-vision")
        self.add_chat_message("System", "Using llama3.2-vision model")

def main():
    root = tk.Tk()
    app = AgentGUI(root)
    root.mainloop()
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

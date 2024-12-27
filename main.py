import customtkinter as ctk
from rich.console import Console
import threading
import os
import time
from typing import Optional, Dict, Any
import json
import keyboard
import pyautogui
from PIL import ImageGrab
from datetime import datetime

from agent_core import AgentCore
from llm_interface import LLMInterface
from action_executor import ActionExecutor
from vision_processor import VisionProcessor
from state_manager import StateManager
from debug_logger import DebugLogger

class AgentGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Set appearance mode before creating widgets
        ctk.set_appearance_mode("dark")
        self._default_theme = "dark"
        self._running_theme = "light"  # Brighter when running
        
        # Define color schemes
        self.color_schemes = {
            "dark": {
                "frame_color": "#2B2B2B",
                "button_color": "#404040",
                "button_hover_color": "#4A4A4A",
                "text_color": "#FFFFFF"
            },
            "light": {
                "frame_color": "#F0F0F0",
                "button_color": "#E0E0E0",
                "button_hover_color": "#D0D0D0",
                "text_color": "#000000"
            }
        }
        
        # Initialize state variables
        self._running = False
        self._agent = None
        self._agent_thread = None
        self._active_threads = []
        
        # Set up window management and position
        self._setup_window()
        
        # Initialize core components
        self.logger = DebugLogger("gui", gui=self)
        self.auto_scroll = ctk.BooleanVar(value=True)
        self.state_manager = StateManager()
        
        # Create main containers
        self._create_main_layout()
        
        # Initialize GUI components
        self._create_tabs()
        
        # Set default goal
        self.goal_entry.insert(0, "draw a house in paint")
        
    def _setup_window(self):
        """Configure window size and position"""
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Calculate window size (80% of screen)
        window_width = int(screen_width * 0.8)
        window_height = int(screen_height * 0.8)
        
        # Calculate position (centered)
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Set window properties
        self.title("AI Vision Agent")
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(800, 600)

    def _init_colors(self):
        """Initialize color schemes"""
        self.normal_colors = {
            "frame_color": "#2b2b2b",
            "button_color": "#1f538d",
            "button_hover_color": "#14375e",
            "text_color": "#ffffff",
            "entry_text_color": "#000000",
            "entry_bg_color": "#ffffff"
        }
        
        self.running_colors = {
            "frame_color": "#1e3d59",
            "button_color": "#ff9a3c",
            "button_hover_color": "#ff6e40",
            "text_color": "#17b978",
            "entry_text_color": "#000000",
            "entry_bg_color": "#ffffff"
        }

    def _create_main_layout(self):
        """Create main window layout"""
        # Main container
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Tab view
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.pack(fill="both", expand=True)
        
        # Create tabs
        self.tab_main = self.tabview.add("Main")
        self.tab_test = self.tabview.add("Test")
        self.tab_debug = self.tabview.add("Debug")
        self.tab_settings = self.tabview.add("Settings")

    def _create_tabs(self):
        """Create all tab contents"""
        self._create_main_tab()
        self._create_test_tab()
        self._create_debug_tab()
        self._create_settings_tab()

    def _create_main_tab(self):
        """Create main control tab"""
        # Goal input frame
        goal_frame = ctk.CTkFrame(self.tab_main)
        goal_frame.pack(fill="x", padx=10, pady=5)
        
        goal_label = ctk.CTkLabel(
            goal_frame, 
            text="Goal:",
            font=("Arial", 12, "bold")
        )
        goal_label.pack(side="left", padx=5)
        
        self.goal_entry = ctk.CTkEntry(
            goal_frame,
            placeholder_text="Enter goal here...",
            width=400,
            font=("Arial", 12)
        )
        self.goal_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        # Control buttons - Moved up
        button_frame = ctk.CTkFrame(self.tab_main)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        self.start_button = ctk.CTkButton(
            button_frame,
            text="Start Agent",
            command=self.start_agent,
            font=("Arial", 12, "bold"),
            height=35
        )
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = ctk.CTkButton(
            button_frame,
            text="Stop Agent",
            command=self.stop_agent,
            state="disabled",
            font=("Arial", 12, "bold"),
            height=35
        )
        self.stop_button.pack(side="left", padx=5)
        
        # Status output
        status_frame = ctk.CTkFrame(self.tab_main)
        status_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.status_text = ctk.CTkTextbox(
            status_frame,
            wrap="word",
            font=("Arial", 12)
        )
        self.status_text.pack(fill="both", expand=True, padx=5, pady=5)

    def _update_theme(self, colors):
        """Update GUI theme colors"""
        self.configure(fg_color=colors["frame_color"])
        self.main_frame.configure(fg_color=colors["frame_color"])
        
        for tab in [self.tab_main, self.tab_test, self.tab_debug, self.tab_settings]:
            tab.configure(fg_color=colors["frame_color"])
            
        if hasattr(self, 'start_button'):
            self.start_button.configure(
                fg_color=colors["button_color"],
                hover_color=colors["button_hover_color"],
                text_color=colors["text_color"]
            )
            self.stop_button.configure(
                fg_color=colors["button_color"],
                hover_color=colors["button_hover_color"],
                text_color=colors["text_color"]
            )

    def start_agent(self):
        """Start the agent in a separate thread"""
        if not self._running:
            goal_text = self.goal_entry.get().strip()
            if not goal_text:
                self.show_error("Error", "Please enter a goal")
                return
                
            self._running = True
            self._update_gui_state()
            
            # Initialize agent if needed
            if not self._agent:
                self._agent = AgentCore(
                    LLMInterface(),
                    ActionExecutor(self.logger),
                    self.logger
                )
            
            # Start agent thread
            self._agent_thread = threading.Thread(
                target=self._run_agent,
                args=(goal_text,),
                daemon=True
            )
            self._agent_thread.start()
            self._active_threads.append(self._agent_thread)
            
            self.log_message("Agent started")

    def stop_agent(self):
        """Stop the agent and clean up"""
        if self._running:
            self._running = False
            if self._agent:
                self._agent.running = False
            self._update_gui_state()
            self.log_message("Agent stopped")

    def _update_gui_state(self):
        """Update GUI elements based on running state"""
        if self._running:
            # Switch to running theme
            ctk.set_appearance_mode(self._running_theme)
            
            # Update button states
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            
            # Keep text elements readable
            self._keep_text_readable()
        else:
            # Switch back to default theme
            ctk.set_appearance_mode(self._default_theme)
            
            # Update button states
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            
            # Keep text elements readable
            self._keep_text_readable()

    def _keep_text_readable(self):
        """Ensure text elements remain readable regardless of theme"""
        # Define text colors that work well in both light and dark modes
        text_color = "#FFFFFF" if self._running else "#CCCCCC"
        
        # Update text colors for key elements
        self.goal_entry.configure(text_color=text_color)
        self.agent_log.configure(text_color=text_color)
        self.debug_text.configure(text_color=text_color)
        self.test_input.configure(text_color=text_color)
        self.test_output.configure(text_color=text_color)
        
        # Keep labels readable
        for widget in [self.goal_label, self.status_label]:
            widget.configure(text_color=text_color)

    def log_message(self, message: str):
        """Add message to status text"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.status_text.insert("end", f"[{timestamp}] {message}\n")
            if self.auto_scroll.get():
                self.status_text.see("end")
        except Exception as e:
            print(f"Error logging message: {str(e)}")

    def _create_test_tab(self):
        """Create test execution tab"""
        # Test input frame
        input_frame = ctk.CTkFrame(self.tab_test)
        input_frame.pack(fill="x", padx=10, pady=5)
        
        input_label = ctk.CTkLabel(
            input_frame, 
            text="Test Instructions:",
            font=("Arial", 12, "bold")
        )
        input_label.pack(anchor="w", padx=5, pady=5)
        
        self.test_input = ctk.CTkTextbox(
            input_frame,
            height=100,
            wrap="word",
            font=("Arial", 12)
        )
        self.test_input.pack(fill="x", padx=5, pady=5)
        
        # Test output
        output_frame = ctk.CTkFrame(self.tab_test)
        output_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        output_label = ctk.CTkLabel(
            output_frame,
            text="Test Results:",
            font=("Arial", 12, "bold")
        )
        output_label.pack(anchor="w", padx=5, pady=5)
        
        self.test_output = ctk.CTkTextbox(
            output_frame,
            wrap="word",
            font=("Arial", 12)
        )
        self.test_output.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Control buttons
        button_frame = ctk.CTkFrame(self.tab_test)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        self.run_test_button = ctk.CTkButton(
            button_frame,
            text="Run Test",
            command=self.run_ai_test,
            font=("Arial", 12, "bold"),
            height=35
        )
        self.run_test_button.pack(side="left", padx=5)

    def _create_debug_tab(self):
        """Create debug output tab"""
        # Debug output
        self.debug_text = ctk.CTkTextbox(
            self.tab_debug,
            wrap="none",
            font=("Courier", 12)
        )
        self.debug_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Auto-scroll toggle
        scroll_frame = ctk.CTkFrame(self.tab_debug)
        scroll_frame.pack(fill="x", padx=10, pady=5)
        
        self.auto_scroll_check = ctk.CTkCheckBox(
            scroll_frame,
            text="Auto-scroll",
            variable=self.auto_scroll,
            font=("Arial", 12)
        )
        self.auto_scroll_check.pack(side="left", padx=5)

    def _create_settings_tab(self):
        """Create settings configuration tab"""
        # Color scheme selection
        color_frame = ctk.CTkFrame(self.tab_settings)
        color_frame.pack(fill="x", padx=10, pady=5)
        
        # Delay settings
        delay_frame = ctk.CTkFrame(self.tab_settings)
        delay_frame.pack(fill="x", padx=10, pady=5)
        
        delay_label = ctk.CTkLabel(
            delay_frame,
            text="Action Delays (seconds):",
            font=("Arial", 12, "bold")
        )
        delay_label.pack(anchor="w", padx=5, pady=5)
        
        # Action delay
        action_delay_frame = ctk.CTkFrame(delay_frame)
        action_delay_frame.pack(fill="x", padx=5, pady=2)
        
        action_delay_label = ctk.CTkLabel(
            action_delay_frame,
            text="Min Action Delay:",
            font=("Arial", 12)
        )
        action_delay_label.pack(side="left", padx=5)
        
        self.action_delay = ctk.CTkEntry(
            action_delay_frame,
            width=80,
            font=("Arial", 12)
        )
        self.action_delay.insert(0, "0.5")
        self.action_delay.pack(side="left", padx=5)
        
        # Key press delay
        key_delay_frame = ctk.CTkFrame(delay_frame)
        key_delay_frame.pack(fill="x", padx=5, pady=2)
        
        key_delay_label = ctk.CTkLabel(
            key_delay_frame,
            text="Key Press Delay:",
            font=("Arial", 12)
        )
        key_delay_label.pack(side="left", padx=5)
        
        self.key_delay = ctk.CTkEntry(
            key_delay_frame,
            width=80,
            font=("Arial", 12)
        )
        self.key_delay.insert(0, "0.1")
        self.key_delay.pack(side="left", padx=5)

    def _change_color_scheme(self, choice):
        """Handle color scheme changes"""
        ctk.set_appearance_mode(choice.lower())

    def show_error(self, title, message):
        """Show error dialog"""
        try:
            from tkinter import messagebox
            messagebox.showerror(title, message)
        except Exception as e:
            print(f"Error showing dialog: {str(e)}")

    def _run_agent(self, goal_text: str):
        """Run agent with specified goal"""
        try:
            if self._agent:
                if self._agent.set_goal(goal_text):
                    self.log_message(f"Starting agent with goal: {goal_text}")
                    
                    # Run agent and wait for actual completion
                    result = self._agent.run()
                    
                    if result:
                        self.log_message("Goal completed successfully")
                    else:
                        self.log_message("Goal failed or was interrupted")
                else:
                    self.log_message("Failed to set goal")
                    
        except Exception as e:
            error_msg = f"Error running agent: {str(e)}"
            self.log_message(error_msg)
            self.logger.error(error_msg)  # Log to debug as well
        finally:
            self._running = False
            self._update_gui_state()

    def run_ai_test(self):
        """Run AI-assisted test"""
        if not self._running:
            test_text = self.test_input.get("1.0", "end").strip()
            if test_text:
                self.test_output.delete("1.0", "end")
                self.test_output.insert("end", "Starting test...\n")
                
                # Create test context
                test_context = {
                    "start_time": datetime.now().isoformat(),
                    "test_description": test_text,
                    "results": []
                }
                
                # Set up test logging
                def log_test(message):
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    self.test_output.insert("end", f"[{timestamp}] {message}\n")
                    test_context["results"].append({
                        "timestamp": timestamp,
                        "message": message
                    })
                    self.test_output.see("end")
                
                # Run test in agent
                try:
                    self.goal_entry.delete(0, "end")
                    self.goal_entry.insert(0, test_text)
                    
                    # Store original logging function
                    original_log = self.log_message
                    self.log_message = log_test
                    
                    # Start agent
                    self.start_agent()
                    
                    # Restore original logging
                    self.log_message = original_log
                    
                    # Save test results
                    self._save_test_results(test_context)
                    
                except Exception as e:
                    log_test(f"Test error: {str(e)}")
            else:
                self.show_error("Error", "Please enter test instructions")

    def _save_test_results(self, test_context):
        """Save test results to file"""
        try:
            if not os.path.exists("test_results"):
                os.makedirs("test_results")
            
            filename = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join("test_results", filename)
            
            with open(filepath, 'w') as f:
                json.dump(test_context, f, indent=2)
            
            self.test_output.insert("end", f"\nTest results saved to {filename}\n")
            
        except Exception as e:
            self.test_output.insert("end", f"\nError saving test results: {str(e)}\n")

if __name__ == "__main__":
    app = AgentGUI()
    app.mainloop()

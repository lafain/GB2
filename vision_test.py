import tkinter as tk
import random
import string
import logging
from PIL import ImageGrab
import traceback

class VisionTestWindow:
    def __init__(self, vision_processor, logger):
        self.vision_processor = vision_processor
        self.logger = logger
        
        # Create window
        self.window = tk.Tk()
        self.window.title("Vision Test")
        
        # Position window in center of screen
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        window_width = 800  # Increased from 600
        window_height = 200
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Configure window
        self.window.attributes('-topmost', True)
        self.window.configure(bg='white')  # White background for better contrast
        # self.window.overrideredirect(True)  # Removed to keep window decorations
        
        # Add border
        border_frame = tk.Frame(self.window, bg='black', relief='solid', borderwidth=1)
        border_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        content_frame = tk.Frame(border_frame, bg='white')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Generate random test string
        self.test_string = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        
        # Create label with test string
        self.label = tk.Label(
            content_frame, 
            text=self.test_string,
            font=("Arial", 48, "bold"),  # Large font
            bg='white',
            fg='black'
        )
        self.label.pack(pady=30)
        
        # Add result label
        self.result_label = tk.Label(
            content_frame,
            text="Testing vision...",
            font=("Arial", 12),
            bg='white',
            fg='blue'
        )
        self.result_label.pack(pady=10)
        
        # Add close button
        self.close_button = tk.Button(
            content_frame,
            text="Close",
            command=self.cleanup,
            bg='red',
            fg='white',
            font=("Arial", 10, "bold")
        )
        self.close_button.pack(pady=5)
        
        self.window.protocol("WM_DELETE_WINDOW", self.cleanup)
        self.test_completed = False
        
    def run_test(self) -> bool:
        """Run vision test"""
        try:
            # Initial window setup
            self.window.update()
            
            # Force window to be on top and focused
            self.window.lift()
            self.window.attributes('-topmost', True)
            self.window.focus_force()
            
            # Wait for window to be fully visible and focused
            self.window.after(2000)  # Increased delay to 2 seconds
            self.window.update()
            
            # Double check focus and visibility
            if not self.window.focus_get():
                self.logger.warning("Window may not have focus, retrying...")
                self.window.focus_force()
                self.window.update()
                self.window.after(500)  # Additional small delay
            
            # Log test parameters
            self.logger.info(f"Running vision test with string: {self.test_string}")
            self.logger.info(f"Window size: {self.window.winfo_width()}x{self.window.winfo_height()}")
            self.logger.info(f"Window position: {self.window.winfo_x()}, {self.window.winfo_y()}")
            self.logger.info(f"Label position: {self.label.winfo_x()}, {self.label.winfo_y()}")
            self.logger.info(f"Window has focus: {self.window.focus_get() is not None}")
            
            # Capture screenshot
            screenshot = ImageGrab.grab()
            self.logger.info(f"Screenshot size: {screenshot.size}")
            
            # Get vision analysis with test flag
            self.logger.info("Sending to vision processor...")
            analysis = self.vision_processor.analyze_screen(screenshot, is_test=True)
            
            if not analysis.get("success"):
                error_msg = f"Vision analysis failed: {analysis.get('error')}"
                self.logger.error(error_msg)
                self.result_label.config(
                    text=error_msg,
                    fg="red"
                )
                return False
                
            # Check if test string is in description
            description = analysis.get("description", "").lower()
            self.logger.info("Vision response received:")
            self.logger.info("-" * 40)
            self.logger.info(description)
            self.logger.info("-" * 40)
            
            if self.test_string.lower() in description:
                self.logger.info("Test string found in description!")
                self.result_label.config(
                    text="Vision test passed!",
                    fg="green"
                )
                self.window.after(2000, self.window.destroy)
                return True
            else:
                self.logger.error(f"Test string '{self.test_string}' not found in vision output")
                self.logger.info("Checking for partial matches...")
                
                # Check for partial matches
                test_chars = set(self.test_string.lower())
                desc_chars = set(description.lower())
                common_chars = test_chars & desc_chars
                self.logger.info(f"Characters found: {common_chars}")
                self.logger.info(f"Missing characters: {test_chars - desc_chars}")
                
                self.result_label.config(
                    text=f"Vision test failed - string not found",
                    fg="red"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Vision test failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            self.result_label.config(
                text=f"Test error: {str(e)}",
                fg="red"
            )
            return False 

    def cleanup(self):
        """Ensure window is destroyed"""
        try:
            if self.window:
                self.window.destroy()
                self.window = None
        except:
            pass

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup() 
import tkinter as tk
import random
import string
import logging
from PIL import ImageGrab

class VisionTestWindow:
    def __init__(self, vision_processor, logger):
        self.vision_processor = vision_processor
        self.logger = logger
        
        # Create window
        self.window = tk.Tk()
        self.window.title("Vision Test")
        self.window.geometry("400x200")
        
        # Generate random test string
        self.test_string = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        
        # Create label with test string
        self.label = tk.Label(
            self.window, 
            text=self.test_string,
            font=("Arial", 24)
        )
        self.label.pack(pady=50)
        
        # Add result label
        self.result_label = tk.Label(
            self.window,
            text="Testing vision...",
            font=("Arial", 12)
        )
        self.result_label.pack(pady=20)
        
    def run_test(self) -> bool:
        """Run vision test"""
        try:
            self.window.update()
            self.window.after(1000)  # Wait for window to be visible
            
            # Capture screenshot
            screenshot = ImageGrab.grab()
            
            # Get vision analysis
            analysis = self.vision_processor.analyze_screen(screenshot)
            
            if not analysis.get("success"):
                self.result_label.config(
                    text=f"Vision analysis failed: {analysis.get('error')}",
                    fg="red"
                )
                return False
                
            # Check if test string is in description
            description = analysis.get("description", "").lower()
            if self.test_string.lower() in description:
                self.result_label.config(
                    text="Vision test passed!",
                    fg="green"
                )
                self.window.after(2000, self.window.destroy)  # Close after 2 seconds
                return True
            else:
                self.result_label.config(
                    text=f"Vision test failed - string not found",
                    fg="red"
                )
                self.logger.error(f"Test string '{self.test_string}' not found in vision output")
                self.logger.debug(f"Vision output: {description}")
                return False
                
        except Exception as e:
            self.logger.error(f"Vision test failed: {str(e)}")
            self.result_label.config(
                text=f"Test error: {str(e)}",
                fg="red"
            )
            return False 
import tkinter as tk
import random
import string
import logging
from PIL import ImageGrab
import traceback
import win32gui

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
        window_width = 1000  # Width stays the same
        window_height = 400  # Increased from 300 to 400
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Add flag to track window state
        self.window_destroyed = False
        
        # Configure window
        self.window.attributes('-topmost', True)
        self.window.configure(bg='black')
        
        # Add border
        border_frame = tk.Frame(self.window, bg='white', relief='solid', borderwidth=2)
        border_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        content_frame = tk.Frame(border_frame, bg='black')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Generate random test string
        self.test_string = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        
        # Create label with test string
        self.label = tk.Label(
            content_frame, 
            text=self.test_string,
            font=("Arial", 72, "bold"),
            bg='black',
            fg='white',
            padx=25,
            pady=35
        )
        self.label.pack(expand=True)
        
        # Add result label
        self.result_label = tk.Label(
            content_frame,
            text="Testing vision...",
            font=("Arial", 14),
            bg='black',
            fg='white'
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
            
            # Get vision analysis with test flag and test string
            self.logger.info("Sending to vision processor...")
            analysis = self.vision_processor.analyze_screen(
                screenshot, 
                is_test=True,
                test_string=self.test_string
            )
            
            if not analysis.get("success"):
                error_msg = f"Vision analysis failed: {analysis.get('error')}"
                self.logger.error(error_msg)
                self.result_label.config(
                    text=error_msg,
                    fg="red"
                )
                return False
                
            # Check test results
            test_results = analysis.get("test_results", {})
            exact_matches = test_results.get("exact_matches", [])
            case_matches = test_results.get("case_insensitive_matches", [])
            
            if exact_matches:
                self.logger.info(f"Found exact match: {exact_matches[0]}")
                self.result_label.config(
                    text="Vision test passed! (Exact match)",
                    fg="green"
                )
                self.window.after(2000, self.window.destroy)
                return True
                
            elif case_matches:
                self.logger.info(f"Found case-insensitive match: {case_matches[0]}")
                self.result_label.config(
                    text="Vision test passed! (Case-insensitive match)",
                    fg="green"
                )
                self.window.after(2000, self.window.destroy)
                return True
                
            # Fallback to description search
            description = analysis.get("description", "").lower()
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
        """Clean up and close test window"""
        try:
            if not self.window_destroyed:
                # Store parent window handle before closing
                parent_hwnd = win32gui.FindWindow(None, "AI Control Panel")
                
                try:
                    # Close test window if it exists
                    if self.window and self.window.winfo_exists():
                        self.window_destroyed = True
                        self.window.destroy()
                        self.window = None
                except tk.TclError as e:
                    self.logger.debug(f"Window already destroyed: {e}")
                
                # Restore parent window if found
                if parent_hwnd:
                    try:
                        # Restore if minimized
                        if win32gui.IsIconic(parent_hwnd):
                            win32gui.ShowWindow(parent_hwnd, 9)  # SW_RESTORE = 9
                        
                        # Bring to front
                        win32gui.SetForegroundWindow(parent_hwnd)
                    except Exception as e:
                        self.logger.error(f"Failed to restore parent window: {e}")
                
                self.logger.info("Vision test window cleaned up")
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            self.logger.error(traceback.format_exc())
            
        finally:
            self.test_completed = True
            self.window = None  # Ensure window reference is cleared

    def __del__(self):
        """Destructor to ensure cleanup"""
        if not self.window_destroyed:
            self.cleanup() 
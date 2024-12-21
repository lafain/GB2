import pyautogui
import keyboard
import mouse
import time
from rich.console import Console

console = Console()

class InputController:
    def __init__(self, logger):
        self.logger = logger
        
    def verify_input_permissions(self):
        try:
            # Test keyboard control
            keyboard.press_and_release('shift')
            time.sleep(0.1)
            
            # Test mouse control  
            current_pos = pyautogui.position()
            pyautogui.moveRel(1, 1)
            pyautogui.moveRel(-1, -1)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Input permission check failed: {str(e)}")
            return False
        
    def click(self, x, y):
        self.console.print(f"[yellow]Clicking at position ({x}, {y})")
        pyautogui.click(x, y)
        
    def double_click(self, x, y):
        self.console.print(f"[yellow]Double clicking at position ({x}, {y})")
        pyautogui.doubleClick(x, y)
        
    def drag(self, start_x, start_y, end_x, end_y, duration=0.5):
        self.console.print(f"[yellow]Dragging from ({start_x}, {start_y}) to ({end_x}, {end_y})")
        pyautogui.moveTo(start_x, start_y)
        pyautogui.dragTo(end_x, end_y, duration=duration)
        
    def type_text(self, text, interval=0.1):
        self.console.print(f"[yellow]Typing: {text}")
        pyautogui.write(text, interval=interval)
        
    def press_key(self, key):
        self.console.print(f"[yellow]Pressing key: {key}")
        pyautogui.press(key)
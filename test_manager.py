import logging
import time
from typing import Dict, Any
import tkinter as tk
from tkinter import scrolledtext

class TestManager:
    def __init__(self, logger):
        self.logger = logger
        self.test_results = {}
        
    def run_test_suite(self, test_display: scrolledtext.ScrolledText) -> Dict[str, Any]:
        """Run complete test suite"""
        test_display.delete(1.0, tk.END)
        
        test_functions = [
            ("Import Tests", self.test_imports),
            ("Display Tests", self.test_display),
            ("Coordinate Tests", self.test_coordinates),
            ("Vision Tests", self.test_vision),
            ("Input Tests", self.test_input),
            ("State Tests", self.test_state)
        ]
        
        results = {}
        for name, func in test_functions:
            try:
                result = func()
                status = "PASS" if result else "FAIL"
                test_display.insert(tk.END, f"{name}: {status}\n")
                results[name] = {"success": result}
            except Exception as e:
                test_display.insert(tk.END, f"{name}: ERROR - {str(e)}\n")
                results[name] = {"success": False, "error": str(e)}
                
        return results

    def test_imports(self) -> bool:
        """Test required imports"""
        required = ['tkinter', 'PIL', 'win32gui', 'win32con', 'win32api']
        for module in required:
            try:
                __import__(module)
            except ImportError:
                return False
        return True 

    def test_display(self) -> bool:
        """Test display configuration"""
        try:
            from win32api import GetSystemMetrics
            from win32con import SM_CXSCREEN, SM_CYSCREEN
            
            screen_width = GetSystemMetrics(SM_CXSCREEN)
            screen_height = GetSystemMetrics(SM_CYSCREEN)
            
            self.logger.info("Screen Configuration:")
            self.logger.info(f"  Primary screen: {screen_width}x{screen_height}")
            
            return screen_width > 0 and screen_height > 0
        except Exception as e:
            self.logger.error(f"Display test failed: {str(e)}")
            return False

    def test_coordinates(self) -> bool:
        """Test coordinate system"""
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            rect = win32gui.GetWindowRect(hwnd)
            return all(isinstance(x, int) for x in rect)
        except Exception as e:
            self.logger.error(f"Coordinate test failed: {str(e)}")
            return False

    def test_vision(self) -> bool:
        """Test vision system"""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags")
            if response.status_code != 200:
                return False
            return True
        except Exception as e:
            self.logger.error(f"Vision test failed: {str(e)}")
            return False

    def test_input(self) -> bool:
        """Test input systems"""
        try:
            import pyautogui
            import keyboard
            import mouse
            return True
        except Exception as e:
            self.logger.error(f"Input test failed: {str(e)}")
            return False

    def test_state(self) -> bool:
        """Test state tracking"""
        try:
            import psutil
            processes = psutil.process_iter(['name'])
            return any(processes)
        except Exception as e:
            self.logger.error(f"State test failed: {str(e)}")
            return False 
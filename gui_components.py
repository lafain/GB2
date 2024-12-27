import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime

class GUIComponents:
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
        
        # Setup chat interface
        self.setup_chat_interface() 
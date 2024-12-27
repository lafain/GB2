import tkinter as tk
from tkinter import ttk

class MainTab:
    def setup_main_tab(self):
        """Setup main control tab"""
        # Goal frame
        goal_frame = ttk.LabelFrame(self.main_tab, text="Goal Configuration")
        goal_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.goal_var = tk.StringVar()
        goal_entry = ttk.Entry(goal_frame, textvariable=self.goal_var)
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
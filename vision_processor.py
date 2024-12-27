import cv2
import numpy as np
from PIL import ImageGrab
import torch
from transformers import AutoProcessor, AutoModelForVision2Seq

class VisionProcessor:
    def __init__(self):
        self.processor = AutoProcessor.from_pretrained("microsoft/kosmos-2-patch14-224")
        self.model = AutoModelForVision2Seq.from_pretrained("microsoft/kosmos-2-patch14-224")
        
    def analyze_screen(self, region=None):
        """Analyze screen content and return description"""
        screenshot = ImageGrab.grab(bbox=region)
        inputs = self.processor(images=screenshot, return_tensors="pt")
        
        with torch.no_grad():
            outputs = self.model.generate(
                pixel_values=inputs["pixel_values"],
                max_length=128,
                num_beams=5
            )
            
        return self.processor.batch_decode(outputs, skip_special_tokens=True)[0] 
import nltk
import os

def download_nltk_data():
    # Download required NLTK data
    nltk.download('punkt')
    nltk.download('stopwords')

def setup_resources():
    # Create resources directory if it doesn't exist
    if not os.path.exists('resources'):
        os.makedirs('resources')
        
    # Create a simple paint icon if it doesn't exist
    if not os.path.exists('resources/paint_icon.png'):
        from PIL import Image
        icon = Image.new('RGB', (32, 32), color='white')
        icon.save('resources/paint_icon.png')

if __name__ == "__main__":
    download_nltk_data()
    setup_resources() 
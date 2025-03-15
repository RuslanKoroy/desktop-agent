import pyautogui
from PIL import Image, ImageDraw
import numpy as np



# Enhanced function to save screenshot with elements
def save_screenshot():
    """Save screenshot with detected UI elements using advanced detection techniques"""
    # Take a new screenshot
    screenshot = np.array(pyautogui.screenshot())

    fullscreen_pil = Image.fromarray(screenshot)
    original_width, original_height = fullscreen_pil.size

    new_height = 512
    new_width = int(original_width * (new_height / original_height))
    resized_fullscreen = fullscreen_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Get the current cursor position
    cursor_x, cursor_y = pyautogui.position()

    # Calculate the resized cursor position
    resized_cursor_x = int(cursor_x * (new_width / original_width))
    resized_cursor_y = int(cursor_y * (new_height / original_height))

    # Draw a red dot at the cursor position
    draw = ImageDraw.Draw(resized_fullscreen)
    draw.ellipse((resized_cursor_x - 5, resized_cursor_y - 5, resized_cursor_x + 5, resized_cursor_y + 5), fill=(255, 0, 0))

    # Save the annotated screenshot
    resized_fullscreen.save('screenshots/fullscreen.jpg', 'JPEG')

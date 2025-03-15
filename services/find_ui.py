import base64
import io
import time
import cv2
import numpy as np
import pyautogui
from PIL import Image
import os
import re
from services.openrouter_api import generate
from services.cache_module import _screenshot_cache, _cache_lock

def encode_image_to_base64(image_path=None, pil_image=None):
    """Convert image to base64 encoding"""
    if pil_image:
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format='JPEG')
        img_data = img_byte_arr.getvalue()
    elif image_path:
        with open(image_path, 'rb') as image_file:
            img_data = image_file.read()
    else:
        raise ValueError("Either image_path or pil_image must be provided")

    return base64.b64encode(img_data).decode('utf-8')

def get_grid_cells_from_cache():
    """Get grid cells from the cache"""
    with _cache_lock:
        return _screenshot_cache.get('grid_cells', [])

def get_current_screenshot():
    """Capture current screenshot and return as OpenCV image"""
    screenshot = pyautogui.screenshot()
    img_np = np.array(screenshot)
    # Convert from RGB to BGR (OpenCV format)
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    return img_cv, screenshot.width, screenshot.height

def llm_choose_best_grid_cell(element_description, grid_image_path, original_image_path, screen_dimensions):
    """
    Ask LLM to choose the best grid cell for the UI element
    """
    screen_width, screen_height = screen_dimensions

    # Load and encode both images to base64
    with open(grid_image_path, 'rb') as grid_file:
        grid_image_base64 = base64.b64encode(grid_file.read()).decode('utf-8')

    with open(original_image_path, 'rb') as original_file:
        original_image_base64 = base64.b64encode(original_file.read()).decode('utf-8')

    # Prepare the prompt with both images
    prompt_text = f'Find grid cell with element "{element_description}"'

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{grid_image_base64}"}}
                #{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{original_image_base64}"}}
            ]
        }
    ]

    system_prompt = "locate_ui_element"
    result = generate(messages, system_prompt)

    return result

def extract_cell_number_from_llm_response(response):
    """Extract grid cell number from the LLM response"""
    # Try to find cell number in the format #X or number X
    cell_pattern = r'#(\d+)'
    match = re.search(cell_pattern, response, re.IGNORECASE)

    if match:
        cell_number = int(match.group(1))
        return cell_number

    # If the pattern doesn't match, try to find any number
    numbers = re.findall(r'\d+', response)
    if numbers:
        # Assume the first number is the cell number
        return int(numbers[0])

    return None

def get_cell_center_coordinates(cell_number):
    """Get the center coordinates of a grid cell from the cache"""
    grid_cells = get_grid_cells_from_cache()

    for cell in grid_cells:
        if cell['index'] == cell_number:
            return cell['center_x'], cell['center_y']

    return None

def ensure_grid_screenshot_exists():
    """Ensure grid screenshot exists, generate if needed"""
    grid_path = 'screenshots/grid.jpg'
    fullscreen_path = 'screenshots/fullscreen.jpg'

    # Check if the required files exist and are recent enough
    if (not os.path.exists(grid_path) or
        not os.path.exists(fullscreen_path) or
        time.time() - os.path.getmtime(grid_path) > 5):  # 5 seconds threshold

        # Import here to avoid circular imports
        from services.screenshot_module import save_screenshot_with_grid

        # Create screenshots directory if needed
        if not os.path.exists('screenshots'):
            os.makedirs('screenshots')

        # Generate new screenshots
        save_screenshot_with_grid()

    return grid_path, fullscreen_path

def get_ui_element_coordinates(screenshot_path=None, element_description=None, screen_width=None, screen_height=None):
    """
    Find UI element coordinates using the grid-based approach and LLM
    """
    # Get screen dimensions if not provided
    if screen_width is None or screen_height is None:
        screen_width, screen_height = pyautogui.size()

    screen_dimensions = (screen_width, screen_height)

    # Ensure we have a recent grid screenshot
    grid_path, fullscreen_path = ensure_grid_screenshot_exists()

    # Use provided screenshot path if given
    if screenshot_path is not None:
        fullscreen_path = screenshot_path
        # We need to regenerate the grid for this custom screenshot
        from services.screenshot_module import save_screenshot_with_grid
        save_screenshot_with_grid()
        grid_path = 'screenshots/grid.jpg'

    # Ask LLM to identify the correct grid cell
    print(f"Asking LLM to identify grid cell for '{element_description}'...")
    llm_response = llm_choose_best_grid_cell(
        element_description,
        grid_path,
        fullscreen_path,
        screen_dimensions
    )
    print(f"LLM response: {llm_response}")

    # Extract cell number from LLM response
    cell_number = extract_cell_number_from_llm_response(llm_response)

    if cell_number:
        # Get coordinates of the cell center
        coordinates = get_cell_center_coordinates(cell_number)
        if coordinates:
            print(f"Found coordinates for cell #{cell_number}: {coordinates}")
            return coordinates

    # If we couldn't get coordinates, fallback to direct coordinate detection
    print("Falling back to direct coordinate detection...")
    return fallback_llm_coordinate_detection(fullscreen_path, element_description, screen_dimensions)

def fallback_llm_coordinate_detection(image_path, element_description, screen_dimensions):
    """Fallback method using only LLM to determine coordinates"""
    screen_width, screen_height = screen_dimensions

    # Load and encode image
    with open(image_path, 'rb') as image_file:
        img_base64 = base64.b64encode(image_file.read()).decode('utf-8')

    # Direct question to LLM about the coordinates
    prompt_text = (
        f"Look at this screenshot and find the exact pixel coordinates (x, y) of the center of "
        f"this UI element: '{element_description}'. The screen resolution is {screen_width}x{screen_height}. "
        f"Respond with ONLY the x and y coordinates in this format: 'x: X, y: Y'"
    )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
            ]
        }
    ]

    system_prompt = "locate_ui_element"
    result = generate(messages, system_prompt)

    # Extract coordinates
    coordinates_pattern = r'x:\s*(\d+(?:\.\d+)?),\s*y:\s*(\d+(?:\.\d+)?)'
    match = re.search(coordinates_pattern, result, re.IGNORECASE)

    if match:
        x = int(float(match.group(1)))
        y = int(float(match.group(2)))
        return x, y

    # Try more flexible pattern if the first one fails
    numbers = re.findall(r'\d+(?:\.\d+)?', result)
    if len(numbers) >= 2:
        x = int(float(numbers[-2]))
        y = int(float(numbers[-1]))
        return x, y

    return None

def move_mouse_to_ui_element(element_description, screenshot_path=None):
    """
    Moves the mouse cursor to the UI element described.

    Args:
        element_description: Natural language description of the UI element
        screenshot_path: Optional path to a screenshot file

    Returns:
        tuple: (x, y) coordinates where the mouse was moved, or None if failed
    """
    # Get screen dimensions
    screen_width, screen_height = pyautogui.size()

    # Get coordinates of the UI element using grid-based method
    coordinates = get_ui_element_coordinates(
        screenshot_path=screenshot_path,
        element_description=element_description,
        screen_width=screen_width,
        screen_height=screen_height
    )

    if coordinates:
        x, y = coordinates
        print(f"Moving mouse to coordinates: x: {x}, y: {y}")

        # Move mouse to the coordinates
        pyautogui.moveTo(x, y, duration=0.5)
        return coordinates
    else:
        print("Failed to find the UI element.")
        return None

def move_mouse_to_grid_cell(cell_number):
    """
    Moves the mouse cursor to the center of the specified grid cell.

    Args:
        cell_number: The grid cell number to move to

    Returns:
        tuple: (x, y) coordinates where the mouse was moved, or None if failed
    """
    coordinates = get_cell_center_coordinates(cell_number)

    if coordinates:
        x, y = coordinates
        print(f"Moving mouse to grid cell #{cell_number} at coordinates: x: {x}, y: {y}")

        # Move mouse to the coordinates
        pyautogui.moveTo(x, y, duration=0.5)
        return coordinates
    else:
        print(f"Failed to find grid cell #{cell_number}.")
        return None
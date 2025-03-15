import os
import time
import numpy as np
import pyautogui
from PIL import Image
import cv2
import threading

from services.cache_module import _screenshot_cache, _cache_lock
from services.cursor_module import get_cursor_position, get_screen_dimensions
from config import NUM_CELLS

# Capture screenshot of area around cursor
def capture_cursor_area(area_size=128):
    x, y = get_cursor_position()
    
    with _cache_lock:
        # Check if we can use cached screenshot
        current_time = time.time()
        if (_screenshot_cache['cursor_area'] is not None and 
            current_time - _screenshot_cache['last_capture_time'] < _screenshot_cache['cache_ttl'] and
            _screenshot_cache['cursor_pos'] == (x, y)):
            return _screenshot_cache['cursor_area']
    
    # Calculate area dimensions
    x_start = max(0, x - int(area_size / 2))
    y_start = max(0, y - int(area_size / 2))
    
    # Ensure area is within screen bounds
    screen_width, screen_height = get_screen_dimensions()
    if x_start + area_size > screen_width:
        x_start = screen_width - area_size
    if y_start + area_size > screen_height:
        y_start = screen_height - area_size
    
    x_start = max(0, x_start)
    y_start = max(0, y_start)
    
    try:
        screenshot = pyautogui.screenshot(region=(x_start, y_start, area_size, area_size))
        
        with _cache_lock:
            # Update cache
            _screenshot_cache['cursor_area'] = screenshot
            _screenshot_cache['last_capture_time'] = time.time()
            _screenshot_cache['cursor_pos'] = (x, y)
        
        return screenshot
    except Exception as e:
        print(f"Error capturing cursor area: {e}")
        # Return a blank image as fallback
        return Image.new('RGB', (area_size, area_size), color='gray')


# Capture and save screenshots
def save_screenshots():
    # Create screenshots directory if it doesn't exist
    if not os.path.exists('screenshots'):
        os.makedirs('screenshots')
    
    with _cache_lock:
        # Reset cache to force new captures
        _screenshot_cache['last_capture_time'] = 0
    
    try:
        # Save screenshot with grid
        save_screenshot_with_grid()
    except Exception as e:
        print(f"Error saving screenshots: {e}")


# Function to create a grid overlay on the screenshot
def save_screenshot_with_grid(num_cells=NUM_CELLS):
    try:
        # Capture the screenshot
        screenshot = np.array(pyautogui.screenshot())
        screenshot_rgb = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
    except Exception as e:
        print(f"Error capturing screenshot: {e}")
        return
    
    # Get screen dimensions
    height, width = screenshot_rgb.shape[:2]
    
    # Calculate grid dimensions
    # We'll aim for approximately num_cells total cells
    # by determining the number of rows and columns needed
    aspect_ratio = width / height
    num_rows = int(np.sqrt(num_cells / aspect_ratio))
    num_cols = int(num_rows * aspect_ratio)
    
    # Ensure we have at least 1000 cells
    while num_rows * num_cols < 500:
        num_rows += 1
        num_cols += 1
    
    # Calculate cell dimensions
    cell_width = width // num_cols
    cell_height = height // num_rows
    
    # Create a copy of the screenshot for annotations
    annotated = np.array(screenshot).copy()
    
    # Store grid information for future use
    grid_info = []
    
    # Draw the grid and add cell numbers
    cell_index = 1
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.3
    font_thickness = 1
    
    for row in range(num_rows):
        for col in range(num_cols):
            # Calculate cell coordinates
            x1 = col * cell_width
            y1 = row * cell_height
            x2 = x1 + cell_width
            y2 = y1 + cell_height
            
            # Store cell information
            grid_info.append({
                'index': cell_index,
                'x': x1,
                'y': y1,
                'width': cell_width,
                'height': cell_height,
                'center_x': x1 + cell_width // 2,
                'center_y': y1 + cell_height // 2
            })
            
            # Draw cell boundary
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 255, 255), 1)
            
            # Add cell number
            text = str(cell_index)
            text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
            text_x = x1 + (cell_width - text_size[0]) // 2
            text_y = y1 + (cell_height + text_size[1]) // 2
            
            # Draw text background for better visibility
            '''
            cv2.rectangle(
                annotated,
                (text_x - 2, text_y - text_size[1] - 2),
                (text_x + text_size[0] + 2, text_y + 2),
                (0, 0, 0), -1
            )'''
            
            # Draw text
            cv2.putText(
                annotated, text, (text_x, text_y),
                font, font_scale, (255, 0, 0), font_thickness
            )
            
            cell_index += 1
    
    # Store grid information in cache
    with _cache_lock:
        _screenshot_cache['grid_cells'] = grid_info
        _screenshot_cache['last_capture_time'] = time.time()
    
    # Mark cursor position
    cursor_x, cursor_y = get_cursor_position()
    cv2.circle(annotated, (cursor_x, cursor_y), 10, (0, 0, 255), -1)
    
    # Find which cell contains the cursor
    cursor_cell = None
    for cell in grid_info:
        if (cell['x'] <= cursor_x < cell['x'] + cell['width'] and 
            cell['y'] <= cursor_y < cell['y'] + cell['height']):
            cursor_cell = cell
            break
    
    # Highlight the cell containing the cursor
    if cursor_cell:
        x1, y1 = cursor_cell['x'], cursor_cell['y']
        x2, y2 = x1 + cursor_cell['width'], y1 + cursor_cell['height']
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Add label for current cursor cell
        cv2.putText(
            annotated, 
            f"Cursor in cell: {cursor_cell['index']}", 
            (10, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
        )
    
    # Convert the annotated screenshot to PIL Image and save/resize
    annotated_pil = Image.fromarray(annotated)
    fullscreen_pil = Image.fromarray(screenshot)
    
    # Save original screenshots
    fullscreen_pil.save('screenshots/fullscreen.jpg', 'JPEG')
    annotated_pil.save('screenshots/grid.jpg', 'JPEG')
    
    # Create and save a resized version for display
    original_width, original_height = annotated_pil.size
    new_height = 512
    new_width = int(original_width * (new_height / original_height))
    
    #resized_fullscreen = fullscreen_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
    #resized_fullscreen.save('screenshots/fullscreen_resized.jpg', 'JPEG')
    
    #resized_annotated = annotated_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
    #resized_annotated.save('screenshots/grid_resized.jpg', 'JPEG')
    
    # Add grid info to text file for reference
    with open('screenshots/grid_info.txt', 'w') as f:
        f.write(f"Screen dimensions: {width}x{height}\n")
        f.write(f"Grid: {num_rows} rows x {num_cols} columns\n")
        f.write(f"Cell size: {cell_width}x{cell_height} pixels\n")
        f.write(f"Total cells: {len(grid_info)}\n")
        if cursor_cell:
            f.write(f"Cursor position: ({cursor_x}, {cursor_y}) in cell {cursor_cell['index']}\n")
        else:
            f.write(f"Cursor position: ({cursor_x}, {cursor_y})\n")


# Function to move cursor to a specified grid cell
def move_cursor_to_cell(cell_index):
    with _cache_lock:
        grid_cells = _screenshot_cache.get('grid_cells', [])
    
    # Find the specified cell
    target_cell = None
    for cell in grid_cells:
        if cell['index'] == cell_index:
            target_cell = cell
            break
    
    if target_cell:
        # Move cursor to the center of the cell
        try:
            pyautogui.moveTo(
                target_cell['center_x'],
                target_cell['center_y'],
                duration=0.2  # Smooth movement
            )
            return True
        except Exception as e:
            print(f"Error moving cursor: {e}")
    else:
        print(f"Cell {cell_index} not found in grid")
    
    return False


# Replace the find_ui_elements function with a grid-based approach
def get_grid_cells():
    """
    Returns the current grid cell information.
    If the grid hasn't been generated yet, returns an empty list.
    """
    with _cache_lock:
        return _screenshot_cache.get('grid_cells', [])
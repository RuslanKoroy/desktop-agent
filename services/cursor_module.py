import pyautogui
from screeninfo import get_monitors

# Get current cursor position
def get_cursor_position():
    return pyautogui.position()


# Get screen dimensions
def get_screen_dimensions():
    monitors = get_monitors()
    if monitors:
        return monitors[0].width, monitors[0].height
    else:
        return pyautogui.size()


# Move cursor to absolute coordinates
def move_cursor_absolute(x, y):
    screen_width, screen_height = get_screen_dimensions()
    # Ensure coordinates are within screen bounds
    x = max(0, min(x, screen_width - 1))
    y = max(0, min(y, screen_height - 1))
    pyautogui.FAILSAFE = False
    pyautogui.moveTo(x, y, duration=0.1)  # Small duration to prevent jumps


# Move cursor by relative offset
def move_cursor_relative(dx, dy):
    current_x, current_y = pyautogui.position()
    screen_width, screen_height = get_screen_dimensions()
    
    # Calculate new position with bounds checking
    new_x = max(0, min(current_x + dx, screen_width - 1))
    new_y = max(0, min(current_y + dy, screen_height - 1))
    
    pyautogui.FAILSAFE = False
    pyautogui.moveTo(new_x, new_y, duration=0.1)


# Mouse button click
def click_mouse_button(button="left"):
    pyautogui.click(button=button)
    return True


# Double click
def double_click(button="left"):
    pyautogui.doubleClick(button=button)
    return True


# Drag from current position to target position
def drag_to(x, y, button="left", duration=0.5):
    screen_width, screen_height = get_screen_dimensions()
    # Ensure coordinates are within screen bounds
    x = max(0, min(x, screen_width - 1))
    y = max(0, min(y, screen_height - 1))
    
    pyautogui.dragTo(x, y, button=button, duration=duration)
    return True


# Press and hold mouse button
def mouse_down(button="left"):
    pyautogui.mouseDown(button=button)
    return True


# Release mouse button
def mouse_up(button="left"):
    pyautogui.mouseUp(button=button)
    return True


# Scroll up or down
def scroll(clicks):
    pyautogui.scroll(clicks)
    return True
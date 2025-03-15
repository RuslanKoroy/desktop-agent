import threading
import time

# Cache for screenshots and UI elements to reduce processing time
_screenshot_cache = {
    'last_capture_time': 0,
    'cache_ttl': 0.3,  # 300ms cache TTL
    'cursor_area': None,
    'ui_elements': None,
    'fullscreen': None,
    'cursor_pos': (0, 0)
}

# Lock for thread safety
_cache_lock = threading.Lock()

# Element detection thresholds
BUTTON_MIN_SIZE = (30, 15)
BUTTON_MAX_SIZE = (300, 100)
TEXTBOX_MIN_SIZE = (100, 20)
TEXTBOX_MAX_SIZE = (800, 50)
ICON_SIZE_RANGE = (16, 64)
MENU_MIN_SIZE = (100, 200)
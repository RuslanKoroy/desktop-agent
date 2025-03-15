# Импорт всех функций из модулей для обратной совместимости
from services.cache_module import (
    _screenshot_cache,
    _cache_lock,
    BUTTON_MIN_SIZE,
    BUTTON_MAX_SIZE,
    TEXTBOX_MIN_SIZE,
    TEXTBOX_MAX_SIZE,
    ICON_SIZE_RANGE,
    MENU_MIN_SIZE
)

from services.cursor_module import (
    get_cursor_position,
    get_screen_dimensions,
    move_cursor_absolute,
    move_cursor_relative,
    click_mouse_button,
    double_click,
    drag_to,
    mouse_down,
    mouse_up,
    scroll
)

from services.keyboard_module import (
    press_key,
    press_hotkey,
    type_text
)

# Для обратной совместимости экспортируем все функции
__all__ = [
    # Cursor module
    'get_cursor_position',
    'get_screen_dimensions',
    'move_cursor_absolute',
    'move_cursor_relative',
    'move_cursor_to_element',
    'move_cursor_to_element_by_index',
    'click_mouse_button',
    'double_click',
    'drag_to',
    'mouse_down',
    'mouse_up',
    'scroll',
    
    # Keyboard module
    'press_key',
    'press_hotkey',
    'type_text',
    
    # Screenshot module
    'capture_cursor_area',
    'save_screenshot',
    
    # UI detection module
    'find_all_ui_elements'  # Добавляем новую функцию в экспорт
]
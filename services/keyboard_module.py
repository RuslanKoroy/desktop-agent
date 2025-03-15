import pyautogui
import pyperclip
import threading
import time

# Press keyboard key
def press_key(key):
    pyautogui.press(key)
    return True


# Press key combination
def press_hotkey(*keys):
    pyautogui.hotkey(*keys)
    return True


# Type text
def type_text(text):
    original_clipboard = pyperclip.paste()
    try:
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')  # Paste the text
        return True
    except Exception as e:
        print(f"Error typing text: {e}")
        return False
    finally:
        # Restore clipboard asynchronously
        def restore_clipboard():
            time.sleep(0.2)  # Small delay to ensure paste completes
            pyperclip.copy(original_clipboard)
        
        threading.Thread(target=restore_clipboard, daemon=True).start()
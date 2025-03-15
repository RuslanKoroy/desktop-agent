import json
from datetime import datetime
import sched
import time
import re
from services.cursor import (
    move_cursor_absolute, 
    move_cursor_relative, 
    click_mouse_button, 
    press_key, 
    double_click,
    drag_to,
    mouse_down,
    mouse_up,
    press_hotkey,
    type_text,
    scroll,
    get_cursor_position
)
from services.find_ui import move_mouse_to_ui_element

listening = False


def extract_json(text):
    # Remove escape characters for correct JSON parsing
    text = text.replace('\\_', '_')

    json_objects = []
    json_str = ""
    in_json = False
    brace_count = 0

    # List to save start and end positions of JSON insertions
    json_positions = []

    # Iterate through text characters
    for index, char in enumerate(text):
        if char == '{':
            if not in_json:
                start_pos = index  # Save JSON start position
                in_json = True
            brace_count += 1
        if in_json:
            json_str += char
        if char == '}':
            brace_count -= 1
            if brace_count == 0 and in_json:
                try:
                    # Try to convert string to JSON
                    json_obj = json.loads(json_str)
                    json_objects.append(json_obj)

                    # Save positions for removing JSON insertion
                    json_positions.append((start_pos, index + 1))
                except json.JSONDecodeError:
                    pass  # Skip invalid insertions
                in_json = False
                json_str = ""

    # Remove JSON insertions from text based on saved positions
    for start, end in reversed(json_positions):
        text = text[:start] + text[end:]

    return json_objects, text.strip()


def process_commands(commands):
    results = []
    try:
        # Process commands in batches for efficiency
        batch_commands = []
        batch_results = []
        
        for command in commands:
            result = {"command": command["command"], "success": True, "message": ""}
            
            try:
                # Group commands that can be batched together
                if command['command'] in ['wait']:
                    # Process any accumulated batch commands first
                    if batch_commands:
                        batch_results = execute_batch_commands(batch_commands)
                        results.extend(batch_results)
                        batch_commands = []
                    
                    # Process the wait command individually
                    seconds = command['params']['seconds']
                    time.sleep(seconds)
                    result["message"] = f"Waited for {seconds} seconds"
                    results.append(result)
                else:
                    # Add command to batch
                    batch_commands.append(command)
                    
                    # If batch size reaches threshold or this is the last command, process the batch
                    if len(batch_commands) >= 3 or command == commands[-1]:
                        batch_results = execute_batch_commands(batch_commands)
                        results.extend(batch_results)
                        batch_commands = []
                        continue
                    
                    # Skip adding this result since it will be added as part of the batch
                    continue
            
            except KeyError as e:
                result["success"] = False
                result["message"] = f"Missing required parameter: {e}"
                results.append(result)
            except Exception as e:
                result["success"] = False
                result["message"] = f"Error executing command: {str(e)}"
                results.append(result)
        
        # Process any remaining batch commands
        if batch_commands:
            batch_results = execute_batch_commands(batch_commands)
            results.extend(batch_results)
    
    except Exception as e:
        print(f"Error processing commands: {e}")
    
    return results


def is_listening():
    global listening
    return listening


def set_listening(value):
    global listening
    listening = value
    return

def execute_batch_commands(commands):
    """Execute a batch of commands efficiently"""
    global listening
    results = []
    
    for command in commands:
        result = {"command": command["command"], "success": True, "message": ""}
        try:
            if command['command'] == 'move_cursor_absolute':
                move_cursor_absolute(command['params']['x'], command['params']['y'])
                result["message"] = f"Moved cursor to absolute position: {command['params']['x']}, {command['params']['y']}"
            
            elif command['command'] == 'move_cursor_relative':
                move_cursor_relative(command['params']['dx'], command['params']['dy'])
                x, y = get_cursor_position()
                result["message"] = f"Moved cursor by offset: {command['params']['dx']}, {command['params']['dy']}. New position: {x}, {y}"
            
            elif command['command'] == 'mouse_button':
                click_mouse_button(command['params']['button'])
                result["message"] = f"Clicked {command['params']['button']} mouse button"
            
            elif command['command'] == 'move_cursor_to_element':
                move_mouse_to_ui_element(command['params']['name'])
                time.sleep(5)
                result["message"] = f"Moved cursor to element {command['params']['name']}"
            
            elif command['command'] == 'double_click':
                button = command['params'].get('button', 'left')
                double_click(button)
                result["message"] = f"Double-clicked {button} mouse button"
            
            elif command['command'] == 'drag_to':
                x = command['params']['x']
                y = command['params']['y']
                button = command['params'].get('button', 'left')
                duration = command['params'].get('duration', 0.5)
                drag_to(x, y, button, duration)
                result["message"] = f"Dragged to position: {x}, {y}"
            
            elif command['command'] == 'mouse_down':
                button = command['params'].get('button', 'left')
                mouse_down(button)
                result["message"] = f"Pressed and held {button} mouse button"
            
            elif command['command'] == 'mouse_up':
                button = command['params'].get('button', 'left')
                mouse_up(button)
                result["message"] = f"Released {button} mouse button"
            
            elif command['command'] == 'press_key':
                press_key(command['params']['key'])
                result["message"] = f"Pressed key: {command['params']['key']}"
            
            elif command['command'] == 'press_hotkey':
                keys = command['params']['keys']
                press_hotkey(*keys)
                result["message"] = f"Pressed hotkey combination: {'+'.join(keys)}"
            
            elif command['command'] == 'enter_text':
                text = command['params']['text']
                type_text(text)
                result["message"] = f"Typed text: {text}"
            
            elif command['command'] == 'scroll':
                clicks = command['params']['clicks']
                scroll(clicks)
                result["message"] = f"Scrolled by {clicks} clicks"
            elif command['command'] == 'listen':
                if not listening:
                    set_listening(True)
                    result["success"] = True
                    result["message"] = f"Waiting for user instructions..."
                    results.append(result)
                return results
            elif command['command'] == 'listen':
                set_listening(True)
                result["success"] = True
                result["message"] = f"<repeat>"
                results.append(result)
                return results
            else:
                result["success"] = False
                result["message"] = f"Unknown command: {command['command']}"
                results.append(result)
                break
        
        except KeyError as e:
            result["success"] = False
            result["message"] = f"Missing required parameter: {e}"
            results.append(result)
            set_listening(False)
            break
        except Exception as e:
            result["success"] = False
            result["message"] = f"Error executing command: {str(e)}"
            results.append(result)
            set_listening(False)
            break
        
        results.append(result)
        time.sleep(0.5)
    
    return results

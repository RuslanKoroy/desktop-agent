# Desktop Agent

A powerful desktop automation tool that allows AI models to control your computer through visual feedback, precise commands, and voice input.

## Features

- **Computer Vision Integration**: Automatically detects UI elements like buttons, textboxes, icons, and menus
- **Smart Cursor Control**: Multiple ways to move the cursor (absolute, relative, or to specific UI elements)
- **Rich Visual Feedback**: Provides the AI with full screen view, cursor area close-up, and detected UI elements
- **Advanced Interaction**: Supports clicks, double-clicks, drag-and-drop, keyboard shortcuts, and text input
- **Voice Control**: Allows users to provide verbal feedback and corrections in real-time
- **Detailed Feedback Loop**: Provides execution results back to the AI for better decision making

## Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`
- For voice input: Microphone and audio drivers

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/RuslanKoroy/desktop-agent.git
   cd desktop-agent
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your API keys in `config.py`

## Usage

Run the desktop agent with a specific task:

```
python main.py "Open Chrome and navigate to youtube.com"
```

### Command Line Options

- `--no-voice`: Disable voice input
- `--voice-model MODEL`: Specify Whisper model size (tiny, base, small, medium, large)
- `--voice-language LANG`: Specify language code for voice recognition (default: ru)
- `--max-iterations N`: Set maximum number of iterations to run

Example with options:
```
python main.py "Open Notepad and type 'Hello, world!'" --voice-model base --voice-language en --max-iterations 20
```

## Voice Feedback

While the agent is running, you can speak into your microphone to provide feedback or corrections. The system will:

1. Continuously listen for voice input
2. Transcribe your speech using the Whisper model
3. Include your feedback in the next message to the AI
4. The AI will adjust its actions based on your verbal instructions

Examples of voice commands you might use:
- "Click on that button instead"
- "Move the cursor to the right"
- "Stop and wait"
- "Type slower"
- "That's not what I wanted, try this instead..."

## How It Works

1. The system captures screenshots of your screen
2. Computer vision algorithms detect UI elements
3. The AI analyzes the screenshots and plans actions
4. Voice input is processed in parallel and provided to the AI
5. Commands are executed to control your computer
6. Results are fed back to the AI for the next decision

## Command Types

The AI can issue various commands to control your computer:

- **Cursor Movement**: Absolute position, relative movement, or to specific UI elements
- **Mouse Actions**: Click, double-click, drag, press and hold, release
- **Keyboard Input**: Press keys, key combinations, or type text
- **Other**: Scroll, wait

## Safety Features

- Configurable failsafe (press ESC to abort)
- Command validation to prevent harmful actions
- Iteration limits to prevent infinite loops
- Voice override to correct or stop actions

## Extending

You can extend the functionality by:

1. Customizing the prompt in `prompts/default.md`
2. Adding new command types in `services/execute_funcs.py`
3. Enhancing voice processing in `services/voice_input.py`

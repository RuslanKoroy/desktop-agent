from openai import OpenAI
from config import OPENROUTER_KEY, MODEL

import os
import time
import threading

# Cache for system prompts to avoid repeated file reads
_prompt_cache = {}
_prompt_cache_lock = threading.Lock()

openrouter_client = OpenAI(
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1",
    timeout=30.0  # Increase timeout for more reliable responses
)

def generate(messages, prompt, replace_dict=None):
    global openrouter_client
    
    # Use cached prompt if available
    prompt_path = f'./prompts/{prompt}.md'
    with _prompt_cache_lock:
        if prompt_path in _prompt_cache:
            system_message = _prompt_cache[prompt_path]
        else:
            # Read prompt from file and cache it
            with open(prompt_path, encoding='utf8') as f:
                system_message = f.read()
            _prompt_cache[prompt_path] = system_message
    
    if replace_dict:
        for key in list(replace_dict.keys()):
            if replace_dict[key]:
                system_message = system_message.replace(key, replace_dict[key])
    
    # Optimize message history by limiting context
    if len(messages) > 10:
        # Keep system message, first user message, and last 8 messages
        messages = [messages[0]] + messages[-9:]

    system_content = [{'role': 'system', 'content': [{"type": "text", "text": system_message}]}]
    system_content = list(system_content) + list(messages)
    print('generating...')
    try:
        start_time = time.time()

        chat_completion = openrouter_client.chat.completions.create(
            model=MODEL, 
            messages=system_content
        )
        end_time = time.time()
        print(f"LLM response time: {end_time - start_time:.2f}s")
        
        generated_text = chat_completion.choices[0].message.content
        return generated_text

    except Exception as e:
        print(f"Error in API call: {e}")
        # Try to recover with a new client instance
        return "Error generating response. Please try again."

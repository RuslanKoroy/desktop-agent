# Отключение предупреждений
import warnings
warnings.filterwarnings("ignore")

from services.cursor import get_cursor_position, get_screen_dimensions, press_hotkey
from services.openrouter_api import generate
from services.execute_funcs import extract_json, process_commands, is_listening, set_listening
from services.image_utils import convert_to_base64
from services.screenshot_utils import save_screenshot
from config import SYSTEM_PROMPT
import os
import json
import time
import argparse
import threading
import asyncio
import queue
import sys
import tkinter as tk
from pynput import keyboard

# Глобальные переменные для управления агентом
agent_running = True
agent_status = "Инициализация"
status_window = None
stop_event = threading.Event()

# Попытка импорта голосового ввода, обработка ошибок
try:
    from services.voice_input import VoiceInputProcessor
    VOICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Voice input functionality not available: {e}")
    print("Running without voice input support.")
    VOICE_AVAILABLE = False

# Глобальные переменные для параллельной обработки
_last_cursor_position = None
_last_screen_dimensions = None
_cursor_position_lock = threading.Lock()
_screen_dimensions_lock = threading.Lock()
_screenshot_queue = queue.Queue()
_command_results_queue = queue.Queue()

# Функция для обновления статуса агента
def update_agent_status(status):
    global agent_status
    agent_status = status
    if status_window:
        status_window.update_status(status)

# Класс для создания окна статуса
class StatusOverlay:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)  # Убираем рамку окна
        self.root.attributes('-topmost', True)  # Поверх всех окон
        self.root.attributes('-alpha', 0.85)  # Полупрозрачность
        
        # Размещаем окно в правом верхнем углу
        screen_width = self.root.winfo_screenwidth()
        window_width = 300
        self.root.geometry(f"{window_width}x80+{screen_width - window_width - 10}+10")
        
        # Создаем рамку
        self.frame = tk.Frame(self.root, bg="#333333", bd=1)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        self.title_label = tk.Label(self.frame, text="Desktop Agent", fg="white", bg="#333333", font=("Arial", 12, "bold"))
        self.title_label.pack(pady=(5, 0))
        
        # Статус
        self.status_label = tk.Label(self.frame, text="Статус: Инициализация", fg="#33ff33", bg="#333333", font=("Arial", 10))
        self.status_label.pack()
        
        # Инструкция
        self.esc_label = tk.Label(self.frame, text="Нажмите ESC чтобы остановить агента", fg="yellow", bg="#333333", font=("Arial", 9))
        self.esc_label.pack(pady=(0, 5))
        
        # Обновление UI каждые 100мс
        self.root.after(100, self.check_running)
    
    def update_status(self, status):
        self.status_label.config(text=f"Статус: {status}")
    
    def check_running(self):
        # Если агент остановлен, закрываем окно
        if not agent_running:
            self.root.destroy()
            return
        self.root.after(100, self.check_running)

# Функция для создания и запуска окна статуса
def run_status_overlay():
    global status_window
    root = tk.Tk()
    status_window = StatusOverlay(root)
    root.mainloop()

# Обработчик нажатия клавиши ESC
def on_esc_press(key):
    global agent_running
    try:
        if key == keyboard.Key.esc:
            print("Нажата клавиша ESC. Останавливаю агента...")
            agent_running = False
            stop_event.set()
            return False  # Прекращаем прослушивание
    except Exception as e:
        print(f"Ошибка при обработке клавиш: {e}")

# Функция для запуска слушателя клавиш
def start_key_listener():
    listener = keyboard.Listener(on_press=on_esc_press)
    listener.start()
    return listener

# Функция для преобразования UI-элементов: убираем width и height, добавляем индекс и группируем координаты в 'position'
def transform_ui_elements(elements):
    transformed = []
    for element in elements:
        transformed.append({
            "index": element.get("index", 0),  # Используем индекс из элемента
            "type": element.get("type", ""),
            "position": {"x": element.get("x", 0), "y": element.get("y", 0)}
        })
    
    # Сортируем по индексу если не все элементы имеют его
    transformed.sort(key=lambda e: e["index"])
    
    # Переназначаем индексы для упорядоченного списка в UI если необходимо
    for idx, element in enumerate(transformed, start=1):
        if element["index"] == 0:
            element["index"] = idx
    
    return transformed

# Функция для создания наглядного текстового представления распознанных объектов
def get_ui_visual_summary(ui_elements):
    summary = "Распознанные UI-элементы:\n"
    for element in ui_elements:
        summary += f"  [{element['index']}] {element['type']} at ({element['position']['x']}, {element['position']['y']})\n"
    return summary

# Фоновой поток для обновления позиции курсора и размеров экрана
def update_position_info():
    global _last_cursor_position, _last_screen_dimensions
    while agent_running:
        with _cursor_position_lock:
            _last_cursor_position = get_cursor_position()
        with _screen_dimensions_lock:
            _last_screen_dimensions = get_screen_dimensions()
        time.sleep(0.05)  # Обновление 20 раз в секунду

def update_screenshots():
    while agent_running:
        save_screenshot()
        time.sleep(0.2)  # Частота 5 раз в секунду

def command_processor_thread():
    """Поток для обработки команд из очереди"""
    while agent_running:
        if not _command_results_queue.empty():
            item = _command_results_queue.get()
            if item is None:  # Сигнал остановки
                break
            commands, callback = item
            update_agent_status("Выполнение команд")
            results = process_commands(commands)
            callback(results)
            _command_results_queue.task_done()
        else:
            time.sleep(0.01)  # Короткий сон для снижения нагрузки на CPU

def run_desktop_agent(task, max_iterations=15, use_voice=True, voice_model="tiny", voice_language="ru"):
    global _last_cursor_position, _last_screen_dimensions, agent_running

    """Запуск desktop-агента с заданной задачей"""
    messages = [{'role': 'user', 'content': [{"type": "text", "text": f"New task: {task}"}]}]
    
    # Инициализация голосового ввода, если включён и доступен
    voice_processor = None
    if use_voice and VOICE_AVAILABLE:
        try:
            voice_processor = VoiceInputProcessor(
                model_name=voice_model,
                language=voice_language,
                # Добавляем функцию обратного вызова для мгновенной обработки
                callback=lambda text: print(f"[Callback] Распознано: {text}")
            )
            voice_processor.start()
            print("Voice input включён. Говорите для обратной связи или корректировки.")
        except Exception as e:
            print(f"Ошибка инициализации голосового ввода: {e}")
            print("Продолжаем работу без голосового ввода.")
            use_voice = False
    else:
        if use_voice and not VOICE_AVAILABLE:
            print("Голосовой ввод запрошен, но не доступен. Проверьте зависимости.")
            print("Продолжаем работу без голосового ввода.")
        use_voice = False
    
    # Запуск фоновых потоков
    position_thread = threading.Thread(target=update_position_info, daemon=True)
    position_thread.start()

    press_hotkey('win', 'd')
    time.sleep(2)
    save_screenshot()
    
    cmd_processor = threading.Thread(target=command_processor_thread, daemon=True)
    cmd_processor.start()
    
    conversion_threads = []
    
    # Событие для ожидания завершения выполнения команд
    cmd_feedback_event = threading.Event()
    command_results = []
    
    def command_callback(results):
        nonlocal command_results
        command_results = results
        cmd_feedback_event.set()
    
    # Функция для обработки голосового ввода
    def process_voice_input():
        voice_feedback = None
        if use_voice and voice_processor:
            # Проверяем, идет ли процесс распознавания
            if voice_processor.is_processing():
                update_agent_status("Распознавание речи")
                print("Идет распознавание речи...")
                return None
                
            # Уменьшаем время ожидания до 0.5 секунд 
            # для более частых проверок транскрипций
            poll_start = time.time()
            while time.time() - poll_start < 0.5:
                transcriptions = voice_processor.get_all_transcriptions()
                if transcriptions:
                    for transcription in transcriptions:
                        if transcription and "МУЗЫКА" not in transcription and "Субтит" not in transcription and "субтит" not in transcription:
                            voice_feedback = transcription.strip()
                            print(f"Получен голосовой ввод: {voice_feedback}")
                            
                            # Прямая обработка критичных команд
                            lower_feedback = voice_feedback.lower()
                            if lower_feedback in ["стоп", "останови", "прекрати"]:
                                print("Получена команда остановки!")
                                return "STOP_COMMAND"
                            elif lower_feedback in ["пауза", "подожди"]:
                                print("Получена команда паузы!")
                                update_agent_status("На паузе")
                                set_listening(True)
                                return None
                            elif lower_feedback in ["продолжай", "продолжить", "дальше"]:
                                print("Получена команда продолжения!")
                                update_agent_status("Работаю")
                                set_listening(False)
                                return None
                            
                            set_listening(False)
                            return voice_feedback
                # Более частые проверки
                time.sleep(0.05)
        return voice_feedback

    i = 0
    try:
        # Основной цикл работы агента
        while i < max_iterations and agent_running:
            if stop_event.is_set():
                print("Получен сигнал остановки. Завершаю работу агента.")
                break
                
            print(f"\n--- Итерация {i+1}/{max_iterations} ---")
            
            # Индикатор распознавания для пользовательской обратной связи
            if use_voice and voice_processor and voice_processor.is_processing():
                update_agent_status("Распознавание речи")
                print("== Идет распознавание речи... ==")
                time.sleep(0.1)  # Короткая пауза, чтобы не забивать консоль
                continue  # Пропускаем итерацию, пока идет распознавание
            
            # Обработка голосового ввода до всех остальных действий
            voice_feedback = process_voice_input()
            
            # Специальные команды
            if voice_feedback == "STOP_COMMAND":
                print("Выполнение остановлено по голосовой команде.")
                agent_running = False
                break
            
            # Если мы в режиме ожидания, но получили голосовой ввод, перестаем ждать
            if is_listening() and voice_feedback:
                set_listening(False)
            
            # Если все еще в режиме ожидания и нет голосового ввода, пропускаем итерацию
            if is_listening() and not voice_feedback:
                update_agent_status("Ожидание пользователя")
                print('== Ожидаю запрос пользователя ==')
                time.sleep(0.2)  # Небольшая задержка перед следующей проверкой
                if use_voice:
                    continue
                else:
                    voice_feedback = input('>> ')

            update_agent_status("Анализ экрана")
            save_screenshot()
            
            # Параллельное преобразование скриншотов в base64
            fullscreen_img = None
            def convert_screenshots():
                nonlocal fullscreen_img
                fullscreen_img = convert_to_base64('screenshots/fullscreen.jpg')
            convert_thread = threading.Thread(target=convert_screenshots)
            convert_thread.start()
            conversion_threads.append(convert_thread)
            
            # Очистка завершённых потоков конвертации
            for thread in conversion_threads[:]:
                if not thread.is_alive():
                    thread.join()
                    conversion_threads.remove(thread)
            
            # Ожидание завершения конвертации скриншотов
            convert_thread.join()

            message_content = [
                {"type": "text", "text": "Fullscreen screenshot:"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{fullscreen_img}"}}
            ]

            # Добавление голосового ввода, если он доступен (сразу для текущей итерации)
            if voice_feedback:
                message_content.append({"type": "text", "text": f"Voice feedback: {voice_feedback}"})
                print(f"Обрабатываю голосовой ввод немедленно: {voice_feedback}")
            
            temp_messages = list(messages)
            if temp_messages[-1]['role'] == 'user':
                temp_messages[-1]['content'].extend(message_content)
            else:
                temp_messages.append({'role': 'user', 'content': message_content})

            #messages = list(temp_messages)
            if messages[-1]['role'] == 'user':
                messages[-1]['content'].append({"type": "text", "text": f"'*Screenshots hidden by system*'"})
            else:
                messages.append({'role': 'user', 'content': [{'role': 'user', 'content': [{"type": "text", "text": f"'*Screenshots hidden by system*'"}]}]})

            # Генерация ответа от LLM
            update_agent_status("Анализ и обработка")
            generated_text = generate(list(temp_messages), SYSTEM_PROMPT)
            
            # Извлечение команд и текста из ответа
            commands, text = extract_json(generated_text)

            print("\nОтвет ассистента:")
            print(generated_text)
            
            # Обработка команд, если они есть
            if commands:
                print("\nВыполнение команд:")
                update_agent_status("Выполнение команд")
                cmd_feedback_event.clear()
                command_results = process_commands(commands)

                results_text = "Результаты выполнения команд:\n"
                for result in command_results:
                    status = "+" if result["success"] else "-"
                    results_text += f"{status} {result['command']}: {result['message']}\n"
                print(results_text)
                
                feedback_message = {"type": "text", "text": results_text}
                if messages[-1]['role'] == 'user':
                    messages.append({'role': 'assistant', 'content': [feedback_message]})
                else:
                    messages[-1]['content'].append({"type": "text", "text": feedback_message})
                
                # Обрезка истории, если она становится слишком длинной
                if len(messages) > 15:
                    system_message = messages[0]
                    recent_messages = messages[-14:]
                    messages = [system_message] + recent_messages
                time.sleep(0.5)
            else:
                update_agent_status("Ожидание")
                time.sleep(0.5)
            i += 1
            
            # Обновляем статус на "Работаю" после всех операций
            if agent_running and not is_listening():
                update_agent_status("Работаю")
                
    finally:
        update_agent_status("Завершение работы")
        agent_running = False
        if voice_processor:
            voice_processor.stop()
        _command_results_queue.put(None)
        if cmd_processor.is_alive():
            cmd_processor.join(timeout=1.0)
        print("Агент остановлен.")

if __name__ == "__main__":
    import sys
    parser = argparse.ArgumentParser(description="Desktop Agent с голосовым управлением")
    parser.add_argument("task", nargs="?", default="Open Chrome and navigate to youtube.com", 
                        help="Задача для выполнения")
    parser.add_argument("--no-voice", action="store_true", help="Отключить голосовой ввод")
    parser.add_argument("--voice-model", default="tiny", choices=["tiny", "base", "small", "medium", "large"],
                        help="Размер модели Whisper для распознавания голоса")
    parser.add_argument("--voice-language", default="ru", help="Языковой код для распознавания голоса")
    parser.add_argument("--max-iterations", type=int, default=15, 
                        help="Максимальное число итераций")
    
    args = parser.parse_args()
    
    print(f"Запуск desktop-агента с задачей: {args.task}")
    print(f"Голосовой ввод: {'отключён' if args.no_voice else 'включён'}")
    
    # Запускаем статусное окно в отдельном потоке
    status_thread = threading.Thread(target=run_status_overlay, daemon=True)
    status_thread.start()
    
    # Запускаем слушатель клавиш в отдельном потоке
    key_listener = start_key_listener()
    
    update_agent_status("Запуск")
    
    try:
        run_desktop_agent(
            task=args.task,
            max_iterations=args.max_iterations,
            use_voice=not args.no_voice,
            voice_model=args.voice_model,
            voice_language=args.voice_language
        )
    except Exception as e:
        print(f"Ошибка в работе агента: {e}")
    finally:
        agent_running = False
        if key_listener.is_alive():
            key_listener.stop()
        print("Программа завершена.")
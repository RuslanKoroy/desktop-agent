import threading
import queue
import time
import numpy as np
import sounddevice as sd
import os
import torch
import concurrent.futures

# Импортируем Whisper (с учётом альтернативных путей)
try:
    import openai.whisper as whisper
except ImportError:
    try:
        from openai import whisper
    except ImportError:
        try:
            import whisper
        except ImportError:
            print("ERROR: Не удалось импортировать whisper. Установите его через: pip install git+https://github.com/openai/whisper.git")
            whisper = None

class VoiceInputProcessor:
    def __init__(self, model_name="tiny", language="ru", sample_rate=16000, device=None, vad_threshold=0.05, callback=None):
        """
        Инициализация процессора голосового ввода.
        
        Args:
            model_name: Размер модели Whisper ("tiny", "base", "small", "medium", "large")
            language: Языковой код для распознавания речи
            sample_rate: Частота дискретизации аудио в Гц
            device: Устройство PyTorch (None для автоопределения)
            vad_threshold: Порог для обнаружения голосовой активности (выше = менее чувствительно)
            callback: Функция обратного вызова для мгновенной передачи распознанного текста
        """
        if whisper is None:
            raise ImportError("Модуль Whisper не найден. Голосовой ввод отключён.")
            
        self.model_name = model_name
        self.language = language
        self.sample_rate = sample_rate
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.use_fp16 = self.device == "cuda"
        
        print(f"Загрузка модели Whisper {model_name} на {self.device}...")
        self.model = whisper.load_model(model_name, device=self.device, download_root=os.path.join(os.path.expanduser("~"), ".cache", "whisper"))
        self.model.eval()
        print("Модель Whisper успешно загружена")
        
        self.audio_queue = queue.Queue()
        self.text_queue = queue.Queue()
        self.is_running = False
        self.thread = None
        
        # Улучшенные параметры голосовой активности
        self.vad_threshold = vad_threshold
        self.silence_duration = 0.3        # Уменьшено для более быстрого завершения записи после паузы
        self.max_record_duration = 3.0     # Ограничиваем максимальную длительность для быстрой обработки
        self.min_speech_duration = 0.2     # Минимальная длительность, чтобы считаться речью
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.futures = []
        self.audio_buffer = []
        self.last_speech_time = 0
        self.recording_start_time = 0
        self.is_recording = False
        
        self.callback = callback  # Функция обратного вызова для мгновенной передачи текста
        
        # Добавляем индикатор состояния распознавания для пользователя
        self.processing_indicator = False
    
    def audio_callback(self, indata, frames, time_info, status):
        """Callback для sounddevice для захвата аудио данных"""
        if status:
            print(f"Audio callback status: {status}")
        
        audio_data = indata.copy()
        if audio_data.shape[1] > 1:
            audio_data = np.mean(audio_data, axis=1)
        else:
            audio_data = audio_data.flatten()
        
        self.audio_buffer.extend(audio_data.tolist())
        
        energy = np.mean(np.abs(audio_data))
        current_time = time.time()
        
        if energy > self.vad_threshold:
            if not self.is_recording:
                self.is_recording = True
                self.recording_start_time = current_time
                print("Речь обнаружена, запись началась...")
            self.last_speech_time = current_time
        
        if self.is_recording:
            recording_duration = current_time - self.recording_start_time
            silence_duration = current_time - self.last_speech_time
            
            # Проверяем, нужно ли завершить запись
            if (silence_duration >= self.silence_duration or 
                recording_duration >= self.max_record_duration):
                if recording_duration >= self.min_speech_duration:
                    audio_array = np.array(self.audio_buffer, dtype=np.float32)
                    self.audio_queue.put(audio_array)
                    self.processing_indicator = True  # Включаем индикатор обработки
                    print(f"Добавлено {recording_duration:.2f} с аудио в очередь на обработку")
                else:
                    print(f"Запись отброшена - слишком короткая ({recording_duration:.2f}с)")
                self.audio_buffer = []
                self.is_recording = False
    
    def _transcribe_audio(self, audio_data):
        """Распознавание аудио данных в отдельном потоке"""
        print("Начало распознавания...")
        start_time = time.time()
        
        # Ускорение распознавания для маленьких моделей
        if self.model_name in ["tiny", "base"]:
            # Уменьшаем complexity для более быстрого распознавания
            result = self.model.transcribe(
                audio_data, 
                language=self.language, 
                fp16=self.use_fp16,
                beam_size=3        # Уменьшаем размер луча для быстроты
            )
        else:
            result = self.model.transcribe(audio_data, language=self.language, fp16=self.use_fp16)
            
        end_time = time.time()
        transcription = result["text"].strip()
        print(f"Распознавание завершено за {end_time - start_time:.2f} секунд: '{transcription}'")
        self.processing_indicator = False  # Выключаем индикатор обработки
        return transcription if transcription else None
    
    def process_audio_queue(self):
        """Обработка аудио очереди с использованием Whisper"""
        while self.is_running:
            try:
                # Установим меньший таймаут для более быстрого реагирования на завершение
                audio_data = self.audio_queue.get(timeout=0.2)
                queue_size = self.audio_queue.qsize()
                if queue_size > 0:
                    print(f"В очереди еще {queue_size} аудиофрагментов")
                    
                if np.max(np.abs(audio_data)) > 0:
                    audio_data = audio_data / np.max(np.abs(audio_data))
                
                # Отменяем все незавершенные задачи распознавания при добавлении новой
                # чтобы не создавать большую очередь обработки
                for future in self.futures:
                    if not future.done():
                        future.cancel()
                
                future = self.executor.submit(self._transcribe_audio, audio_data)
                self.futures = [future]  # Заменяем список будущих задач одной текущей
                
                completed_futures = []
                for future in self.futures:
                    if future.done():
                        try:
                            transcription = future.result()
                            if transcription:
                                print(f"Распознано и отправлено: {transcription}")
                                self.text_queue.put(transcription)
                                if self.callback:
                                    self.callback(transcription)
                        except Exception as e:
                            print(f"Ошибка при распознавании: {e}")
                        completed_futures.append(future)
                self.futures = [f for f in self.futures if f not in completed_futures]
                self.audio_queue.task_done()
            
            except queue.Empty:
                # Проверяем завершенные задачи даже когда нет новых данных
                completed_futures = []
                for future in self.futures:
                    if future.done():
                        try:
                            transcription = future.result()
                            if transcription:
                                print(f"Распознано и отправлено: {transcription}")
                                self.text_queue.put(transcription)
                                if self.callback:
                                    self.callback(transcription)
                        except Exception as e:
                            print(f"Ошибка при распознавании: {e}")
                        completed_futures.append(future)
                self.futures = [f for f in self.futures if f not in completed_futures]
                continue
            except Exception as e:
                print(f"Ошибка обработки аудио: {e}")
    
    def start(self):
        """Запуск процессора голосового ввода"""
        if self.is_running:
            return
        
        self.is_running = True
        self.futures = []
        self.thread = threading.Thread(target=self.process_audio_queue)
        self.thread.daemon = True
        self.thread.start()
        
        self.stream = sd.InputStream(
            callback=self.audio_callback,
            channels=1,
            samplerate=self.sample_rate,
            blocksize=int(self.sample_rate * 0.2)  # Уменьшаем блоки до 200 мс для более быстрой реакции
        )
        self.stream.start()
        print("Процессор голосового ввода запущен")
    
    def stop(self):
        """Остановка процессора голосового ввода"""
        if not self.is_running:
            return
        
        self.is_running = False
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        if self.executor:
            self.executor.shutdown(wait=False)
            for future in self.futures:
                future.cancel()
        if self.thread:
            self.thread.join(timeout=2.0)
        print("Процессор голосового ввода остановлен")
    
    def get_transcription(self, block=False, timeout=None):
        """
        Получить последнюю транскрипцию из очереди.
        
        Args:
            block: блокировать до появления транскрипции
            timeout: таймаут в секундах, если block=True
            
        Returns:
            Текст транскрипции или None, если очередь пуста.
        """
        try:
            return self.text_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def get_all_transcriptions(self):
        """Получить все доступные транскрипции из очереди"""
        transcriptions = []
        while not self.text_queue.empty():
            transcriptions.append(self.text_queue.get())
        return transcriptions
    
    def is_processing(self):
        """Проверяет, идет ли процесс распознавания"""
        return self.processing_indicator
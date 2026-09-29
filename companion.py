"""
Mini Companion - реагує на рухи миші та зміни вікна
Сумісний з Python 3.14+
"""

import threading
import time
import tkinter as tk
from pynput import mouse
from typing import Tuple, Optional
import sys

try:
    import pygetwindow as gw
    WINDOW_TRACKING = True
except ImportError:
    WINDOW_TRACKING = False
    print("⚠️  pygetwindow не встановлена. Стеження за вікнами вимкнено.")


class MiniCompanion:
    """Міні-компаньйон що реагує на курсор і вікна"""
    
    # Емодзі для різних станів
    FACES = {
        "idle": "🙂",
        "watching": "👀",
        "click": "😄",
        "window": "🪟",
        "thinking": "🤔",
        "surprised": "😮",
        "happy": "😊",
        "yawn": "😴"
    }
    
    def __init__(self, width: int = 120, height: int = 120):
        """Ініціалізація компаньйона"""
        self.width = width
        self.height = height
        
        # Основне вікно Tkinter
        self.root = tk.Tk()
        self.root.title("Mini Companion")
        self.root.overrideredirect(True)  # без системної рамки
        self.root.attributes("-topmost", True)  # завжди на верхньому шарі
        self.root.attributes("-alpha", 0.95)  # напівпрозорість
        self.root.wm_attributes("-transparentcolor", "black")  # чорний фон прозорий
        self.root.geometry(f"{width}x{height}+200+200")
        self.root.configure(bg="black")
        
        # Етикетка з емодзі
        self.label = tk.Label(
            self.root,
            text=self.FACES["idle"],
            font=("Segoe UI Emoji", 48),
            bg="black",
            fg="white",
            padx=10,
            pady=10
        )
        self.label.pack(expand=True)
        
        # Стан компаньйона
        self.state = "idle"
        self.state_changed_time = time.time()
        self.current_active_window: Optional[str] = None
        self.mouse_x = 0
        self.mouse_y = 0
        self.clicks_count = 0
        
        print("✅ Mini Companion запущено")
        print(f"📊 Python {sys.version}")
        print("🎮 Рухай мишею та клікай!")
    
    def set_state(self, new_state: str, duration: float = 1.2) -> None:
        """Встановити новий стан компаньйона"""
        if new_state not in self.FACES:
            print(f"⚠️  Невідомий стан: {new_state}")
            return
        
        self.state = new_state
        self.state_changed_time = time.time()
        
        # Оновити емодзі
        self.label.config(text=self.FACES[new_state])
        
        # Повернути до idle після затримки
        self.root.after(
            int(duration * 1000),
            lambda: self._restore_idle_if_needed(new_state, duration)
        )
    
    def _restore_idle_if_needed(self, prev_state: str, duration: float) -> None:
        """Повернути до idle якщо стан не змінився"""
        elapsed = time.time() - self.state_changed_time
        if self.state == prev_state and elapsed >= duration - 0.1:
            self.set_state("idle", 0.5)
    
    def on_move(self, x: int, y: int) -> None:
        """Реакція на рух миші"""
        self.mouse_x = x
        self.mouse_y = y
        
        if self.state not in ["click", "surprised", "thinking"]:
            self.set_state("watching", 0.3)
    
    def on_click(self, x: int, y: int, button, pressed: bool) -> None:
        """Реакція на клік миші"""
        if not pressed:
            return
        
        self.clicks_count += 1
        button_name = str(button).split(".")[-1]
        
        if button_name == "left":
            self.set_state("click", 0.6)
            print(f"👆 Лівий клік! Всього кліків: {self.clicks_count}")
        
        elif button_name == "right":
            self.set_state("surprised", 1.0)
            print(f"🔧 Правий клік!")
        
        elif button_name == "middle":
            self.set_state("happy", 0.8)
            print(f"🎯 Середній клік!")
    
    def window_watcher(self) -> None:
        """Стеження за активним вікном (фоновий потік)"""
        if not WINDOW_TRACKING:
            return
        
        while True:
            try:
                window = gw.getActiveWindow()
                title = window.title if window else "Без активного вікна"
                
                # Якщо вікно змінилось
                if title != self.current_active_window:
                    self.current_active_window = title
                    print(f"🪟 Активне вікно: {title[:50]}")
                    
                    # Різні реакції на різні вікна
                    if any(app in title.lower() for app in ["chrome", "firefox", "edge"]):
                        self.set_state("thinking", 1.5)
                    elif any(app in title.lower() for app in ["code", "studio", "sublime"]):
                        self.set_state("thinking", 1.2)
                    elif any(app in title.lower() for app in ["discord", "telegram", "slack"]):
                        self.set_state("happy", 1.0)
                    else:
                        self.set_state("window", 1.0)
                
            except Exception as e:
                # Мовчазно ігноруємо помилки
                pass
            
            # Перевіряємо кожні 250 мс
            time.sleep(0.25)
    
    def update_position(self) -> None:
        """Оновити позицію компаньйона біля курсора"""
        # Позиція трохи праворуч від курсора
        x = self.mouse_x + 30
        y = self.mouse_y + 30
        
        # Обмеження екраном
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        
        if x > screen_w - self.width:
            x = screen_w - self.width
        if y > screen_h - self.height:
            y = screen_h - self.height
        if x < 0:
            x = 0
        if y < 0:
            y = 0
        
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
        # Оновити позицію кожні 30 мс
        self.root.after(30, self.update_position)
    
    def start(self) -> None:
        """Запустити компаньйона"""
        # Слухач миші
        self.listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click
        )
        self.listener.start()
        
        # Потік стеження за вікнами
        if WINDOW_TRACKING:
            self.window_thread = threading.Thread(
                target=self.window_watcher,
                daemon=True
            )
            self.window_thread.start()
        
        # Оновлення позиції
        self.root.after(30, self.update_position)
        
        # Запуск основного цикла
        self.root.mainloop()
    
    def stop(self) -> None:
        """Зупинити компаньйона"""
        self.listener.stop()
        self.root.quit()


def main():
    """Головна функція"""
    print("🎮 Mini Companion для Python 3.14")
    print("=" * 50)
    print("📝 Налаштування:")
    print("   • Ширина: 120 пікселів")
    print("   • Висота: 120 пікселів")
    print("   • Стан: Активна стеження за мишею та вікнами")
    print("=" * 50)
    
    try:
        companion = MiniCompanion()
        companion.start()
    except KeyboardInterrupt:
        print("\n👋 До побачення!")
    except Exception as e:
        print(f"❌ Помилка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

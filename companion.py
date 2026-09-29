"""
Mini Companion - реагує на рухи миші та зміни вікна
Сумісний з Python 3.14+
Версія з вибором папки для PNG емоцій
"""

import threading
import time
import tkinter as tk
from tkinter import filedialog
from tkinter import PhotoImage
from pynput import mouse
from typing import Optional, Dict
import sys
import os
from pathlib import Path

try:
    import pygetwindow as gw
    WINDOW_TRACKING = True
except ImportError:
    WINDOW_TRACKING = False
    print("⚠️  pygetwindow не встановлена. Стеження за вікнами вимкнено.")


class MiniCompanion:
    """Міні-компаньйон що реагує на утримування та вікна"""
    
    # Стани компаньйона
    STATES = [
        "idle",
        "watching",
        "click",
        "window",
        "thinking",
        "surprised",
        "happy",
        "yawn",
        "dragging"
    ]
    
    def __init__(self, width: int = 120, height: int = 120, assets_dir: Optional[Path] = None):
        """Ініціалізація компаньйона"""
        self.width = width
        self.height = height
        
        # Вибір папки з емоціями
        if assets_dir is None:
            self.assets_dir = self._select_emotions_folder()
        else:
            self.assets_dir = Path(assets_dir)
        
        if self.assets_dir is None:
            print("❌ Папка не вибрана. Вихід.")
            sys.exit(0)
        
        print(f"📁 Директорія емоцій: {self.assets_dir.absolute()}")
        
        # Основне вікно Tkinter
        self.root = tk.Tk()
        self.root.title("Mini Companion")
        self.root.overrideredirect(True)  # без системної рамки
        self.root.attributes("-topmost", True)  # завжди на верхньому шарі
        self.root.attributes("-alpha", 0.95)  # напівпрозорість
        self.root.wm_attributes("-transparentcolor", "black")  # чорний фон прозорий
        self.root.geometry(f"{width}x{height}+200+200")
        self.root.configure(bg="black")
        
        # Етикетка для зображення або тексту
        self.label = tk.Label(
            self.root,
            text="🙂",
            font=("Segoe UI Emoji", 48),
            bg="black",
            fg="white",
            padx=10,
            pady=10
        )
        self.label.pack(expand=True)
        
        # Кешування зображень
        self.images_cache: Dict[str, PhotoImage] = {}
        self._load_images()
        
        # Стан компаньйона
        self.state = "idle"
        self.state_changed_time = time.time()
        self.current_active_window: Optional[str] = None
        self.mouse_x = 0
        self.mouse_y = 0
        self.companion_x = 200
        self.companion_y = 200
        self.clicks_count = 0
        
        # Режим утримування (перетягування)
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.companion_drag_offset_x = 0
        self.companion_drag_offset_y = 0
        
        # Слухачі миші
        self.listener = None
        
        # Інформаційна панель
        self._print_info()
    
    def _select_emotions_folder(self) -> Optional[Path]:
        """Вибрати папку з емоціями через діалог"""
        print("\n" + "=" * 60)
        print("🎨 Виберіть папку з PNG емоціями")
        print("=" * 60)
        
        # Створити приховане вікно для діалогу
        root = tk.Tk()
        root.withdraw()
        
        folder_path = filedialog.askdirectory(
            title="Виберіть папку з PNG емоціями для Mini Companion",
            initialdir=str(Path.home())
        )
        
        root.destroy()
        
        if folder_path:
            return Path(folder_path)
        else:
            return None
    
    def _print_info(self) -> None:
        """Вивести інформацію про запуск"""
        print("\n" + "=" * 60)
        print("🎮 Mini Companion для Python 3.14")
        print("=" * 60)
        print("📝 Налаштування:")
        print(f"   • Розмір: {self.width}x{self.height} пікселів")
        print(f"   • Директорія емоцій: {self.assets_dir.absolute()}")
        print("=" * 60)
        print("🎮 Керування:")
        print("   • УТРИМУЙ компаньйона - переміщення")
        print("   • ОТПУСТИ - компаньйон зупиняється")
        print("   • Лівий клік - 😄 (реакція)")
        print("   • Правий клік - 😮 (реакція)")
        print("   • Зміна вікна - 🪟 (реакція)")
        print("=" * 60)
        print("📂 Очікувані PNG файли у папці:")
        for state in self.STATES:
            print(f"      • {state}.png")
        print("=" * 60 + "\n")
    
    def _load_images(self) -> None:
        """Завантажити PNG емоції з папки"""
        print("🖼️  Завантаження емоцій...")
        
        if not self.assets_dir.exists():
            print(f"❌ Папка не існує: {self.assets_dir}")
            return
        
        # Пошук усіх PNG файлів у папці
        png_files = list(self.assets_dir.glob("*.png"))
        
        if not png_files:
            print(f"⚠️  У папці {self.assets_dir} немає PNG файлів")
            print("   Використовуватимуться стандартні емодзі")
            return
        
        print(f"   📊 Знайдено PNG файлів: {len(png_files)}")
        
        for state in self.STATES:
            image_path = self.assets_dir / f"{state}.png"
            
            if image_path.exists():
                try:
                    # Завантажити зображення
                    img = PhotoImage(file=str(image_path))
                    
                    # Масштабувати до розміру вікна (якщо потрібно)
                    original_w = img.width()
                    original_h = img.height()
                    
                    if original_w > self.width or original_h > self.height:
                        scale_x = max(1, original_w // self.width)
                        scale_y = max(1, original_h // self.height)
                        scale = max(scale_x, scale_y)
                        img = img.subsample(scale, scale)
                    
                    self.images_cache[state] = img
                    print(f"   ✅ Завантажено: {state}.png ({original_w}x{original_h})")
                
                except Exception as e:
                    print(f"   ❌ Помилка завантаження {state}.png: {e}")
            else:
                print(f"   ⚠️  Не знайдено: {state}.png")
        
        print(f"   📊 Всього завантажено: {len(self.images_cache)}/{len(self.STATES)} емоцій\n")
    
    def set_state(self, new_state: str, duration: float = 1.2) -> None:
        """Встановити новий стан компаньйона"""
        if new_state not in self.STATES:
            print(f"⚠️  Невідомий стан: {new_state}")
            return
        
        if self.is_dragging and new_state != "dragging":
            return  # Не змінювати стан під час перетягування
        
        self.state = new_state
        self.state_changed_time = time.time()
        
        # Використати PNG зображення якщо є, інакше використати емодзі
        if new_state in self.images_cache:
            self.label.config(image=self.images_cache[new_state], text="")
        else:
            # Fallback емодзі
            fallback_faces = {
                "idle": "🙂",
                "watching": "👀",
                "click": "😄",
                "window": "🪟",
                "thinking": "🤔",
                "surprised": "😮",
                "happy": "😊",
                "yawn": "😴",
                "dragging": "✋"
            }
            self.label.config(text=fallback_faces.get(new_state, "🙂"), image="")
        
        # Повернути до idle після затримки (якщо не перетягується)
        if not self.is_dragging:
            self.root.after(
                int(duration * 1000),
                lambda: self._restore_idle_if_needed(new_state, duration)
            )
    
    def _restore_idle_if_needed(self, prev_state: str, duration: float) -> None:
        """Повернути до idle якщо стан не змінився"""
        if not self.is_dragging:
            elapsed = time.time() - self.state_changed_time
            if self.state == prev_state and elapsed >= duration - 0.1:
                self.set_state("idle", 0.5)
    
    def on_move(self, x: int, y: int) -> None:
        """Реакція на рух миші"""
        self.mouse_x = x
        self.mouse_y = y
        
        # Якщо перетягуємо компаньйона
        if self.is_dragging:
            new_x = x - self.companion_drag_offset_x
            new_y = y - self.companion_drag_offset_y
            
            # Обмежити екраном
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            
            new_x = max(0, min(new_x, screen_w - self.width))
            new_y = max(0, min(new_y, screen_h - self.height))
            
            self.companion_x = new_x
            self.companion_y = new_y
            self.root.geometry(f"{self.width}x{self.height}+{new_x}+{new_y}")
            
            self.set_state("dragging")
    
    def on_click(self, x: int, y: int, button, pressed: bool) -> None:
        """Реакція на клік миші"""
        # Перевірити, чи клік на компаньйона
        is_on_companion = (
            self.companion_x <= x <= self.companion_x + self.width and
            self.companion_y <= y <= self.companion_y + self.height
        )
        
        if pressed:
            if is_on_companion:
                # Почати перетягування
                if str(button).split(".")[-1] == "left":
                    self.is_dragging = True
                    self.companion_drag_offset_x = x - self.companion_x
                    self.companion_drag_offset_y = y - self.companion_y
                    self.set_state("dragging")
                    print("✋ Утримування...")
            else:
                # Клік поза компаньйоном
                self.clicks_count += 1
                button_name = str(button).split(".")[-1]
                
                if button_name == "left":
                    self.set_state("click", 0.6)
                    print(f"👆 Лівий клік! Всього кліків: {self.clicks_count}")
                
                elif button_name == "right":
                    self.set_state("surprised", 1.0)
                    print("🔧 Правий клік!")
                
                elif button_name == "middle":
                    self.set_state("happy", 0.8)
                    print("🎯 Середній клік!")
        else:
            # Випустити клавішу
            if self.is_dragging:
                self.is_dragging = False
                print("🛑 Опущено")
                self.set_state("idle")
    
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
                
            except Exception:
                pass
            
            # Перевіряємо кожні 250 мс
            time.sleep(0.25)
    
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
        
        # Запуск основного цикла
        self.root.mainloop()
    
    def stop(self) -> None:
        """Зупинити компаньйона"""
        if self.listener:
            self.listener.stop()
        self.root.quit()


def main():
    """Головна функція"""
    try:
        companion = MiniCompanion()
        companion.start()
    except KeyboardInterrupt:
        print("\n👋 До побачення!")
    except Exception as e:
        print(f"❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

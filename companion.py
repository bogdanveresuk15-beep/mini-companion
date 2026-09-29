"""
Mini Companion - анімований компаньйон з підтримкою 20+ кадрів на емоцію
Структура: emotions/idle/frame_00.png ... frame_19.png, тощо
"""

import threading
import time
import tkinter as tk
from tkinter import filedialog
from tkinter import PhotoImage
from pynput import mouse
from typing import Optional, Dict, List
import sys
from pathlib import Path

try:
    import pygetwindow as gw
    WINDOW_TRACKING = True
except ImportError:
    WINDOW_TRACKING = False
    print("⚠️  pygetwindow не встановлена. Стеження за вікнами вимкнено.")


class AnimationPlayer:
    """Плеєр для циклічної анімації"""
    def __init__(self, frames: List[PhotoImage], fps: int = 10):
        self.frames = frames
        self.fps = fps  # кадрів на секунду
        self.frame_delay = int(1000 / fps)  # затримка між кадрами в мс
        self.current_frame = 0
        self.is_playing = False

    def get_current_frame(self) -> Optional[PhotoImage]:
        if not self.frames:
            return None
        return self.frames[self.current_frame]

    def next_frame(self) -> Optional[PhotoImage]:
        if not self.frames:
            return None
        self.current_frame = (self.current_frame + 1) % len(self.frames)
        return self.frames[self.current_frame]

    def reset(self):
        self.current_frame = 0

    def get_delay(self) -> int:
        """Повернути затримку до наступного кадру в мс"""
        return self.frame_delay


class MiniCompanion:
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

    # Стандартні затримки для кожної емоції (в секундах)
    STATE_DURATIONS = {
        "idle": 3.0,          # idle циклює весь час
        "watching": 2.0,
        "click": 0.6,
        "window": 1.5,
        "thinking": 2.0,
        "surprised": 1.0,
        "happy": 1.5,
        "yawn": 2.0,
        "dragging": 0.1       # під час перетягування
    }

    def __init__(self, width: int = 120, height: int = 120, anim_root: Optional[Path] = None):
        self.width = width
        self.height = height

        if anim_root is None:
            self.anim_root = self._select_anim_folder()
        else:
            self.anim_root = Path(anim_root)

        if self.anim_root is None:
            print("❌ Папка з анімаціями не вибрана. Вихід.")
            sys.exit(0)

        self.root = tk.Tk()
        self.root.title("Mini Companion")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.wm_attributes("-transparentcolor", "black")
        self.root.geometry(f"{width}x{height}+200+200")
        self.root.configure(bg="black")

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

        # Кеш анімацій
        self.animation_players: Dict[str, AnimationPlayer] = {}
        self.current_state = "idle"
        self.animation_id = None  # ID таймера для анімації

        self.load_animations()

        self.state_changed_time = time.time()
        self.current_active_window: Optional[str] = None
        self.mouse_x = 0
        self.mouse_y = 0
        self.companion_x = 200
        self.companion_y = 200
        self.clicks_count = 0

        self.is_dragging = False
        self.companion_drag_offset_x = 0
        self.companion_drag_offset_y = 0

        self.listener = None

        self._print_info()

    def _select_anim_folder(self) -> Optional[Path]:
        """Вибрати папку з анімаціями через діалог"""
        root = tk.Tk()
        root.withdraw()
        folder = filedialog.askdirectory(
            title="Виберіть папку з анімаціями для компаньйона",
            initialdir=str(Path.home())
        )
        root.destroy()

        if folder:
            return Path(folder)
        return None

    def _print_info(self):
        """Вивести інформацію про запуск"""
        print("\n" + "=" * 70)
        print("🎮 Mini Companion - Анімований компаньйон")
        print("=" * 70)
        print("📁 Папка з анімаціями:")
        print(f"   {self.anim_root}")
        print("\n📂 Очікувана структура:")
        print("   my_emotions/")
        for state in self.STATES:
            print(f"      {state}/")
            print(f"         frame_00.png")
            print(f"         frame_01.png")
            print(f"         ...")
            print(f"         frame_19.png  (мінімум 20 кадрів)")
        print("\n🎯 Керування:")
        print("   • УТРИМУЙ мишею - перетягування")
        print("   • ОТПУСТИ - компаньйон зупиняється")
        print("   • Лівий клік - 😄 реакція")
        print("   • Правий клік - 😮 реакція")
        print("   • Зміна вікна - 🪟 реакція")
        print("\n⚙️ Налаштування анімації:")
        print("   • FPS: 10 кадрів/сек (100мс на кадр)")
        print("   • На 20 кадрів = ~2 секунди анімації")
        print("=" * 70 + "\n")

    def load_animations(self):
        """Завантажити анімації з папок"""
        print("🖼️  Завантаження анімацій...")
        if not self.anim_root.exists():
            print(f"❌ Папка не існує: {self.anim_root}")
            return

        total_loaded = 0

        for state in self.STATES:
            folder = self.anim_root / state
            if not folder.exists():
                print(f"⚠️  Папка '{state}' не знайдена.")
                continue

            frames = []
            
            # Пошук PNG файлів з сортуванням за номером
            pngs = sorted(folder.glob("frame_*.png"))
            if not pngs:
                pngs = sorted(folder.glob("*.png"))
            
            if not pngs:
                print(f"⚠️  У папці '{state}' немає PNG файлів.")
                continue

            # Завантажити кожен кадр
            for i, path in enumerate(pngs):
                try:
                    image = PhotoImage(file=str(path))
                    frames.append(image)
                except Exception as e:
                    print(f"❌ Помилка завантаження {path.name}: {e}")
                    continue

            if frames:
                # FPS = 10 означає 100мс на кадр
                player = AnimationPlayer(frames, fps=10)
                self.animation_players[state] = player
                total_loaded += 1
                print(f"   ✅ '{state}': {len(frames)} кадрів завантажено ({len(frames) / 10:.1f}с анімації)")
            else:
                print(f"   ❌ '{state}': кадри не завантажились.")

        print(f"\n📊 Всього емоцій завантажено: {total_loaded}/{len(self.STATES)}")
        if total_loaded == 0:
            print("⚠️  Будуть використовуватися стандартні емодзі.\n")
        else:
            print()

    def _show_current_frame(self):
        """Показати поточний кадр анімації"""
        if self.current_state in self.animation_players:
            player = self.animation_players[self.current_state]
            frame = player.get_current_frame()
            if frame:
                self.label.config(image=frame, text="")
                return

        # Fallback на емодзі
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
        self.label.config(text=fallback_faces.get(self.current_state, "🙂"), image="")

    def _animate_loop(self):
        """Основний цикл анімації"""
        if self.current_state not in self.animation_players:
            # Якщо немає анімації — залишити на першому кадрі
            self._show_current_frame()
            return

        player = self.animation_players[self.current_state]
        
        # Показати поточний кадр
        self._show_current_frame()
        
        # Перейти до наступного кадру
        player.next_frame()
        
        # Запланувати наступний кадр
        delay = player.get_delay()
        self.animation_id = self.root.after(delay, self._animate_loop)

    def set_state(self, new_state: str, duration: float = None):
        """Встановити новий стан з анімацією"""
        if new_state not in self.STATES:
            return

        if self.is_dragging and new_state != "dragging":
            return

        # Скасувати попередній таймер анімації
        if self.animation_id is not None:
            self.root.after_cancel(self.animation_id)
            self.animation_id = None

        self.current_state = new_state
        self.state_changed_time = time.time()

        # Взяти тривалість з налаштувань або параметра
        if duration is None:
            duration = self.STATE_DURATIONS.get(new_state, 2.0)

        # Скинути анімацію на початок
        if self.current_state in self.animation_players:
            self.animation_players[self.current_state].reset()

        # Запустити анімацію
        self._animate_loop()

        # Якщо не перетягується — повернути до idle після тривалості
        if not self.is_dragging and new_state != "idle":
            self.root.after(
                int(duration * 1000),
                lambda: self._restore_idle_if_needed(new_state, duration)
            )

    def _restore_idle_if_needed(self, prev_state: str, duration: float):
        """Повернути до idle якщо стан не змінився"""
        if self.is_dragging:
            return
        elapsed = time.time() - self.state_changed_time
        if self.current_state == prev_state and elapsed >= duration - 0.1:
            self.set_state("idle")

    def on_move(self, x: int, y: int):
        """Реакція на рух миші"""
        self.mouse_x = x
        self.mouse_y = y

        if self.is_dragging:
            new_x = x - self.companion_drag_offset_x
            new_y = y - self.companion_drag_offset_y

            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            new_x = max(0, min(new_x, screen_w - self.width))
            new_y = max(0, min(new_y, screen_h - self.height))

            self.companion_x = new_x
            self.companion_y = new_y
            self.root.geometry(f"{self.width}x{self.height}+{new_x}+{new_y}")
            
            # Показати dragging без зміни стану
            if self.current_state != "dragging":
                self.set_state("dragging", 0.1)

    def on_click(self, x: int, y: int, button, pressed: bool):
        """Реакція на клік миші"""
        is_on_companion = (
            self.companion_x <= x <= self.companion_x + self.width and
            self.companion_y <= y <= self.companion_y + self.height
        )

        if pressed:
            if is_on_companion and str(button).split(".")[-1] == "left":
                # Почати перетягування
                self.is_dragging = True
                self.companion_drag_offset_x = x - self.companion_x
                self.companion_drag_offset_y = y - self.companion_y
                self.set_state("dragging", 0.1)
                print("✋ Утримування...")
            else:
                # Клік поза компаньйоном
                self.clicks_count += 1
                button_name = str(button).split(".")[-1]

                if button_name == "left":
                    self.set_state("click", 0.6)
                    print(f"👆 Лівий клік! Всього: {self.clicks_count}")
                elif button_name == "right":
                    self.set_state("surprised", 1.0)
                    print("🔧 Правий клік!")
                elif button_name == "middle":
                    self.set_state("happy", 0.8)
                    print("🎯 Середній клік!")
        else:
            # Відпустити клавішу
            if self.is_dragging:
                self.is_dragging = False
                self.set_state("idle")
                print("🛑 Опущено")

    def window_watcher(self):
        """Стеження за активним вікном (фоновий потік)"""
        if not WINDOW_TRACKING:
            return

        while True:
            try:
                window = gw.getActiveWindow()
                title = window.title if window else "Без активного вікна"

                if title != self.current_active_window:
                    self.current_active_window = title
                    print(f"🪟 Активне вікно: {title[:50]}")

                    # Різні реакції на різні додатки
                    if any(app in title.lower() for app in ["chrome", "firefox", "edge"]):
                        self.set_state("thinking", 2.0)
                    elif any(app in title.lower() for app in ["code", "studio", "sublime"]):
                        self.set_state("thinking", 2.0)
                    elif any(app in title.lower() for app in ["discord", "telegram", "slack"]):
                        self.set_state("happy", 1.5)
                    else:
                        self.set_state("window", 1.5)
            except Exception:
                pass

            time.sleep(0.25)

    def start(self):
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

        # Запустити начальну анімацію
        self.set_state("idle")

        # Запуск основного цикла Tkinter
        self.root.mainloop()

    def stop(self):
        """Зупинити компаньйона"""
        if self.listener:
            self.listener.stop()
        if self.animation_id:
            self.root.after_cancel(self.animation_id)
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

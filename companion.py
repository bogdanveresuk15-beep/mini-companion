import threading
import time
import tkinter as tk
from tkinter import filedialog, PhotoImage
from pathlib import Path
from typing import Dict, List, Optional
from pynput import mouse
import sys

try:
    import pygetwindow as gw
    WINDOW_TRACKING = True
except ImportError:
    WINDOW_TRACKING = False
    print("⚠️  pygetwindow не встановлена. Стеження за вікнами вимкнено.")

WINDOW_KEYWORDS = {
    "browser": ["chrome", "firefox", "edge", "opera", "brave", "browser"],
    "editor": ["code", "visual studio", "sublime", "notepad", "pycharm", "vscode", "editor"],
    "chat": ["discord", "telegram", "slack", "teams", "messenger", "signal", "chat"],
    "default": []
}

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

FALLBACK_EMOJIS = {
    "idle": "🙂",
    "watching": "👀",
    "click": "😄",
    "window": "🪟",
    "thinking": "🤔",
    "surprised": "😮",
    "happy": "😊",
    "yawn": "😴",
    "dragging": "✋",
}

DURATION_BY_STATE = {
    "idle": 2.5,
    "watching": 2.0,
    "click": 0.8,
    "window": 1.5,
    "thinking": 2.0,
    "surprised": 1.0,
    "happy": 1.8,
    "yawn": 2.0,
    "dragging": 0.1,
}

FPS_BY_STATE = {
    "idle": 10,
    "watching": 10,
    "click": 12,
    "window": 10,
    "thinking": 10,
    "surprised": 12,
    "happy": 10,
    "yawn": 8,
    "dragging": 8,
}


class AnimationPlayer:
    def __init__(self, frames: List[PhotoImage], fps: int = 10):
        self.frames = frames
        self.fps = fps
        self.delay = int(1000 / fps)
        self.index = 0

    def reset(self):
        self.index = 0

    def current(self):
        if not self.frames:
            return None
        return self.frames[self.index]

    def next(self):
        if not self.frames:
            return None
        frame = self.frames[self.index]
        self.index = (self.index + 1) % len(self.frames)
        return frame


class MiniCompanion:
    def __init__(self, width: int = 120, height: int = 120, emotions_root: Optional[Path] = None):
        self.width = width
        self.height = height

        if emotions_root is None:
            self.emotions_root = self._select_folder()
        else:
            self.emotions_root = Path(emotions_root)

        if self.emotions_root is None:
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

        self.animation_cache: Dict[str, Dict[str, List[PhotoImage]]] = {}
        self.animation_player: Optional[AnimationPlayer] = None
        self.current_state = "idle"
        self.current_window_type = "default"
        self.current_window_title = "default"
        self.animation_timer_id = None

        self.is_dragging = False
        self.mouse_pressed_on_companion = False
        self.click_start_x = 0
        self.click_start_y = 0
        self.click_start_time = 0.0
        self.drag_threshold = 12
        self.last_click_reaction_time = 0.0
        self.click_reaction_cooldown = 0.75

        self.companion_x = 200
        self.companion_y = 200
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        self.clicks_count = 0
        self.current_active_window: Optional[str] = None

        self.listener = None

        self.load_animations()
        self._print_info()

    def _select_folder(self) -> Optional[Path]:
        root = tk.Tk()
        root.withdraw()
        folder = filedialog.askdirectory(
            title="Виберіть папку з анімаціями компаньйона",
            initialdir=str(Path.home())
        )
        root.destroy()

        if folder:
            return Path(folder)
        return None

    def _print_info(self):
        print("\n" + "=" * 80)
        print("🎮 Mini Companion — анімації на емоції + типи вікон")
        print("=" * 80)
        print(f"📁 Користувацька папка: {self.emotions_root}")
        print("Структура:")
        print("  emotions/")
        for state in STATES:
            print(f"    {state}/")
            print("      default/")
            print("      browser/")
            print("      editor/")
            print("      chat/")
        print("=" * 80)
        print("🎯 Керування:")
        print("  • Утримуй ЛКМ — перетягування")
        print("  • Відпусти — зупинити")
        print("  • Клік по компаньйону — одиночна реакція (тільки в idle)")
        print("  • Клік поза компаньйоном — ігнорується")
        print("  • Зміна активного вікна — реакція (тільки в idle)")
        print("=" * 80)

    def detect_window_type(self, title: str) -> str:
        text = title.lower()

        for kind, keywords in WINDOW_KEYWORDS.items():
            if kind == "default":
                continue
            if any(keyword in text for keyword in keywords):
                return kind

        return "default"

    def load_animations(self):
        print("🖼️  Завантаження анімацій...")
        if not self.emotions_root.exists():
            print(f"❌ Папка не існує: {self.emotions_root}")
            return

        total_loaded = 0

        for state in STATES:
            state_dir = self.emotions_root / state
            if not state_dir.exists():
                print(f"⚠️  Папка '{state}' відсутня.")
                continue

            self.animation_cache[state] = {}

            variants = [p for p in state_dir.iterdir() if p.is_dir()]
            if not variants:
                variants = [state_dir]

            for variant in variants:
                variant_name = variant.name if variant.is_dir() else "default"
                frames = []
                for path in sorted(variant.glob("frame_*.png")):
                    try:
                        img = PhotoImage(file=str(path))
                        frames.append(img)
                    except Exception as e:
                        print(f"❌ Не вдалось завантажити {path}: {e}")

                if frames:
                    self.animation_cache[state][variant_name] = frames
                    print(f"   ✅ {state}/{variant_name}: {len(frames)} кадрів")
                    total_loaded += 1

        print(f"\n📊 Завантажено: {total_loaded} анімаційних варіантів")
        if total_loaded == 0:
            print("⚠️  Немає анімацій — будуть використовуватися стандартні емодзі.\n")

    def _choose_frames_for_state(self, state: str, window_title: str) -> List[PhotoImage]:
        window_type = self.detect_window_type(window_title)
        variant_map = self.animation_cache.get(state, {})

        if window_type in variant_map and variant_map[window_type]:
            return variant_map[window_type]

        if "default" in variant_map and variant_map["default"]:
            return variant_map["default"]

        for frames in variant_map.values():
            if frames:
                return frames

        return []

    def _show_fallback_emoji(self):
        self.label.config(
            text=FALLBACK_EMOJIS.get(self.current_state, "🙂"),
            image=""
        )

    def _show_current_frame(self):
        if self.animation_player is None:
            self._show_fallback_emoji()
            return

        frame = self.animation_player.current()
        if frame is not None:
            self.label.config(image=frame, text="")
            return

        self._show_fallback_emoji()

    def _animate_loop(self):
        if self.is_dragging:
            return

        if self.animation_player is None:
            self._show_fallback_emoji()
            return

        frame = self.animation_player.next()
        if frame is not None:
            self.label.config(image=frame, text="")
        else:
            self._show_fallback_emoji()

        delay = 1000 // FPS_BY_STATE.get(self.current_state, 10)
        self.animation_timer_id = self.root.after(delay, self._animate_loop)

    def set_state(self, state: str, duration: Optional[float] = None, window_title: Optional[str] = None):
        if state not in STATES:
            return

        if self.is_dragging and state != "dragging":
            return

        if self.animation_timer_id is not None:
            self.root.after_cancel(self.animation_timer_id)
            self.animation_timer_id = None

        self.current_state = state
        if window_title:
            self.current_window_title = window_title
        else:
            self.current_window_title = self.current_window_title or "default"

        self.current_window_type = self.detect_window_type(self.current_window_title)
        frames = self._choose_frames_for_state(state, self.current_window_title)

        if frames:
            self.animation_player = AnimationPlayer(frames, fps=FPS_BY_STATE.get(state, 10))
            self.animation_player.reset()
            self._show_current_frame()
            self.animation_timer_id = self.root.after(100, self._animate_loop)
        else:
            self.animation_player = None
            self._show_fallback_emoji()

        if not self.is_dragging and state != "idle":
            duration_value = duration if duration is not None else DURATION_BY_STATE.get(state, 1.5)
            self.root.after(
                int(duration_value * 1000),
                lambda: self._restore_idle_if_needed(state)
            )

    def _restore_idle_if_needed(self, prev_state: str):
        if self.is_dragging:
            return

        if self.current_state == prev_state:
            self.set_state("idle", duration=DURATION_BY_STATE.get("idle", 2.5), window_title=self.current_window_title)

    def on_move(self, x: int, y: int):
        self.mouse_x = x
        self.mouse_y = y

        if self.mouse_pressed_on_companion and not self.is_dragging:
            movement_x = abs(x - self.click_start_x)
            movement_y = abs(y - self.click_start_y)

            if movement_x > self.drag_threshold or movement_y > self.drag_threshold:
                self.is_dragging = True
                self.drag_offset_x = x - self.companion_x
                self.drag_offset_y = y - self.companion_y
                self.set_state("dragging", duration=0.1, window_title=self.current_window_title)
                print("✋ Почали перетягування")

        if self.is_dragging:
            new_x = x - self.drag_offset_x
            new_y = y - self.drag_offset_y

            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            new_x = max(0, min(new_x, screen_w - self.width))
            new_y = max(0, min(new_y, screen_h - self.height))

            self.companion_x = new_x
            self.companion_y = new_y
            self.root.geometry(f"{self.width}x{self.height}+{new_x}+{new_y}")

            if self.current_state != "dragging":
                self.set_state("dragging", duration=0.1, window_title=self.current_window_title)

    def on_click(self, x: int, y: int, button, pressed: bool):
        is_on_companion = (
            self.companion_x <= x <= self.companion_x + self.width and
            self.companion_y <= y <= self.companion_y + self.height
        )

        if not is_on_companion:
            return

        button_name = str(button).split(".")[-1]

        if pressed:
            if button_name == "left":
                self.mouse_pressed_on_companion = True
                self.click_start_x = x
                self.click_start_y = y
                self.click_start_time = time.time()
                return

        if not pressed:
            if self.mouse_pressed_on_companion:
                self.mouse_pressed_on_companion = False

                press_duration = time.time() - self.click_start_time
                movement_x = abs(x - self.click_start_x)
                movement_y = abs(y - self.click_start_y)

                # РЕАКЦІЯ НА КЛІК ТІЛЬКИ КОЛИ В IDLE
                if press_duration < 0.5 and movement_x < self.drag_threshold and movement_y < self.drag_threshold:
                    if self.current_state == "idle":  # ← ДОДАНО
                        now = time.time()
                        if now - self.last_click_reaction_time >= self.click_reaction_cooldown:
                            self.last_click_reaction_time = now
                            self.set_state("click", duration=0.7, window_title=self.current_window_title)
                            print("👆 Одинарний клік по компаньйону (в idle)")
                            return
                    else:
                        print(f"⏸️ Клік проігнорований (компаньйон в стані {self.current_state})")
                        return

                if self.is_dragging:
                    self.is_dragging = False
                    self.set_state("idle", duration=2.5, window_title=self.current_window_title)
                    print("🛑 Відпустили компаньйона")
                    return

    def window_watcher(self):
        if not WINDOW_TRACKING:
            return

        while True:
            try:
                window = gw.getActiveWindow()
                title = window.title if window else "Без активного вікна"
                if title != self.current_active_window:
                    self.current_active_window = title
                    self.current_window_title = title

                    detected = self.detect_window_type(title)
                    print(f"🪟 Активне вікно: {title[:60]} | тип: {detected}")

                    # РЕАКЦІЯ НА ВІКНА ТІЛЬКИ КОЛИ В IDLE
                    if self.current_state == "idle":  # ← ДОДАНО
                        if any(keyword in title.lower() for keyword in ["chrome", "firefox", "edge", "opera", "brave"]):
                            self.set_state("thinking", duration=2.0, window_title=title)
                        elif any(keyword in title.lower() for keyword in ["code", "visual studio", "sublime", "notepad", "pycharm", "vscode"]):
                            self.set_state("window", duration=1.5, window_title=title)
                        elif any(keyword in title.lower() for keyword in ["discord", "telegram", "slack", "teams", "messenger", "signal"]):
                            self.set_state("happy", duration=1.8, window_title=title)
                        else:
                            self.set_state("window", duration=1.5, window_title=title)
                    else:
                        print(f"   ⏸️ Реакція на вікно пропущена (в стані {self.current_state})")

            except Exception:
                pass

            time.sleep(0.25)

    def start(self):
        self.listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click
        )
        self.listener.start()

        if WINDOW_TRACKING:
            self.window_thread = threading.Thread(target=self.window_watcher, daemon=True)
            self.window_thread.start()

        self.set_state("idle", duration=2.5, window_title="default")
        self.root.mainloop()


def main():
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

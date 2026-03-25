import tkinter as tk
from tkinter import ttk
import json
import os
from datetime import date
import threading
import pystray
from PIL import Image, ImageDraw
import keyboard

SETTINGS_FILE = "pomodoro_settings.json"

class PomodoroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pomodoro Pro")
        self.root.geometry("380x360")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.load_settings()
        self.is_running = False
        self.is_break = False
        self.pomodoro_count = 0
        self.remaining_seconds = self.work_minutes * 60

        self.build_ui()
        self.apply_theme()
        self.update_timer_display()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {}

        self.work_minutes = data.get("work", 25)
        self.break_minutes = data.get("break", 5)
        self.long_break_minutes = data.get("long_break", 15)
        self.dark_mode = data.get("dark", False)

        today = str(date.today())
        self.stats = data.get("stats", {})
        if today not in self.stats:
            self.stats[today] = 0

    def save_settings(self):
        data = {
            "work": self.work_minutes,
            "break": self.break_minutes,
            "long_break": self.long_break_minutes,
            "dark": self.dark_mode,
            "stats": self.stats
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f)

    def build_ui(self):
        self.frame = ttk.Frame(self.root, padding=10)
        self.frame.pack(fill="both", expand=True)

        self.title_label = ttk.Label(self.frame, text="Çalışma", font=("Arial", 16))
        self.title_label.pack()

        self.timer_label = ttk.Label(self.frame, text="00:00", font=("Arial", 32))
        self.timer_label.pack(pady=5)

        self.stats_label = ttk.Label(self.frame, text=f"Bugün: {self.stats[str(date.today())]} Pomodoro")
        self.stats_label.pack()

        settings = ttk.Frame(self.frame)
        settings.pack(pady=5)

        ttk.Label(settings, text="Çalışma").grid(row=0, column=0)
        self.work_spin = ttk.Spinbox(settings, from_=1, to=60, width=5)
        self.work_spin.set(self.work_minutes)
        self.work_spin.grid(row=0, column=1)

        ttk.Label(settings, text="Kısa").grid(row=0, column=2)
        self.break_spin = ttk.Spinbox(settings, from_=1, to=30, width=5)
        self.break_spin.set(self.break_minutes)
        self.break_spin.grid(row=0, column=3)

        ttk.Label(settings, text="Uzun").grid(row=0, column=4)
        self.long_spin = ttk.Spinbox(settings, from_=5, to=60, width=5)
        self.long_spin.set(self.long_break_minutes)
        self.long_spin.grid(row=0, column=5)

        btns = ttk.Frame(self.frame)
        btns.pack(pady=10)

        self.start_btn = ttk.Button(btns, text="Başlat", command=self.start)
        self.start_btn.grid(row=0, column=0, padx=3)
        ttk.Button(btns, text="Duraklat", command=self.pause).grid(row=0, column=1, padx=3)
        ttk.Button(btns, text="Sıfırla", command=self.reset).grid(row=0, column=2, padx=3)

        ttk.Button(self.frame, text="Dark Mode", command=self.toggle_theme).pack()

    def apply_theme(self):
        bg = "#1e1e1e" if self.dark_mode else "#f0f0f0"
        self.root.configure(bg=bg)
        for widget in self.frame.winfo_children():
            widget.configure(background=bg)

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.save_settings()

    def update_timer_display(self):
        m = self.remaining_seconds // 60
        s = self.remaining_seconds % 60
        self.timer_label.config(text=f"{m:02}:{s:02}")

    def start(self):
        if not self.is_running:
            self.work_minutes = int(self.work_spin.get())
            self.break_minutes = int(self.break_spin.get())
            self.long_break_minutes = int(self.long_spin.get())

            self.is_running = True
            self.start_btn.config(state="disabled")
            self.tick()

    def pause(self):
        self.is_running = False
        self.start_btn.config(state="normal")

    def reset(self):
        self.is_running = False
        self.is_break = False
        self.remaining_seconds = int(self.work_spin.get()) * 60
        self.title_label.config(text="Çalışma")
        self.start_btn.config(state="normal")
        self.update_timer_display()

    def tick(self):
        if self.is_running:
            if self.remaining_seconds > 0:
                self.remaining_seconds -= 1
                self.update_timer_display()
                self.root.after(1000, self.tick)
            else:
                self.switch_mode()

    def switch_mode(self):
        self.root.bell()
        self.is_break = not self.is_break

        if self.is_break:
            self.pomodoro_count += 1
            today = str(date.today())
            self.stats[today] += 1
            self.stats_label.config(text=f"Bugün: {self.stats[today]} Pomodoro")

            if self.pomodoro_count % 4 == 0:
                self.remaining_seconds = self.long_break_minutes * 60
                self.title_label.config(text="Uzun Mola")
            else:
                self.remaining_seconds = self.break_minutes * 60
                self.title_label.config(text="Kısa Mola")
        else:
            self.remaining_seconds = self.work_minutes * 60
            self.title_label.config(text="Çalışma")

        self.save_settings()
        self.update_timer_display()
        self.tick()

    def hide_window(self):
        self.root.withdraw()

def create_image():
    img = Image.new('RGB', (64, 64), color=(200, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((18, 20), "P", fill=(255, 255, 255))
    return img

def setup_tray(app):
    def show(icon, item):
        app.root.after(0, app.root.deiconify)

    def quit_app(icon, item):
        icon.stop()
        app.root.after(0, app.root.destroy)

    icon = pystray.Icon(
        "Pomodoro",
        create_image(),
        menu=pystray.Menu(
            pystray.MenuItem("Aç", show),
            pystray.MenuItem("Çıkış", quit_app)
        )
    )
    icon.run()

if __name__ == "__main__":
    root = tk.Tk()
    app = PomodoroApp(root)

    tray_thread = threading.Thread(target=setup_tray, args=(app,), daemon=True)
    tray_thread.start()

    keyboard.add_hotkey("ctrl+alt+p", lambda: root.deiconify())

    root.mainloop()
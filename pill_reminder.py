import json
import subprocess
import sys
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk


APP_NAME = "Pill Reminder"
APP_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
DATA_FILE = APP_DIR / "data.json"
LEGACY_HOME_DATA_FILE = Path.home() / ".pill_reminder.json"
LEGACY_LOCAL_DATA_FILE = Path("pill_data.json")

TIME_FORMAT = "%H:%M"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
CHECK_INTERVAL_MS = 15000
SNOOZE_MINUTES = 10
REPEAT_REMINDER_MINUTES = 5
HISTORY_LIMIT = 90

WINDOW_BG = "#eef4f2"
PANEL_BG = "#ffffff"
HEADER_BG = "#183642"
TEXT_COLOR = "#16252d"
MUTED_COLOR = "#5d6f78"
PRIMARY_BG = "#0f7c72"
SECONDARY_BG = "#dcecff"
DANGER_BG = "#ffe1dd"
WARNING_BG = "#fff1c9"
SUCCESS_BG = "#ddf3e6"
BORDER_COLOR = "#88a1aa"

COMMON_PILL_NAMES = [
    "Birth Control Pill",
    "My Daily Pill",
    "Combined Birth Control Pill",
    "Mini Pill",
    "Progestin-Only Pill",
    "Morning Pill",
    "Evening Pill",
    "Custom Pill Name",
]


def is_valid_time(value):
    try:
        datetime.strptime(value, TIME_FORMAT)
    except ValueError:
        return False
    return True


def parse_datetime(value):
    return datetime.strptime(value, DATETIME_FORMAT)


def format_datetime(value):
    return value.strftime(DATETIME_FORMAT)


def parse_history_datetime(entry):
    if not isinstance(entry, str):
        return None

    timestamp = entry.split(" - ", 1)[0]

    try:
        return datetime.strptime(timestamp, "%Y-%m-%d at %H:%M")
    except ValueError:
        return None


def load_json_file(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def load_data():
    for data_file in (DATA_FILE, LEGACY_HOME_DATA_FILE, LEGACY_LOCAL_DATA_FILE):
        if data_file.exists():
            return load_json_file(data_file)
    return {}


def clean_time_list(values, fallback):
    if not isinstance(values, list):
        return fallback

    clean_values = sorted({value for value in values if isinstance(value, str) and is_valid_time(value)})
    return clean_values or fallback


def clean_datetime_list(values):
    if not isinstance(values, list):
        return []

    clean_values = []

    for value in values:
        if not isinstance(value, str):
            continue

        try:
            clean_values.append(parse_datetime(value))
        except ValueError:
            continue

    return [format_datetime(value) for value in sorted(clean_values)]


def prepare_data(raw_data):
    data = raw_data if isinstance(raw_data, dict) else {}
    old_reminder = data.get("reminder_time", "21:00")
    fallback = old_reminder if isinstance(old_reminder, str) and is_valid_time(old_reminder) else "21:00"

    return {
        "pill_name": data.get("pill_name") if isinstance(data.get("pill_name"), str) else "Birth Control Pill",
        "daily_reminders": clean_time_list(data.get("daily_reminders", data.get("reminders")), [fallback]),
        "one_time_reminders": clean_datetime_list(data.get("one_time_reminders")),
        "snoozes": clean_datetime_list(data.get("snoozes")),
        "history": data.get("history", []) if isinstance(data.get("history"), list) else [],
        "last_taken": data.get("last_taken") if isinstance(data.get("last_taken"), str) else None,
        "last_taken_time": data.get("last_taken_time") if isinstance(data.get("last_taken_time"), str) else None,
        "reminders_shown": data.get("reminders_shown", []) if isinstance(data.get("reminders_shown"), list) else [],
    }


def relative_due_text(due):
    seconds = int((due - datetime.now()).total_seconds())

    if seconds <= -60:
        minutes = abs(seconds) // 60
        if minutes >= 60:
            return f"{minutes // 60}h {minutes % 60}m overdue"
        return f"{minutes} min overdue"

    if seconds <= 60:
        return "due now"

    minutes = seconds // 60

    if minutes >= 60:
        return f"in {minutes // 60}h {minutes % 60}m"

    return f"in {minutes}m"


def time_to_minutes(value):
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def friendly_due_text(due):
    today = date.today()

    if due.date() == today:
        day_text = "Today"
    elif due.date() == today + timedelta(days=1):
        day_text = "Tomorrow"
    else:
        day_text = due.strftime("%A, %b %d")

    time_text = due.strftime("%I:%M %p").lstrip("0")
    return f"{day_text} at {time_text}"


class PillReminderApp:
    def __init__(self, root):
        self.root = root
        self.data = prepare_data(load_data())
        self.upcoming_items = []
        self.active_popup = None

        self.root.title(APP_NAME)
        self.root.geometry("980x720")
        self.root.minsize(880, 640)
        self.root.configure(bg=WINDOW_BG)

        self.cleanup_old_reminder_attempts()
        self.build_ui()
        self.save_data()
        self.refresh_all()
        self.tick_clock()
        self.check_reminders()

    def save_data(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        temp_file = DATA_FILE.with_suffix(".tmp")
        temp_file.write_text(json.dumps(self.data, indent=2))
        temp_file.replace(DATA_FILE)

    def cleanup_old_reminder_attempts(self):
        today = date.today().isoformat()
        self.data["reminders_shown"] = [
            value
            for value in self.data.get("reminders_shown", [])
            if isinstance(value, str) and value.startswith(f"{today}|")
        ]

    def panel(self, parent, title, row, column, **grid_options):
        frame = tk.Frame(
            parent,
            bg=PANEL_BG,
            highlightbackground=BORDER_COLOR,
            highlightthickness=2,
            padx=14,
            pady=12,
        )
        frame.grid(row=row, column=column, sticky=grid_options.pop("sticky", "nsew"), **grid_options)
        tk.Label(frame, text=title, bg=PANEL_BG, fg=TEXT_COLOR, font=("Helvetica", 15, "bold")).grid(
            row=0, column=0, columnspan=10, sticky="w", pady=(0, 10)
        )
        return frame

    def label(self, parent, text="", row=None, column=None, *, bold=False, muted=False, bg=PANEL_BG, **grid_options):
        label = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=MUTED_COLOR if muted else TEXT_COLOR,
            font=("Helvetica", 12, "bold" if bold else "normal"),
            anchor="w",
            justify="left",
        )

        if row is not None and column is not None:
            label.grid(row=row, column=column, sticky=grid_options.pop("sticky", "w"), **grid_options)

        return label

    def button(self, parent, text, command, row=None, column=None, *, primary=False, danger=False, **grid_options):
        bg = PRIMARY_BG if primary else SECONDARY_BG
        fg = "#ffffff" if primary else TEXT_COLOR

        if danger:
            bg = DANGER_BG
            fg = TEXT_COLOR

        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            relief="raised",
            bd=2,
            padx=12,
            pady=7,
            cursor="hand2",
            font=("Helvetica", 12, "bold"),
        )

        if row is not None and column is not None:
            button.grid(row=row, column=column, sticky=grid_options.pop("sticky", "w"), **grid_options)

        return button

    def entry(self, parent, row, column, **grid_options):
        entry = tk.Entry(
            parent,
            bg="#ffffff",
            fg=TEXT_COLOR,
            relief="solid",
            bd=2,
            font=("Helvetica", 14),
            insertbackground=TEXT_COLOR,
            highlightbackground=PRIMARY_BG,
            highlightcolor=PRIMARY_BG,
            highlightthickness=1,
        )
        entry.grid(row=row, column=column, sticky=grid_options.pop("sticky", "ew"), ipady=5, **grid_options)
        return entry

    def spinbox(self, parent, row, column, from_, to, **grid_options):
        spinbox = tk.Spinbox(
            parent,
            from_=from_,
            to=to,
            width=4,
            format="%02.0f",
            justify="center",
            bg="#ffffff",
            fg=TEXT_COLOR,
            relief="solid",
            bd=2,
            font=("Helvetica", 14, "bold"),
            highlightbackground=PRIMARY_BG,
            highlightcolor=PRIMARY_BG,
            highlightthickness=1,
        )
        spinbox.grid(row=row, column=column, sticky=grid_options.pop("sticky", "w"), ipady=4, **grid_options)
        return spinbox

    def build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        home = tk.Frame(self.root, bg=WINDOW_BG, padx=34, pady=28)
        home.grid(row=0, column=0, sticky="nsew")
        home.columnconfigure(0, weight=1)
        home.rowconfigure(0, weight=1)

        card = tk.Frame(
            home,
            bg=PANEL_BG,
            highlightbackground=BORDER_COLOR,
            highlightthickness=2,
            padx=34,
            pady=30,
        )
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)

        self.pill_title_label = tk.Label(
            card,
            text="",
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            font=("Helvetica", 30, "bold"),
            anchor="center",
        )
        self.pill_title_label.grid(row=0, column=0, sticky="ew")

        self.date_label = tk.Label(card, text="", bg=PANEL_BG, fg=MUTED_COLOR, font=("Helvetica", 15))
        self.date_label.grid(row=1, column=0, sticky="ew", pady=(6, 26))

        self.status_icon_label = tk.Label(card, text="", bg=PANEL_BG, fg=TEXT_COLOR, font=("Helvetica", 56, "bold"))
        self.status_icon_label.grid(row=2, column=0, sticky="ew")

        self.status_label = tk.Label(card, text="", bg=PANEL_BG, fg=TEXT_COLOR, font=("Helvetica", 22, "bold"))
        self.status_label.grid(row=3, column=0, sticky="ew", pady=(2, 24))

        next_box = tk.Frame(card, bg="#eef6f4", highlightbackground="#bfd2cd", highlightthickness=1, padx=18, pady=14)
        next_box.grid(row=4, column=0, sticky="ew", pady=(0, 24))
        next_box.columnconfigure(0, weight=1)

        tk.Label(next_box, text="Next reminder", bg="#eef6f4", fg=MUTED_COLOR, font=("Helvetica", 13, "bold")).grid(
            row=0, column=0
        )
        self.next_label = tk.Label(next_box, text="", bg="#eef6f4", fg=TEXT_COLOR, font=("Helvetica", 24, "bold"))
        self.next_label.grid(row=1, column=0, pady=(4, 0))
        self.next_detail_label = tk.Label(next_box, text="", bg="#eef6f4", fg=MUTED_COLOR, font=("Helvetica", 13, "bold"))
        self.next_detail_label.grid(row=2, column=0, pady=(4, 0))
        self.current_reminder_label = tk.Label(
            next_box,
            text="",
            bg="#eef6f4",
            fg=TEXT_COLOR,
            font=("Helvetica", 13, "bold"),
        )
        self.current_reminder_label.grid(row=3, column=0, pady=(8, 0))

        take_button = self.button(card, "TAKE PILL", self.mark_taken, row=5, column=0, primary=True, sticky="ew", ipady=14)
        take_button.config(font=("Helvetica", 20, "bold"))

        secondary = tk.Frame(card, bg=PANEL_BG)
        secondary.grid(row=6, column=0, pady=(24, 0))
        self.button(secondary, "Change pill name / reminder time", self.open_settings_dialog).pack(side="left", padx=6)
        self.button(secondary, "History", self.open_history_dialog).pack(side="left", padx=6)
        self.button(secondary, "Extra reminder", self.open_extra_reminder_dialog).pack(side="left", padx=6)

        self.latest_history_label = tk.Label(
            card,
            text="",
            bg=PANEL_BG,
            fg=MUTED_COLOR,
            font=("Helvetica", 12, "bold"),
            wraplength=760,
        )
        self.latest_history_label.grid(row=7, column=0, sticky="ew", pady=(18, 0))

        self.feedback_label = tk.Label(card, text="Ready.", bg=PANEL_BG, fg=MUTED_COLOR, font=("Helvetica", 12, "bold"))
        self.feedback_label.grid(row=8, column=0, sticky="ew", pady=(12, 0))

        self.clock_label = tk.Label(home, text="", bg=WINDOW_BG, fg=MUTED_COLOR, font=("Helvetica", 12, "bold"))
        self.clock_label.grid(row=1, column=0, sticky="e", pady=(10, 0))

    def get_pill_name(self):
        pill_name = self.data.get("pill_name")
        return pill_name.strip() if isinstance(pill_name, str) and pill_name.strip() else "Birth Control Pill"

    def get_history(self):
        history = self.data.get("history")
        return history if isinstance(history, list) else []

    def get_daily_reminder_text(self):
        reminders = self.data.get("daily_reminders", [])
        clean_reminders = [value for value in reminders if isinstance(value, str) and is_valid_time(value)]

        if not clean_reminders:
            return "No daily reminder time saved"

        if len(clean_reminders) == 1:
            return f"Daily reminder time: {clean_reminders[0]}"

        return f"Daily reminder times: {', '.join(clean_reminders)}"

    def widget_is_alive(self, widget_name):
        widget = getattr(self, widget_name, None)
        return bool(widget and widget.winfo_exists())

    def dialog(self, title, width=520, height=420):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry(f"{width}x{height}")
        window.configure(bg=WINDOW_BG)
        window.transient(self.root)

        body = tk.Frame(window, bg=PANEL_BG, padx=18, pady=16)
        body.pack(fill="both", expand=True, padx=16, pady=16)
        body.columnconfigure(0, weight=1)
        return window, body

    def open_settings_dialog(self):
        if self.widget_is_alive("settings_window"):
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        self.settings_window = window
        window.title("Settings")
        window.geometry("620x680")
        window.configure(bg=WINDOW_BG)
        window.transient(self.root)

        def close_settings():
            self.settings_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close_settings)

        body = tk.Frame(window, bg=PANEL_BG, padx=22, pady=20)
        body.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(body, text="Settings", bg=PANEL_BG, fg=TEXT_COLOR, font=("Helvetica", 22, "bold")).pack(anchor="w")

        selector_box = tk.Frame(
            body,
            bg="#fff4bd",
            highlightbackground=PRIMARY_BG,
            highlightthickness=3,
            padx=14,
            pady=12,
        )
        selector_box.pack(fill="x", pady=(18, 16))

        tk.Label(selector_box, text="Pill name", bg="#fff4bd", fg=TEXT_COLOR, font=("Helvetica", 15, "bold")).pack(
            anchor="w", pady=(0, 6)
        )
        self.pill_name_var = tk.StringVar(value=self.get_pill_name())
        pill_menu = tk.OptionMenu(selector_box, self.pill_name_var, *COMMON_PILL_NAMES, command=self.update_custom_name_from_menu)
        pill_menu.config(
            bg="#ffffff",
            fg=TEXT_COLOR,
            activebackground="#ffffff",
            relief="raised",
            bd=2,
            font=("Helvetica", 15, "bold"),
            width=24,
        )
        pill_menu.pack(anchor="w", fill="x", ipady=5)

        tk.Label(selector_box, text="Custom name", bg="#fff4bd", fg=TEXT_COLOR, font=("Helvetica", 13, "bold")).pack(
            anchor="w", pady=(12, 5)
        )
        self.pill_name_entry = tk.Entry(
            selector_box,
            bg="#ffffff",
            fg=TEXT_COLOR,
            relief="solid",
            bd=2,
            font=("Helvetica", 16),
            insertbackground=TEXT_COLOR,
        )
        self.pill_name_entry.insert(0, self.get_pill_name())
        self.pill_name_entry.pack(fill="x", ipady=7)

        tk.Label(selector_box, text="Reminder time every day", bg="#fff4bd", fg=TEXT_COLOR, font=("Helvetica", 15, "bold")).pack(
            anchor="w", pady=(16, 6)
        )
        default_hour, default_minute = self.data["daily_reminders"][0].split(":")

        time_row = tk.Frame(selector_box, bg="#fff4bd")
        time_row.pack(anchor="w", fill="x")
        self.daily_hour_var = tk.StringVar(value=default_hour)
        self.daily_minute_var = tk.StringVar(value=default_minute)

        hour_box = tk.Frame(time_row, bg="#fff4bd")
        hour_box.pack(side="left", fill="x", expand=True, padx=(0, 14))
        tk.Label(hour_box, text="Hour", bg="#fff4bd", fg=MUTED_COLOR, font=("Helvetica", 12, "bold")).pack(anchor="w")
        self.daily_hour_dropdown = ttk.Combobox(
            hour_box,
            textvariable=self.daily_hour_var,
            values=[f"{hour:02}" for hour in range(24)],
            state="readonly",
            width=8,
            justify="center",
            font=("Menlo", 20, "bold"),
        )
        self.daily_hour_dropdown.pack(fill="x", ipady=8, pady=(4, 0))

        minute_box = tk.Frame(time_row, bg="#fff4bd")
        minute_box.pack(side="left", fill="x", expand=True)
        tk.Label(minute_box, text="Minute", bg="#fff4bd", fg=MUTED_COLOR, font=("Helvetica", 12, "bold")).pack(anchor="w")
        self.daily_minute_dropdown = ttk.Combobox(
            minute_box,
            textvariable=self.daily_minute_var,
            values=[f"{minute:02}" for minute in range(60)],
            state="readonly",
            width=8,
            justify="center",
            font=("Menlo", 20, "bold"),
        )
        self.daily_minute_dropdown.pack(fill="x", ipady=8, pady=(4, 0))

        self.daily_hour_dropdown.bind("<<ComboboxSelected>>", self.update_settings_time_preview)
        self.daily_minute_dropdown.bind("<<ComboboxSelected>>", self.update_settings_time_preview)
        self.set_daily_time_selection(default_hour, default_minute)

        self.settings_time_preview_label = tk.Label(
            selector_box,
            text="",
            bg="#fff4bd",
            fg=TEXT_COLOR,
            font=("Helvetica", 14, "bold"),
        )
        self.settings_time_preview_label.pack(anchor="w", pady=(12, 0))
        self.update_settings_time_preview()

        self.button(selector_box, "Save pill name and reminder time", self.save_settings, primary=True).pack(
            anchor="w", pady=(18, 0)
        )

        self.settings_feedback_label = tk.Label(
            body,
            text="",
            bg=PANEL_BG,
            fg=PRIMARY_BG,
            font=("Helvetica", 12, "bold"),
        )
        self.settings_feedback_label.pack(anchor="w", pady=(0, 12))

        self.button(body, "Close", close_settings).pack(anchor="e", pady=(8, 0))
        window.lift()
        window.focus_force()

    def focus_pill_name_entry(self):
        if not self.widget_is_alive("pill_name_entry"):
            return

        self.pill_name_entry.focus_force()
        self.pill_name_entry.selection_range(0, tk.END)

    def update_custom_name_from_menu(self, pill_name):
        if not self.widget_is_alive("pill_name_entry"):
            return

        self.pill_name_entry.delete(0, tk.END)
        self.pill_name_entry.insert(0, pill_name)

    def update_settings_time_preview(self, _event=None):
        if not self.widget_is_alive("settings_time_preview_label"):
            return

        reminder_time = self.get_selected_daily_time(show_error=False)

        if reminder_time:
            self.settings_time_preview_label.config(text=f"Reminder will show every day at {reminder_time}.")
        else:
            self.settings_time_preview_label.config(text="Choose an hour and minute for the reminder.")

    def load_selected_pill_name(self, _event=None):
        if not self.widget_is_alive("pill_name_listbox"):
            return

        selected = self.pill_name_listbox.curselection()

        if not selected:
            return

        pill_name = self.pill_name_listbox.get(selected[0])
        self.pill_name_entry.delete(0, tk.END)
        self.pill_name_entry.insert(0, pill_name)

    def select_current_pill_name(self):
        if not self.widget_is_alive("pill_name_listbox"):
            return

        current_name = self.get_pill_name()

        for index, pill_name in enumerate(COMMON_PILL_NAMES):
            if pill_name.lower() == current_name.lower():
                self.pill_name_listbox.selection_clear(0, tk.END)
                self.pill_name_listbox.selection_set(index)
                self.pill_name_listbox.see(index)
                return

    def set_daily_time_selection(self, hour, minute):
        hour_index = int(hour)
        minute_index = int(minute)
        self.daily_hour_var.set(f"{hour_index:02}")
        self.daily_minute_var.set(f"{minute_index:02}")

    def get_selected_daily_time(self, show_error=True):
        if not hasattr(self, "daily_hour_var") or not hasattr(self, "daily_minute_var"):
            return None

        selected_hour = self.daily_hour_var.get().strip()
        selected_minute = self.daily_minute_var.get().strip()

        if not selected_hour or not selected_minute:
            if show_error:
                messagebox.showinfo("Choose a time", "Choose both an hour and a minute.")
            return None

        try:
            hour = int(selected_hour)
            minute = int(selected_minute)
        except ValueError:
            if show_error:
                messagebox.showerror("Invalid time", "Hour and minute must be numbers.")
            return None

        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            if show_error:
                messagebox.showerror("Invalid time", "Choose an hour from 00-23 and a minute from 00-59.")
            return None

        return f"{hour:02}:{minute:02}"

    def open_extra_reminder_dialog(self):
        window, body = self.dialog("Extra reminder", 560, 310)

        tk.Label(body, text="Extra reminder", bg=PANEL_BG, fg=TEXT_COLOR, font=("Helvetica", 20, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 14)
        )

        default_one_time = datetime.now() + timedelta(hours=1)
        self.label(body, "Date", 1, 0, bold=True, pady=(0, 4))
        self.one_time_date = self.entry(body, 2, 0, columnspan=3, pady=(0, 12))
        self.one_time_date.insert(0, default_one_time.strftime("%Y-%m-%d"))

        self.label(body, "Time", 3, 0, bold=True, pady=(8, 4))
        self.one_time_hour = self.spinbox(body, 4, 0, 0, 23, padx=(0, 6))
        self.one_time_hour.delete(0, tk.END)
        self.one_time_hour.insert(0, default_one_time.strftime("%H"))
        self.label(body, ":", 4, 1, bold=True, padx=(0, 6))
        self.one_time_minute = self.spinbox(body, 4, 2, 0, 59, padx=(0, 12))
        self.one_time_minute.delete(0, tk.END)
        self.one_time_minute.insert(0, default_one_time.strftime("%M"))
        self.button(body, "Add reminder", self.add_one_time_reminder, 4, 3)

    def open_history_dialog(self):
        window, body = self.dialog("History", 660, 480)

        tk.Label(body, text="History", bg=PANEL_BG, fg=TEXT_COLOR, font=("Helvetica", 20, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 14)
        )
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)

        self.history_text = tk.Text(
            body,
            bg="#ffffff",
            fg=TEXT_COLOR,
            relief="solid",
            bd=2,
            font=("Menlo", 13),
            height=12,
            wrap="word",
        )
        self.history_text.grid(row=1, column=0, columnspan=3, sticky="nsew")
        scrollbar = tk.Scrollbar(body, command=self.history_text.yview)
        scrollbar.grid(row=1, column=3, sticky="ns")
        self.history_text.configure(yscrollcommand=scrollbar.set)

        self.button(body, "Undo last taken", self.undo_last_taken, 2, 0, pady=(12, 0), padx=(0, 8))
        self.button(body, "Clear history", self.clear_history, 2, 1, danger=True, pady=(12, 0), padx=(0, 8))
        self.button(body, "Open data folder", self.open_data_folder, 2, 2, pady=(12, 0))
        self.refresh_history_list()

    def get_snoozes(self):
        return [parse_datetime(value) for value in self.data.get("snoozes", []) if isinstance(value, str)]

    def save_snoozes(self, values):
        self.data["snoozes"] = [format_datetime(value) for value in sorted(values)]
        self.save_data()

    def get_one_time_reminders(self):
        return [parse_datetime(value) for value in self.data.get("one_time_reminders", []) if isinstance(value, str)]

    def save_one_time_reminders(self, values):
        self.data["one_time_reminders"] = [format_datetime(value) for value in sorted(values)]
        self.save_data()

    def set_feedback(self, message):
        self.feedback_label.config(text=message)

    def save_settings(self):
        pill_name = self.pill_name_entry.get().strip()

        if not pill_name:
            messagebox.showerror("Missing pill name", "Type the pill name first.")
            return

        reminder_time = self.get_selected_daily_time()

        if not reminder_time:
            return

        self.data["pill_name"] = pill_name
        self.data["daily_reminders"] = [reminder_time]
        self.data["reminder_time"] = reminder_time
        self.daily_hour_var.set(reminder_time.split(":")[0])
        self.daily_minute_var.set(reminder_time.split(":")[1])
        self.save_data()
        self.refresh_all()
        self.set_feedback(f"Saved {pill_name} reminder for {reminder_time}.")
        self.update_settings_time_preview()
        if self.widget_is_alive("settings_feedback_label"):
            self.settings_feedback_label.config(text=f"Saved {pill_name} at {reminder_time}.")

    def normalize_selected_daily_time(self):
        reminder_time = self.get_selected_daily_time()

        if not reminder_time:
            return None

        if not is_valid_time(reminder_time):
            messagebox.showerror("Invalid time", "Choose a valid 24-hour time.")
            return None

        return reminder_time

    def add_daily_reminder(self):
        reminder_time = self.normalize_selected_daily_time()

        if not reminder_time:
            return

        if reminder_time in self.data["daily_reminders"]:
            self.set_feedback(f"{reminder_time} is already in your daily reminders.")
            return

        self.data["daily_reminders"] = sorted(self.data["daily_reminders"] + [reminder_time])
        self.data["reminder_time"] = reminder_time
        self.save_data()
        self.refresh_all()
        self.set_feedback(f"Added daily reminder for {reminder_time}.")

    def update_selected_daily(self):
        selected = self.daily_listbox.curselection()

        if not selected:
            messagebox.showinfo("No daily time selected", "Select a daily reminder time from the list first.")
            return

        old_time = self.daily_listbox.get(selected[0]).split()[0]
        new_time = self.normalize_selected_daily_time()

        if not new_time:
            return

        self.data["daily_reminders"] = sorted(new_time if value == old_time else value for value in self.data["daily_reminders"])
        self.data["reminder_time"] = new_time
        self.save_data()
        self.refresh_all()
        self.set_feedback(f"Updated daily reminder to {new_time}.")

    def remove_selected_daily(self):
        selected = self.daily_listbox.curselection()

        if not selected:
            messagebox.showinfo("No daily time selected", "Select a daily reminder time from the list first.")
            return

        if len(self.data["daily_reminders"]) == 1:
            messagebox.showinfo("Keep one reminder", "You need at least one daily reminder.")
            return

        selected_time = self.daily_listbox.get(selected[0]).split()[0]
        self.data["daily_reminders"] = [value for value in self.data["daily_reminders"] if value != selected_time]
        self.data["reminder_time"] = self.data["daily_reminders"][0]
        self.save_data()
        self.refresh_all()
        self.set_feedback(f"Deleted daily reminder {selected_time}.")

    def load_selected_daily(self, _event=None):
        selected = self.daily_listbox.curselection()

        if not selected:
            return

        hour, minute = self.daily_listbox.get(selected[0]).split()[0].split(":")
        self.set_daily_time_selection(hour, minute)

    def add_one_time_reminder(self):
        reminder_time = f"{self.one_time_hour.get().strip().zfill(2)}:{self.one_time_minute.get().strip().zfill(2)}"
        raw_datetime = f"{self.one_time_date.get().strip()} {reminder_time}"

        try:
            reminder = parse_datetime(raw_datetime)
        except ValueError:
            messagebox.showerror("Invalid one-time reminder", "Use date YYYY-MM-DD and a valid 24-hour time.")
            return

        if reminder <= datetime.now():
            messagebox.showerror("Past reminder", "Choose a future date and time.")
            return

        reminders = self.get_one_time_reminders()

        if reminder not in reminders:
            reminders.append(reminder)

        self.save_one_time_reminders(reminders)
        self.refresh_all()
        self.set_feedback(f"Added one-time reminder for {reminder:%Y-%m-%d at %H:%M}.")

    def get_upcoming_items(self):
        now = datetime.now()
        today = date.today()
        items = []

        for snooze in self.get_snoozes():
            items.append({"due": snooze, "kind": "Snoozed", "id": format_datetime(snooze)})

        for reminder in self.get_one_time_reminders():
            items.append({"due": reminder, "kind": "One-Time", "id": format_datetime(reminder)})

        for reminder in self.data["daily_reminders"]:
            hour, minute = reminder.split(":")
            due = datetime(today.year, today.month, today.day, int(hour), int(minute))

            if self.data.get("last_taken") == today.isoformat():
                due += timedelta(days=1)

            items.append({"due": due, "kind": "Daily", "id": reminder})

        return sorted(items, key=lambda item: item["due"])

    def refresh_all(self):
        self.refresh_status()
        self.refresh_daily_list()
        self.refresh_upcoming_list()
        self.refresh_history_list()

    def refresh_status(self):
        today = date.today().isoformat()
        pill_name = self.get_pill_name()
        today_text = date.today().strftime("%A, %B %-d") if sys.platform != "win32" else date.today().strftime("%A, %B %#d")
        self.pill_title_label.config(text=f"{pill_name}")
        self.date_label.config(text=today_text)

        if self.data.get("last_taken") == today:
            self.status_icon_label.config(text="✓", fg=PRIMARY_BG)
            self.status_label.config(text=f"Taken today at {self.data.get('last_taken_time', 'unknown time')}", bg=PANEL_BG)
        else:
            self.status_icon_label.config(text="○", fg="#c4473d")
            self.status_label.config(text="Not taken today", bg=PANEL_BG)

        upcoming = self.get_upcoming_items()
        if upcoming:
            due = upcoming[0]["due"]
            self.next_label.config(text=f"{due:%I:%M %p}".lstrip("0"))
            self.next_detail_label.config(text=friendly_due_text(due))
        else:
            self.next_label.config(text="None")
            self.next_detail_label.config(text="No reminder time set")

        self.current_reminder_label.config(text=self.get_daily_reminder_text())

        history = self.get_history()
        if history:
            self.latest_history_label.config(text=f"Last taken: {history[-1]}")
        else:
            self.latest_history_label.config(text="No history yet.")

    def refresh_daily_list(self):
        if not self.widget_is_alive("daily_listbox"):
            return

        self.daily_listbox.delete(0, tk.END)
        for reminder in self.data["daily_reminders"]:
            self.daily_listbox.insert(tk.END, f"{reminder} daily")

    def refresh_upcoming_list(self):
        self.upcoming_items = self.get_upcoming_items()
        if not self.widget_is_alive("upcoming_listbox"):
            return

        self.upcoming_listbox.delete(0, tk.END)

        for item in self.upcoming_items:
            self.upcoming_listbox.insert(
                tk.END,
                f"{item['due']:%b %d %H:%M}  {item['kind']:<8}  {relative_due_text(item['due'])}",
            )

    def refresh_history_list(self):
        if not self.widget_is_alive("history_text"):
            return

        self.history_text.config(state="normal")
        self.history_text.delete("1.0", tk.END)
        history = self.get_history()

        if not history:
            self.history_text.insert(tk.END, "No pills marked taken yet.")
            self.history_text.config(state="disabled")
            return

        for entry in reversed(history):
            self.history_text.insert(tk.END, f"{entry}\n")

        self.history_text.config(state="disabled")

    def mark_taken(self, item=None):
        now = datetime.now()
        today = now.date().isoformat()

        if self.data.get("last_taken") != today:
            taken_time = now.strftime("%Y-%m-%d at %H:%M")
            history = self.get_history()
            history.append(f"{taken_time} - {self.get_pill_name()}")
            self.data["history"] = history[-HISTORY_LIMIT:]
            self.data["last_taken"] = today
            self.data["last_taken_time"] = taken_time

        self.data["snoozes"] = []
        self.complete_reminder_item(item)
        self.save_data()
        self.refresh_all()
        self.set_feedback(f"Marked taken at {now:%H:%M}.")

    def complete_reminder_item(self, item):
        if not item:
            return

        if item["kind"] == "One-Time":
            self.save_one_time_reminders(
                [value for value in self.get_one_time_reminders() if format_datetime(value) != item["id"]]
            )
        elif item["kind"] == "Snoozed":
            self.save_snoozes([value for value in self.get_snoozes() if format_datetime(value) != item["id"]])

    def mark_selected_upcoming_taken(self):
        selected = self.upcoming_listbox.curselection()

        if not selected:
            messagebox.showinfo("No reminder selected", "Select a reminder from the upcoming list first.")
            return

        self.mark_taken(self.upcoming_items[selected[0]])

    def remove_selected_upcoming(self):
        selected = self.upcoming_listbox.curselection()

        if not selected:
            messagebox.showinfo("No reminder selected", "Select a reminder from the upcoming list first.")
            return

        item = self.upcoming_items[selected[0]]

        if item["kind"] == "Daily":
            if len(self.data["daily_reminders"]) == 1:
                messagebox.showinfo("Keep one reminder", "You need at least one daily reminder.")
                return
            self.data["daily_reminders"] = [value for value in self.data["daily_reminders"] if value != item["id"]]
        else:
            self.complete_reminder_item(item)

        self.save_data()
        self.refresh_all()
        self.set_feedback(f"Deleted {item['kind'].lower()} reminder.")

    def undo_last_taken(self):
        history = self.get_history()

        if not history:
            return

        history.pop()
        self.data["history"] = history[-HISTORY_LIMIT:]
        latest = max((entry for entry in history if parse_history_datetime(entry)), default=None, key=parse_history_datetime)

        if latest:
            latest_time = parse_history_datetime(latest)
            self.data["last_taken"] = latest_time.date().isoformat()
            self.data["last_taken_time"] = latest.split(" - ", 1)[0]
        else:
            self.data.pop("last_taken", None)
            self.data.pop("last_taken_time", None)

        self.save_data()
        self.refresh_all()
        self.set_feedback("Undid last taken record.")

    def reset_today(self):
        today = date.today()
        history = [entry for entry in self.get_history() if not parse_history_datetime(entry) or parse_history_datetime(entry).date() != today]
        self.data["history"] = history[-HISTORY_LIMIT:]
        self.data.pop("last_taken", None)
        self.data.pop("last_taken_time", None)
        self.data["snoozes"] = []
        self.data["reminders_shown"] = []
        self.save_data()
        self.refresh_all()
        self.set_feedback("Removed today's taken mark.")

    def clear_history(self):
        if not messagebox.askyesno("Clear history", "Clear all taken history?"):
            return

        self.data["history"] = []
        self.data.pop("last_taken", None)
        self.data.pop("last_taken_time", None)
        self.save_data()
        self.refresh_all()

    def snooze_reminder(self, item=None):
        if item:
            self.complete_reminder_item(item)

        snooze_time = (datetime.now() + timedelta(minutes=SNOOZE_MINUTES)).replace(second=0, microsecond=0)
        snoozes = self.get_snoozes()
        snoozes.append(snooze_time)
        self.save_snoozes(snoozes)
        self.refresh_all()
        self.set_feedback(f"Snoozed until {snooze_time:%H:%M}.")

    def tick_clock(self):
        self.clock_label.config(text=datetime.now().strftime("%A, %b %d  %H:%M:%S"))
        self.root.after(1000, self.tick_clock)

    def send_notification(self, message):
        if sys.platform != "darwin":
            return

        safe_message = message.replace('"', '\\"')
        safe_title = APP_NAME.replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}" sound name "Glass"'
        subprocess.run(["osascript", "-e", script], check=False)

    def show_reminder_popup(self, label="Reminder", item=None):
        if self.active_popup and self.active_popup.winfo_exists():
            self.active_popup.lift()
            self.active_popup.focus_force()
            return False

        self.send_notification(f"Time to take {self.get_pill_name()}.")
        self.root.deiconify()
        self.root.lift()
        self.root.bell()

        popup = tk.Toplevel(self.root)
        self.active_popup = popup
        popup.title(APP_NAME)
        popup.geometry("420x220")
        popup.configure(bg=WINDOW_BG)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.after(1500, lambda: popup.attributes("-topmost", False) if popup.winfo_exists() else None)

        def close_popup():
            self.active_popup = None
            popup.destroy()

        tk.Label(
            popup,
            text=f"Time to take {self.get_pill_name()}",
            bg=WINDOW_BG,
            fg=TEXT_COLOR,
            font=("Helvetica", 18, "bold"),
            wraplength=360,
        ).pack(pady=(26, 8))
        tk.Label(popup, text=label, bg=WINDOW_BG, fg=MUTED_COLOR, font=("Helvetica", 13)).pack()

        buttons = tk.Frame(popup, bg=WINDOW_BG)
        buttons.pack(pady=24)
        self.button(buttons, "Taken", lambda: [self.mark_taken(item), close_popup()]).pack(side="left", padx=5)
        self.button(buttons, f"Snooze {SNOOZE_MINUTES} min", lambda: [self.snooze_reminder(item), close_popup()]).pack(
            side="left", padx=5
        )
        self.button(buttons, "Dismiss", close_popup).pack(side="left", padx=5)
        popup.protocol("WM_DELETE_WINDOW", close_popup)
        return True

    def show_test_reminder(self):
        self.show_reminder_popup("Test reminder")

    def get_last_reminder_attempt(self, reminder):
        today = date.today().isoformat()
        prefix = f"{today}|{reminder}|"
        attempts = []

        for value in self.data.get("reminders_shown", []):
            if isinstance(value, str) and value.startswith(prefix):
                try:
                    attempts.append(parse_datetime(value.removeprefix(prefix)))
                except ValueError:
                    pass

        return max(attempts, default=None)

    def record_daily_reminder_attempt(self, reminder, now):
        today = date.today().isoformat()
        prefix = f"{today}|{reminder}|"
        self.data["reminders_shown"] = [
            value
            for value in self.data.get("reminders_shown", [])
            if isinstance(value, str) and value.startswith(f"{today}|") and not value.startswith(prefix)
        ]
        self.data["reminders_shown"].append(f"{prefix}{format_datetime(now)}")

    def check_reminders(self):
        now = datetime.now()

        for snooze in self.get_snoozes():
            if snooze <= now:
                item = {"due": snooze, "kind": "Snoozed", "id": format_datetime(snooze)}
                self.show_reminder_popup(f"Snoozed reminder at {snooze:%H:%M}", item)
                self.root.after(CHECK_INTERVAL_MS, self.check_reminders)
                return

        for reminder in self.get_one_time_reminders():
            if reminder <= now:
                item = {"due": reminder, "kind": "One-Time", "id": format_datetime(reminder)}
                self.show_reminder_popup(f"One-time reminder at {reminder:%H:%M}", item)
                self.root.after(CHECK_INTERVAL_MS, self.check_reminders)
                return

        if self.data.get("last_taken") != now.date().isoformat():
            current_minutes = now.hour * 60 + now.minute

            for reminder in self.data["daily_reminders"]:
                last_attempt = self.get_last_reminder_attempt(reminder)

                if time_to_minutes(reminder) <= current_minutes and (
                    not last_attempt or now - last_attempt >= timedelta(minutes=REPEAT_REMINDER_MINUTES)
                ):
                    item = {"due": now, "kind": "Daily", "id": reminder}

                    if self.show_reminder_popup(f"Daily reminder at {reminder}", item):
                        self.record_daily_reminder_attempt(reminder, now)
                        self.save_data()

                    self.root.after(CHECK_INTERVAL_MS, self.check_reminders)
                    return

        self.refresh_all()
        self.root.after(CHECK_INTERVAL_MS, self.check_reminders)

    def open_data_folder(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)

        if sys.platform == "darwin":
            subprocess.run(["open", str(APP_DIR)], check=False)
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(APP_DIR)], check=False)
        else:
            subprocess.run(["xdg-open", str(APP_DIR)], check=False)


def main():
    root = tk.Tk()
    PillReminderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

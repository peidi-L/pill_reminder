import json
import subprocess
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox


APP_NAME = "Pill Reminder"
APP_VERSION = "Dashboard v2"
APP_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
DATA_FILE = APP_DIR / "data.json"
LEGACY_HOME_DATA_FILE = Path.home() / ".pill_reminder.json"
LEGACY_LOCAL_DATA_FILE = Path("pill_data.json")

TIME_FORMAT = "%H:%M"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
CHECK_INTERVAL_MS = 15000
SNOOZE_MINUTES = 10
HISTORY_LIMIT = 90

WINDOW_BG = "#f5f7fb"
CARD_BG = "#ffffff"
TEXT_COLOR = "#1f2933"
MUTED_COLOR = "#5f6b7a"
BUTTON_BG = "#e9f0ff"
BUTTON_ACTIVE_BG = "#d8e5ff"
DANGER_BG = "#fff0f0"
TAKEN_BG = "#e8f7ef"
OPEN_BG = "#f3f5f8"
OVERDUE_BG = "#fff4df"


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


def parse_history_date(entry):
    if not isinstance(entry, str):
        return None

    try:
        return datetime.strptime(entry[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def short_date_label(day):
    return day.strftime("%b %d").replace(" 0", " ")


def relative_due_text(due):
    now = datetime.now()
    seconds = int((due - now).total_seconds())

    if seconds <= -60:
        minutes = abs(seconds) // 60
        hours = minutes // 60
        remaining_minutes = minutes % 60

        if hours >= 24:
            days = hours // 24
            return f"{days} day{'s' if days != 1 else ''} overdue"

        if hours:
            return f"{hours}h {remaining_minutes}m overdue"

        return f"{minutes} min overdue"

    if seconds <= 60:
        return "due now"

    minutes = seconds // 60
    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours >= 24:
        days = hours // 24
        return f"in {days} day{'s' if days != 1 else ''}"

    if hours:
        return f"in {hours}h {remaining_minutes}m"

    return f"in {minutes}m"


def time_to_minutes(value):
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def normalize_time(hour, minute):
    return f"{hour.strip().zfill(2)}:{minute.strip().zfill(2)}"


def load_data():
    for data_file in (DATA_FILE, LEGACY_HOME_DATA_FILE, LEGACY_LOCAL_DATA_FILE):
        if not data_file.exists():
            continue

        try:
            return json.loads(data_file.read_text())
        except json.JSONDecodeError:
            return {}

    return {}


def valid_time_list(values, fallback=None):
    fallback = fallback or []

    if not isinstance(values, list):
        return fallback

    clean_values = sorted({value for value in values if isinstance(value, str) and is_valid_time(value)})
    return clean_values or fallback


def valid_datetime_list(values):
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

    return sorted(clean_values)


def prepare_data(raw_data):
    data = raw_data if isinstance(raw_data, dict) else {}
    old_reminder = data.get("reminder_time", "21:00")
    fallback_reminder = old_reminder if isinstance(old_reminder, str) and is_valid_time(old_reminder) else "21:00"

    return {
        "daily_reminders": valid_time_list(data.get("daily_reminders", data.get("reminders")), [fallback_reminder]),
        "one_time_reminders": [format_datetime(value) for value in valid_datetime_list(data.get("one_time_reminders"))],
        "snoozes": [format_datetime(value) for value in valid_datetime_list(data.get("snoozes"))],
        "history": data.get("history", []) if isinstance(data.get("history"), list) else [],
        "last_taken": data.get("last_taken") if isinstance(data.get("last_taken"), str) else None,
        "last_taken_time": data.get("last_taken_time") if isinstance(data.get("last_taken_time"), str) else None,
        "reminders_shown": data.get("reminders_shown", []) if isinstance(data.get("reminders_shown"), list) else [],
        "pill_name": data.get("pill_name") if isinstance(data.get("pill_name"), str) else "Birth Control Pill",
    }


class PillReminderApp:
    def __init__(self, root):
        self.root = root
        self.data = prepare_data(load_data())
        self.upcoming_items = []

        self.root.title(f"{APP_NAME} - {APP_VERSION}")
        self.root.geometry("980x760")
        self.root.minsize(900, 700)

        self.configure_style()
        self.build_ui()
        self.save_data()
        self.refresh_all()
        self.check_reminders()

    def configure_style(self):
        self.root.configure(bg=WINDOW_BG)
        self.root.option_add("*Label.foreground", TEXT_COLOR)
        self.root.option_add("*Label.background", CARD_BG)
        self.root.option_add("*Entry.foreground", TEXT_COLOR)
        self.root.option_add("*Listbox.foreground", TEXT_COLOR)

    def card(self, parent, title):
        frame = tk.Frame(
            parent,
            bg=CARD_BG,
            highlightbackground="#d5dce8",
            highlightcolor="#d5dce8",
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        tk.Label(
            frame,
            text=title,
            bg=CARD_BG,
            fg=TEXT_COLOR,
            font=("Helvetica", 13, "bold"),
        ).pack(anchor="w", pady=(0, 10))
        return frame

    def button(self, parent, text, command, danger=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=DANGER_BG if danger else BUTTON_BG,
            activebackground=BUTTON_ACTIVE_BG,
            fg=TEXT_COLOR,
            bd=1,
            relief="raised",
            padx=12,
            pady=6,
            cursor="hand2",
        )

    def label(self, parent, text="", font=None, muted=False):
        return tk.Label(
            parent,
            text=text,
            bg=CARD_BG,
            fg=MUTED_COLOR if muted else TEXT_COLOR,
            font=font or ("Helvetica", 12),
            anchor="w",
            justify="left",
        )

    def build_ui(self):
        main = tk.Frame(self.root, bg=WINDOW_BG, padx=16, pady=14)
        main.pack(fill="both", expand=True)

        header = tk.Frame(main, bg=WINDOW_BG)
        header.pack(fill="x", pady=(0, 12))

        tk.Label(
            header,
            text=f"{APP_NAME} Dashboard",
            bg=WINDOW_BG,
            fg=TEXT_COLOR,
            font=("Helvetica", 24, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text=APP_VERSION,
            bg=WINDOW_BG,
            fg=MUTED_COLOR,
            font=("Helvetica", 12),
        ).pack(side="right", pady=(8, 0))

        body = tk.Frame(main, bg=WINDOW_BG)
        body.pack(fill="both", expand=True)

        left_column = tk.Frame(body, bg=WINDOW_BG)
        left_column.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right_column = tk.Frame(body, bg=WINDOW_BG)
        right_column.pack(side="left", fill="both", expand=True, padx=(8, 0))

        today_frame = self.card(left_column, "Today")
        today_frame.pack(fill="x", pady=(0, 12))

        pill_row = tk.Frame(today_frame, bg=CARD_BG)
        pill_row.pack(fill="x", pady=(0, 10))

        self.label(pill_row, "Pill").pack(side="left", padx=(0, 8))
        self.pill_name_entry = tk.Entry(pill_row, width=28, relief="solid", bd=1)
        self.pill_name_entry.insert(0, self.get_pill_name())
        self.pill_name_entry.pack(side="left")
        self.button(pill_row, "Save Name", self.save_settings).pack(side="left", padx=(10, 0))

        self.status_label = self.label(today_frame, font=("Helvetica", 15, "bold"))
        self.status_label.pack(anchor="w")

        self.next_label = self.label(today_frame)
        self.next_label.pack(anchor="w", pady=(6, 0))

        self.streak_label = self.label(today_frame)
        self.streak_label.pack(anchor="w", pady=(6, 0))

        today_actions = tk.Frame(today_frame, bg=CARD_BG)
        today_actions.pack(anchor="w", pady=(12, 0))

        self.button(today_actions, "Taken Now", self.mark_taken).pack(side="left", padx=(0, 8))
        self.button(today_actions, "Reset Today", self.reset_today).pack(side="left", padx=(0, 8))
        self.button(today_actions, "Test Reminder", self.show_test_reminder).pack(side="left")

        progress_frame = self.card(left_column, "Last 14 Days")
        progress_frame.pack(fill="x", pady=(0, 12))

        self.day_grid = tk.Frame(progress_frame, bg=CARD_BG)
        self.day_grid.pack(fill="x")
        self.day_labels = []

        for column in range(7):
            self.day_grid.columnconfigure(column, weight=1)

        for index in range(14):
            day_label = tk.Label(
                self.day_grid,
                text="",
                bg=OPEN_BG,
                fg=TEXT_COLOR,
                font=("Helvetica", 10),
                relief="solid",
                bd=1,
                padx=4,
                pady=6,
            )
            day_label.grid(row=index // 7, column=index % 7, sticky="ew", padx=2, pady=2)
            self.day_labels.append(day_label)

        daily_frame = self.card(left_column, "Daily Reminders")
        daily_frame.pack(fill="x", pady=(0, 12))

        daily_input = tk.Frame(daily_frame, bg=CARD_BG)
        daily_input.pack(anchor="w")

        self.label(daily_input, "Time").pack(side="left", padx=(0, 8))
        default_hour, default_minute = self.data["daily_reminders"][0].split(":")

        self.daily_hour = tk.Spinbox(daily_input, from_=0, to=23, width=3, format="%02.0f", justify="center")
        self.daily_hour.delete(0, tk.END)
        self.daily_hour.insert(0, default_hour)
        self.daily_hour.pack(side="left")

        self.label(daily_input, ":").pack(side="left", padx=4)

        self.daily_minute = tk.Spinbox(daily_input, from_=0, to=59, width=3, format="%02.0f", justify="center")
        self.daily_minute.delete(0, tk.END)
        self.daily_minute.insert(0, default_minute)
        self.daily_minute.pack(side="left")

        self.button(daily_input, "Add Daily", self.add_daily_reminder).pack(side="left", padx=(12, 0))
        self.button(daily_input, "Update Selected", self.update_selected_daily).pack(side="left", padx=(8, 0))

        daily_list_frame = tk.Frame(daily_frame, bg=CARD_BG)
        daily_list_frame.pack(anchor="w", fill="x", pady=(12, 0))

        self.daily_listbox = tk.Listbox(
            daily_list_frame,
            height=5,
            width=20,
            exportselection=False,
            bg="#fbfdff",
            fg=TEXT_COLOR,
            selectbackground="#cfe0ff",
            relief="solid",
            bd=1,
        )
        self.daily_listbox.pack(side="left", fill="x", expand=True)
        self.daily_listbox.bind("<<ListboxSelect>>", self.load_selected_daily)

        daily_scrollbar = tk.Scrollbar(daily_list_frame, orient="vertical", command=self.daily_listbox.yview)
        daily_scrollbar.pack(side="left", fill="y")
        self.daily_listbox.configure(yscrollcommand=daily_scrollbar.set)

        self.button(daily_frame, "Remove Selected Daily", self.remove_selected_daily, danger=True).pack(
            anchor="w",
            pady=(10, 0),
        )

        one_time_frame = self.card(left_column, "One-Time Reminder")
        one_time_frame.pack(fill="x")

        one_time_input = tk.Frame(one_time_frame, bg=CARD_BG)
        one_time_input.pack(anchor="w")

        default_one_time = datetime.now() + timedelta(hours=1)
        self.label(one_time_input, "Date").pack(side="left", padx=(0, 8))

        self.one_time_date = tk.Entry(one_time_input, width=12, relief="solid", bd=1)
        self.one_time_date.insert(0, default_one_time.strftime("%Y-%m-%d"))
        self.one_time_date.pack(side="left")

        self.label(one_time_input, "Time").pack(side="left", padx=(12, 8))

        self.one_time_hour = tk.Spinbox(one_time_input, from_=0, to=23, width=3, format="%02.0f", justify="center")
        self.one_time_hour.delete(0, tk.END)
        self.one_time_hour.insert(0, default_one_time.strftime("%H"))
        self.one_time_hour.pack(side="left")

        self.label(one_time_input, ":").pack(side="left", padx=4)

        self.one_time_minute = tk.Spinbox(one_time_input, from_=0, to=59, width=3, format="%02.0f", justify="center")
        self.one_time_minute.delete(0, tk.END)
        self.one_time_minute.insert(0, default_one_time.strftime("%M"))
        self.one_time_minute.pack(side="left")

        self.button(one_time_input, "Add One-Time", self.add_one_time_reminder).pack(side="left", padx=(12, 0))
        self.label(one_time_frame, "Date format: YYYY-MM-DD", muted=True).pack(anchor="w", pady=(8, 0))

        upcoming_frame = self.card(right_column, "Upcoming Reminders")
        upcoming_frame.pack(fill="both", expand=True, pady=(0, 12))

        upcoming_list_frame = tk.Frame(upcoming_frame, bg=CARD_BG)
        upcoming_list_frame.pack(fill="both", expand=True)
        self.upcoming_listbox = tk.Listbox(
            upcoming_list_frame,
            height=12,
            exportselection=False,
            bg="#fbfdff",
            fg=TEXT_COLOR,
            selectbackground="#cfe0ff",
            relief="solid",
            bd=1,
            font=("Menlo", 12),
        )
        self.upcoming_listbox.pack(side="left", fill="both", expand=True)

        upcoming_scrollbar = tk.Scrollbar(upcoming_list_frame, orient="vertical", command=self.upcoming_listbox.yview)
        upcoming_scrollbar.pack(side="left", fill="y")
        self.upcoming_listbox.configure(yscrollcommand=upcoming_scrollbar.set)

        upcoming_actions = tk.Frame(upcoming_frame, bg=CARD_BG)
        upcoming_actions.pack(anchor="w", pady=(10, 0))

        self.button(upcoming_actions, "Mark Taken", self.mark_selected_upcoming_taken).pack(
            side="left",
            padx=(0, 8),
        )
        self.button(upcoming_actions, "Remove Selected", self.remove_selected_upcoming, danger=True).pack(
            side="left",
            padx=(0, 8),
        )
        self.button(upcoming_actions, "Refresh", self.refresh_all).pack(side="left")

        history_frame = self.card(right_column, "Taken History")
        history_frame.pack(fill="both", expand=True)

        history_list_frame = tk.Frame(history_frame, bg=CARD_BG)
        history_list_frame.pack(fill="both", expand=True)
        self.history_listbox = tk.Listbox(
            history_list_frame,
            height=8,
            width=42,
            exportselection=False,
            bg="#fbfdff",
            fg=TEXT_COLOR,
            selectbackground="#cfe0ff",
            relief="solid",
            bd=1,
        )
        self.history_listbox.pack(side="left", fill="both", expand=True)

        history_scrollbar = tk.Scrollbar(history_list_frame, orient="vertical", command=self.history_listbox.yview)
        history_scrollbar.pack(side="left", fill="y")
        self.history_listbox.configure(yscrollcommand=history_scrollbar.set)

        history_actions = tk.Frame(history_frame, bg=CARD_BG)
        history_actions.pack(anchor="w", pady=(10, 0))

        self.button(history_actions, "Undo Last Taken", self.undo_last_taken).pack(side="left", padx=(0, 8))
        self.button(history_actions, "Clear History", self.clear_history, danger=True).pack(side="left")

        footer = tk.Frame(main, bg=WINDOW_BG)
        footer.pack(fill="x", pady=(12, 0))

        tk.Label(
            footer,
            text="Keep this app open so reminders can appear.",
            bg=WINDOW_BG,
            fg=MUTED_COLOR,
            font=("Helvetica", 11),
        ).pack(side="left")
        self.button(footer, "Open Data Folder", self.open_data_folder).pack(side="right", padx=(8, 0))
        self.button(footer, "Save Now", self.save_data).pack(side="right")

    def save_data(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps(self.data, indent=2))

    def get_pill_name(self):
        pill_name = self.data.get("pill_name")
        return pill_name.strip() if isinstance(pill_name, str) and pill_name.strip() else "Birth Control Pill"

    def save_settings(self):
        pill_name = self.pill_name_entry.get().strip()

        if not pill_name:
            messagebox.showerror("Missing Name", "Enter a pill name.")
            return

        self.data["pill_name"] = pill_name
        self.save_data()
        self.refresh_all()
        messagebox.showinfo("Saved", "Pill name saved.")

    def get_snoozes(self):
        return valid_datetime_list(self.data.get("snoozes"))

    def save_snoozes(self, snoozes):
        self.data["snoozes"] = [format_datetime(value) for value in sorted(snoozes)]
        self.save_data()

    def get_one_time_reminders(self):
        return valid_datetime_list(self.data.get("one_time_reminders"))

    def save_one_time_reminders(self, reminders):
        self.data["one_time_reminders"] = [format_datetime(value) for value in sorted(reminders)]
        self.save_data()

    def get_history(self):
        history = self.data.get("history")
        return history if isinstance(history, list) else []

    def get_taken_dates(self):
        return {taken_date for taken_date in (parse_history_date(entry) for entry in self.get_history()) if taken_date}

    def get_current_streak(self):
        taken_dates = self.get_taken_dates()
        streak = 0
        cursor = date.today()

        while cursor in taken_dates:
            streak += 1
            cursor -= timedelta(days=1)

        return streak

    def get_latest_history_entry(self):
        for entry in reversed(self.get_history()):
            if parse_history_date(entry):
                return entry

        return None

    def get_upcoming_items(self):
        now = datetime.now()
        today = date.today()
        items = []

        for snooze in self.get_snoozes():
            if snooze >= now:
                items.append({"due": snooze, "kind": "Snoozed", "id": format_datetime(snooze)})

        for reminder in self.get_one_time_reminders():
            if reminder >= now:
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
        self.refresh_progress()
        self.refresh_daily_list()
        self.refresh_upcoming_list()
        self.refresh_history_list()

    def refresh_status(self):
        today = date.today().isoformat()
        pill_name = self.get_pill_name()

        if self.data.get("last_taken") == today:
            status_text = f"{pill_name}: taken today at {self.data.get('last_taken_time', 'unknown time')}"
        elif self.data.get("last_taken_time"):
            status_text = f"{pill_name}: last taken {self.data['last_taken_time']}"
        else:
            status_text = f"{pill_name}: not marked taken today"

        self.status_label.config(text=status_text)

        upcoming_items = self.get_upcoming_items()

        if upcoming_items:
            next_due = upcoming_items[0]["due"]
            when_text = "now" if next_due <= datetime.now() else next_due.strftime("%Y-%m-%d at %H:%M")
            self.next_label.config(text=f"Next reminder: {when_text}")
        else:
            self.next_label.config(text="Next reminder: none")

        streak = self.get_current_streak()
        day_word = "day" if streak == 1 else "days"
        self.streak_label.config(text=f"Current streak: {streak} {day_word}")

    def refresh_progress(self):
        taken_dates = self.get_taken_dates()
        start_day = date.today() - timedelta(days=13)

        for index, day_label in enumerate(self.day_labels):
            day = start_day + timedelta(days=index)
            was_taken = day in taken_dates

            if was_taken:
                status = "Taken"
                background = TAKEN_BG
            elif day < date.today():
                status = "No Log"
                background = OPEN_BG
            else:
                status = "Open"
                background = OPEN_BG

            day_label.config(
                text=f"{short_date_label(day)}\n{status}",
                bg=background,
            )

    def refresh_daily_list(self):
        self.daily_listbox.delete(0, tk.END)

        for reminder in self.data["daily_reminders"]:
            self.daily_listbox.insert(tk.END, reminder)

    def load_selected_daily(self, _event=None):
        selected_indexes = self.daily_listbox.curselection()

        if not selected_indexes:
            return

        selected_time = self.daily_listbox.get(selected_indexes[0])
        hour, minute = selected_time.split(":")
        self.daily_hour.delete(0, tk.END)
        self.daily_hour.insert(0, hour)
        self.daily_minute.delete(0, tk.END)
        self.daily_minute.insert(0, minute)

    def refresh_upcoming_list(self):
        self.upcoming_items = self.get_upcoming_items()
        self.upcoming_listbox.delete(0, tk.END)

        for item in self.upcoming_items[:20]:
            due_text = item["due"].strftime("%a %b %d %H:%M")
            relative_text = relative_due_text(item["due"])
            self.upcoming_listbox.insert(tk.END, f"{due_text:<18} {item['kind']:<9} {relative_text}")

            if item["due"] <= datetime.now():
                self.upcoming_listbox.itemconfig(self.upcoming_listbox.size() - 1, bg=OVERDUE_BG)

    def refresh_history_list(self):
        self.history_listbox.delete(0, tk.END)
        history = self.get_history()

        if not history:
            self.history_listbox.insert(tk.END, "No pills marked taken yet.")
            return

        for entry in reversed(history):
            self.history_listbox.insert(tk.END, entry)

    def add_daily_reminder(self):
        reminder_time = normalize_time(self.daily_hour.get(), self.daily_minute.get())

        if not is_valid_time(reminder_time):
            messagebox.showerror("Invalid Time", "Choose a valid 24-hour time.")
            return

        if reminder_time in self.data["daily_reminders"]:
            messagebox.showinfo("Already Added", f"{reminder_time} is already in your daily reminders.")
            return

        self.data["daily_reminders"].append(reminder_time)
        self.data["daily_reminders"] = sorted(self.data["daily_reminders"])
        self.data["reminder_time"] = reminder_time
        self.save_data()
        self.refresh_all()
        messagebox.showinfo("Added", f"Daily reminder added for {reminder_time}.")

    def update_selected_daily(self):
        selected_indexes = self.daily_listbox.curselection()

        if not selected_indexes:
            messagebox.showinfo("No Reminder Selected", "Select a daily reminder to update.")
            return

        old_time = self.daily_listbox.get(selected_indexes[0])
        new_time = normalize_time(self.daily_hour.get(), self.daily_minute.get())

        if not is_valid_time(new_time):
            messagebox.showerror("Invalid Time", "Choose a valid 24-hour time.")
            return

        if new_time != old_time and new_time in self.data["daily_reminders"]:
            messagebox.showinfo("Already Added", f"{new_time} is already in your daily reminders.")
            return

        self.data["daily_reminders"] = sorted(
            new_time if reminder == old_time else reminder for reminder in self.data["daily_reminders"]
        )
        self.data["reminder_time"] = new_time
        self.save_data()
        self.refresh_all()
        messagebox.showinfo("Updated", f"Daily reminder changed to {new_time}.")

    def remove_selected_daily(self):
        selected_indexes = self.daily_listbox.curselection()

        if not selected_indexes:
            messagebox.showinfo("No Reminder Selected", "Select a daily reminder to remove.")
            return

        if len(self.data["daily_reminders"]) == 1:
            messagebox.showinfo("Keep One Reminder", "You need at least one daily reminder.")
            return

        selected_time = self.daily_listbox.get(selected_indexes[0])
        self.data["daily_reminders"] = [reminder for reminder in self.data["daily_reminders"] if reminder != selected_time]
        self.data["reminder_time"] = self.data["daily_reminders"][0]
        self.save_data()
        self.refresh_all()

    def add_one_time_reminder(self):
        reminder_text = normalize_time(self.one_time_hour.get(), self.one_time_minute.get())
        raw_datetime = f"{self.one_time_date.get().strip()} {reminder_text}"

        try:
            reminder_datetime = parse_datetime(raw_datetime)
        except ValueError:
            messagebox.showerror("Invalid Date/Time", "Use a date like 2026-07-07 and a valid 24-hour time.")
            return

        if reminder_datetime <= datetime.now():
            messagebox.showerror("Past Reminder", "Choose a future date and time.")
            return

        reminders = self.get_one_time_reminders()

        if reminder_datetime in reminders:
            messagebox.showinfo("Already Added", "That one-time reminder already exists.")
            return

        reminders.append(reminder_datetime)
        self.save_one_time_reminders(reminders)
        self.refresh_all()
        messagebox.showinfo("Added", f"One-time reminder added for {reminder_datetime:%Y-%m-%d at %H:%M}.")

    def remove_selected_upcoming(self):
        selected = self.upcoming_listbox.curselection()

        if not selected:
            messagebox.showinfo("No Reminder Selected", "Select an upcoming reminder to remove.")
            return

        item = self.upcoming_items[selected[0]]

        if item["kind"] == "Daily":
            if len(self.data["daily_reminders"]) == 1:
                messagebox.showinfo("Keep One Reminder", "You need at least one daily reminder.")
                return

            self.data["daily_reminders"] = [reminder for reminder in self.data["daily_reminders"] if reminder != item["id"]]
            self.data["reminder_time"] = self.data["daily_reminders"][0]
        elif item["kind"] == "One-Time":
            self.save_one_time_reminders(
                [reminder for reminder in self.get_one_time_reminders() if format_datetime(reminder) != item["id"]]
            )
        elif item["kind"] == "Snoozed":
            self.save_snoozes([snooze for snooze in self.get_snoozes() if format_datetime(snooze) != item["id"]])

        self.save_data()
        self.refresh_all()

    def mark_selected_upcoming_taken(self):
        selected = self.upcoming_listbox.curselection()

        if not selected:
            messagebox.showinfo("No Reminder Selected", "Select an upcoming reminder to mark taken.")
            return

        item = self.upcoming_items[selected[0]]

        if item["kind"] == "One-Time":
            self.save_one_time_reminders(
                [reminder for reminder in self.get_one_time_reminders() if format_datetime(reminder) != item["id"]]
            )
        elif item["kind"] == "Snoozed":
            self.save_snoozes([snooze for snooze in self.get_snoozes() if format_datetime(snooze) != item["id"]])

        self.mark_taken()

    def mark_taken(self):
        now = datetime.now()
        today = now.date().isoformat()

        if self.data.get("last_taken") == today:
            messagebox.showinfo("Already Marked", "You already marked today's pill as taken.")
            return

        taken_time = now.strftime("%Y-%m-%d at %H:%M")
        history = self.get_history()
        history.append(f"{taken_time} - {self.get_pill_name()}")

        self.data["last_taken"] = today
        self.data["last_taken_time"] = taken_time
        self.data["history"] = history[-HISTORY_LIMIT:]
        self.data["snoozes"] = []
        self.save_data()
        self.refresh_all()

    def undo_last_taken(self):
        history = self.get_history()

        if not history:
            messagebox.showinfo("No History", "There is no taken history to undo.")
            return

        removed_entry = history.pop()
        self.data["history"] = history[-HISTORY_LIMIT:]

        latest_entry = self.get_latest_history_entry()

        if latest_entry:
            latest_date = parse_history_date(latest_entry)
            self.data["last_taken"] = latest_date.isoformat()
            self.data["last_taken_time"] = latest_entry.split(" - ", 1)[0]
        else:
            self.data.pop("last_taken", None)
            self.data.pop("last_taken_time", None)

        self.save_data()
        self.refresh_all()
        messagebox.showinfo("Undone", f"Removed: {removed_entry}")

    def reset_today(self):
        self.data.pop("last_taken", None)
        self.data.pop("last_taken_time", None)
        self.data["reminders_shown"] = []
        self.data["snoozes"] = []
        self.save_data()
        self.refresh_all()

    def clear_history(self):
        if not messagebox.askyesno("Clear History", "Clear all taken history?"):
            return

        self.data["history"] = []
        self.data.pop("last_taken", None)
        self.data.pop("last_taken_time", None)
        self.save_data()
        self.refresh_all()

    def snooze_reminder(self):
        snooze_time = (datetime.now() + timedelta(minutes=SNOOZE_MINUTES)).replace(second=0, microsecond=0)
        snoozes = self.get_snoozes()
        snoozes.append(snooze_time)
        self.save_snoozes(snoozes)
        self.refresh_all()
        messagebox.showinfo("Snoozed", f"Reminder snoozed until {snooze_time:%H:%M}.")

    def send_mac_notification(self, message):
        safe_message = message.replace('"', '\\"')
        safe_title = APP_NAME.replace('"', '\\"')

        try:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{safe_message}" with title "{safe_title}"',
                ],
                check=False,
            )
        except FileNotFoundError:
            pass

    def show_reminder_popup(self, reminder_label=None):
        message = f"Time to take {self.get_pill_name()}."
        self.send_mac_notification(message)

        popup = tk.Toplevel(self.root)
        popup.title(APP_NAME)
        popup.geometry("420x200")
        popup.resizable(False, False)
        popup.configure(bg=WINDOW_BG)

        tk.Label(
            popup,
            text=message,
            bg=WINDOW_BG,
            fg=TEXT_COLOR,
            font=("Helvetica", 14, "bold"),
            wraplength=300,
        ).pack(pady=(20, 8))
        tk.Label(
            popup,
            text=reminder_label or "Test reminder",
            bg=WINDOW_BG,
            fg=MUTED_COLOR,
            font=("Helvetica", 12),
        ).pack()

        actions = tk.Frame(popup, bg=WINDOW_BG)
        actions.pack(pady=18)

        if reminder_label:
            self.button(actions, "Taken", lambda: [self.mark_taken(), popup.destroy()]).pack(
                side="left",
                padx=4,
            )
            self.button(
                actions,
                f"Snooze {SNOOZE_MINUTES} Min",
                lambda: [self.snooze_reminder(), popup.destroy()],
            ).pack(side="left", padx=4)

        self.button(actions, "Dismiss", popup.destroy).pack(side="left", padx=4)

    def show_test_reminder(self):
        self.show_reminder_popup()

    def check_reminders(self):
        now = datetime.now()
        today = now.date().isoformat()

        if self.data.get("last_taken") != today:
            due_snoozes = [snooze for snooze in self.get_snoozes() if snooze <= now]

            if due_snoozes:
                due_snooze = due_snoozes[0]
                self.save_snoozes([snooze for snooze in self.get_snoozes() if snooze != due_snooze])
                self.refresh_all()
                self.show_reminder_popup(f"Snoozed reminder at {due_snooze:%H:%M}")
                self.root.after(CHECK_INTERVAL_MS, self.check_reminders)
                return

            due_one_time = [reminder for reminder in self.get_one_time_reminders() if reminder <= now]

            if due_one_time:
                due_reminder = due_one_time[0]
                self.save_one_time_reminders(
                    [reminder for reminder in self.get_one_time_reminders() if reminder != due_reminder]
                )
                self.refresh_all()
                self.show_reminder_popup(f"One-time reminder at {due_reminder:%H:%M}")
                self.root.after(CHECK_INTERVAL_MS, self.check_reminders)
                return

            current_minutes = now.hour * 60 + now.minute
            reminders_shown = self.data.get("reminders_shown", [])

            for reminder in self.data["daily_reminders"]:
                reminder_key = f"{today}:{reminder}"

                if time_to_minutes(reminder) <= current_minutes and reminder_key not in reminders_shown:
                    reminders_shown.append(reminder_key)
                    self.data["reminders_shown"] = reminders_shown[-40:]
                    self.save_data()
                    self.refresh_all()
                    self.show_reminder_popup(f"Daily reminder at {reminder}")
                    self.root.after(CHECK_INTERVAL_MS, self.check_reminders)
                    return

        self.refresh_status()
        self.root.after(CHECK_INTERVAL_MS, self.check_reminders)

    def open_data_folder(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(APP_DIR)], check=False)


def main():
    root = tk.Tk()
    PillReminderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

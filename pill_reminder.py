import json
import subprocess
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
HISTORY_LIMIT = 90


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
    }


class PillReminderApp:
    def __init__(self, root):
        self.root = root
        self.data = prepare_data(load_data())
        self.upcoming_items = []

        self.root.title(APP_NAME)
        self.root.geometry("760x620")
        self.root.minsize(720, 560)

        self.configure_style()
        self.build_ui()
        self.save_data()
        self.refresh_all()
        self.check_reminders()

    def configure_style(self):
        style = ttk.Style()

        if "aqua" in style.theme_names():
            style.theme_use("aqua")

        style.configure("Title.TLabel", font=("Helvetica", 22, "bold"))
        style.configure("Status.TLabel", font=("Helvetica", 14, "bold"))
        style.configure("Muted.TLabel", foreground="#555555")

    def build_ui(self):
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Daily pill reminders, one-time reminders, snooze, and history.", style="Muted.TLabel").pack(
            anchor="w",
            pady=(2, 12),
        )

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="both", expand=True)

        self.today_tab = ttk.Frame(self.notebook, padding=12)
        self.reminders_tab = ttk.Frame(self.notebook, padding=12)
        self.history_tab = ttk.Frame(self.notebook, padding=12)
        self.settings_tab = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.today_tab, text="Today")
        self.notebook.add(self.reminders_tab, text="Reminders")
        self.notebook.add(self.history_tab, text="History")
        self.notebook.add(self.settings_tab, text="Settings")

        self.build_today_tab()
        self.build_reminders_tab()
        self.build_history_tab()
        self.build_settings_tab()

    def build_today_tab(self):
        status_frame = ttk.LabelFrame(self.today_tab, text="Today", padding=12)
        status_frame.pack(fill="x")

        self.status_label = ttk.Label(status_frame, text="", style="Status.TLabel")
        self.status_label.pack(anchor="w")

        self.next_label = ttk.Label(status_frame, text="")
        self.next_label.pack(anchor="w", pady=(6, 0))

        today_actions = ttk.Frame(status_frame)
        today_actions.pack(anchor="w", pady=(12, 0))

        ttk.Button(today_actions, text="Taken Today", command=self.mark_taken).pack(side="left", padx=(0, 8))
        ttk.Button(today_actions, text="Reset Today", command=self.reset_today).pack(side="left", padx=(0, 8))
        ttk.Button(today_actions, text="Test Reminder", command=self.show_test_reminder).pack(side="left")

        upcoming_frame = ttk.LabelFrame(self.today_tab, text="Upcoming Reminders", padding=12)
        upcoming_frame.pack(fill="both", expand=True, pady=(14, 0))

        self.upcoming_tree = ttk.Treeview(upcoming_frame, columns=("when", "kind"), show="headings", height=10)
        self.upcoming_tree.heading("when", text="When")
        self.upcoming_tree.heading("kind", text="Type")
        self.upcoming_tree.column("when", width=210, anchor="w")
        self.upcoming_tree.column("kind", width=180, anchor="w")
        self.upcoming_tree.pack(side="left", fill="both", expand=True)

        upcoming_scrollbar = ttk.Scrollbar(upcoming_frame, orient="vertical", command=self.upcoming_tree.yview)
        upcoming_scrollbar.pack(side="left", fill="y")
        self.upcoming_tree.configure(yscrollcommand=upcoming_scrollbar.set)

        upcoming_actions = ttk.Frame(self.today_tab)
        upcoming_actions.pack(anchor="w", pady=(10, 0))

        ttk.Button(upcoming_actions, text="Remove Selected Upcoming", command=self.remove_selected_upcoming).pack(
            side="left",
            padx=(0, 8),
        )
        ttk.Button(upcoming_actions, text="Refresh", command=self.refresh_all).pack(side="left")

    def build_reminders_tab(self):
        daily_frame = ttk.LabelFrame(self.reminders_tab, text="Daily Reminders", padding=12)
        daily_frame.pack(fill="x")

        daily_input = ttk.Frame(daily_frame)
        daily_input.pack(anchor="w")

        ttk.Label(daily_input, text="Time").pack(side="left", padx=(0, 8))
        default_hour, default_minute = self.data["daily_reminders"][0].split(":")

        self.daily_hour = tk.Spinbox(daily_input, from_=0, to=23, width=3, format="%02.0f")
        self.daily_hour.delete(0, tk.END)
        self.daily_hour.insert(0, default_hour)
        self.daily_hour.pack(side="left")

        ttk.Label(daily_input, text=":").pack(side="left", padx=4)

        self.daily_minute = tk.Spinbox(daily_input, from_=0, to=59, width=3, format="%02.0f")
        self.daily_minute.delete(0, tk.END)
        self.daily_minute.insert(0, default_minute)
        self.daily_minute.pack(side="left")

        ttk.Button(daily_input, text="Add Daily Reminder", command=self.add_daily_reminder).pack(side="left", padx=(12, 0))

        daily_list_frame = ttk.Frame(daily_frame)
        daily_list_frame.pack(anchor="w", pady=(12, 0))

        self.daily_listbox = tk.Listbox(daily_list_frame, height=5, width=18, exportselection=False)
        self.daily_listbox.pack(side="left")

        daily_scrollbar = ttk.Scrollbar(daily_list_frame, orient="vertical", command=self.daily_listbox.yview)
        daily_scrollbar.pack(side="left", fill="y")
        self.daily_listbox.configure(yscrollcommand=daily_scrollbar.set)

        ttk.Button(daily_frame, text="Remove Selected Daily Reminder", command=self.remove_selected_daily).pack(
            anchor="w",
            pady=(10, 0),
        )

        one_time_frame = ttk.LabelFrame(self.reminders_tab, text="One-Time Reminder", padding=12)
        one_time_frame.pack(fill="x", pady=(16, 0))

        one_time_input = ttk.Frame(one_time_frame)
        one_time_input.pack(anchor="w")

        default_one_time = datetime.now() + timedelta(hours=1)
        ttk.Label(one_time_input, text="Date").pack(side="left", padx=(0, 8))

        self.one_time_date = ttk.Entry(one_time_input, width=12)
        self.one_time_date.insert(0, default_one_time.strftime("%Y-%m-%d"))
        self.one_time_date.pack(side="left")

        ttk.Label(one_time_input, text="Time").pack(side="left", padx=(12, 8))

        self.one_time_hour = tk.Spinbox(one_time_input, from_=0, to=23, width=3, format="%02.0f")
        self.one_time_hour.delete(0, tk.END)
        self.one_time_hour.insert(0, default_one_time.strftime("%H"))
        self.one_time_hour.pack(side="left")

        ttk.Label(one_time_input, text=":").pack(side="left", padx=4)

        self.one_time_minute = tk.Spinbox(one_time_input, from_=0, to=59, width=3, format="%02.0f")
        self.one_time_minute.delete(0, tk.END)
        self.one_time_minute.insert(0, default_one_time.strftime("%M"))
        self.one_time_minute.pack(side="left")

        ttk.Button(one_time_input, text="Add One-Time Reminder", command=self.add_one_time_reminder).pack(
            side="left",
            padx=(12, 0),
        )

        ttk.Label(one_time_frame, text="Date format: YYYY-MM-DD", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

    def build_history_tab(self):
        history_frame = ttk.LabelFrame(self.history_tab, text="Taken History", padding=12)
        history_frame.pack(fill="both", expand=True)

        self.history_listbox = tk.Listbox(history_frame, height=16, width=42, exportselection=False)
        self.history_listbox.pack(side="left", fill="both", expand=True)

        history_scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_listbox.yview)
        history_scrollbar.pack(side="left", fill="y")
        self.history_listbox.configure(yscrollcommand=history_scrollbar.set)

        history_actions = ttk.Frame(self.history_tab)
        history_actions.pack(anchor="w", pady=(10, 0))

        ttk.Button(history_actions, text="Clear History", command=self.clear_history).pack(side="left")

    def build_settings_tab(self):
        settings_frame = ttk.LabelFrame(self.settings_tab, text="App Settings", padding=12)
        settings_frame.pack(fill="x")

        ttk.Label(settings_frame, text="Reminder checks run while this app is open.").pack(anchor="w")
        ttk.Label(settings_frame, text="Keep a backup phone or calendar reminder while testing.", style="Muted.TLabel").pack(
            anchor="w",
            pady=(4, 12),
        )
        ttk.Label(settings_frame, text=f"Data file: {DATA_FILE}", style="Muted.TLabel").pack(anchor="w")

        settings_actions = ttk.Frame(settings_frame)
        settings_actions.pack(anchor="w", pady=(12, 0))

        ttk.Button(settings_actions, text="Open Data Folder", command=self.open_data_folder).pack(side="left", padx=(0, 8))
        ttk.Button(settings_actions, text="Save Now", command=self.save_data).pack(side="left")

    def save_data(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps(self.data, indent=2))

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
            elif due <= now:
                reminder_key = f"{today.isoformat()}:{reminder}"

                if reminder_key in self.data.get("reminders_shown", []):
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

        if self.data.get("last_taken") == today:
            status_text = f"Taken today at {self.data.get('last_taken_time', 'unknown time')}"
        elif self.data.get("last_taken_time"):
            status_text = f"Last taken: {self.data['last_taken_time']}"
        else:
            status_text = "Not marked taken today"

        self.status_label.config(text=status_text)

        upcoming_items = self.get_upcoming_items()

        if upcoming_items:
            next_due = upcoming_items[0]["due"]
            when_text = "now" if next_due <= datetime.now() else next_due.strftime("%Y-%m-%d at %H:%M")
            self.next_label.config(text=f"Next reminder: {when_text}")
        else:
            self.next_label.config(text="Next reminder: none")

    def refresh_daily_list(self):
        self.daily_listbox.delete(0, tk.END)

        for reminder in self.data["daily_reminders"]:
            self.daily_listbox.insert(tk.END, reminder)

    def refresh_upcoming_list(self):
        self.upcoming_items = self.get_upcoming_items()

        for item_id in self.upcoming_tree.get_children():
            self.upcoming_tree.delete(item_id)

        for index, item in enumerate(self.upcoming_items[:20]):
            due_text = item["due"].strftime("%Y-%m-%d %H:%M")
            self.upcoming_tree.insert("", tk.END, iid=str(index), values=(due_text, item["kind"]))

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
        selected = self.upcoming_tree.selection()

        if not selected:
            messagebox.showinfo("No Reminder Selected", "Select an upcoming reminder to remove.")
            return

        item = self.upcoming_items[int(selected[0])]

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

    def mark_taken(self):
        now = datetime.now()
        today = now.date().isoformat()

        if self.data.get("last_taken") == today:
            messagebox.showinfo("Already Marked", "You already marked today's pill as taken.")
            return

        taken_time = now.strftime("%Y-%m-%d at %H:%M")
        history = self.get_history()
        history.append(taken_time)

        self.data["last_taken"] = today
        self.data["last_taken_time"] = taken_time
        self.data["history"] = history[-HISTORY_LIMIT:]
        self.data["snoozes"] = []
        self.save_data()
        self.refresh_all()

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
        self.save_data()
        self.refresh_history_list()

    def snooze_reminder(self):
        snooze_time = (datetime.now() + timedelta(minutes=SNOOZE_MINUTES)).replace(second=0, microsecond=0)
        snoozes = self.get_snoozes()
        snoozes.append(snooze_time)
        self.save_snoozes(snoozes)
        self.refresh_all()
        messagebox.showinfo("Snoozed", f"Reminder snoozed until {snooze_time:%H:%M}.")

    def send_mac_notification(self, message):
        try:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{message}" with title "{APP_NAME}"',
                ],
                check=False,
            )
        except FileNotFoundError:
            pass

    def show_reminder_popup(self, reminder_label=None):
        message = "Time to take your birth control pill."
        self.send_mac_notification(message)

        popup = tk.Toplevel(self.root)
        popup.title(APP_NAME)
        popup.geometry("340x190")
        popup.resizable(False, False)

        ttk.Label(popup, text=message, style="Status.TLabel").pack(pady=(20, 8))
        ttk.Label(popup, text=reminder_label or "Test reminder").pack()

        actions = ttk.Frame(popup)
        actions.pack(pady=18)

        if reminder_label:
            ttk.Button(actions, text="Taken", command=lambda: [self.mark_taken(), popup.destroy()]).pack(
                side="left",
                padx=4,
            )
            ttk.Button(actions, text=f"Snooze {SNOOZE_MINUTES} Min", command=lambda: [self.snooze_reminder(), popup.destroy()]).pack(
                side="left",
                padx=4,
            )

        ttk.Button(actions, text="Dismiss", command=popup.destroy).pack(side="left", padx=4)

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

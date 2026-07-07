# Pill Reminder App
# This is a simple pill reminder application that helps users keep track of their medication schedule.
# Keep the app open for the reminder popup to appear at the saved time.

import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
import json
import subprocess
from tkinter import messagebox

LEGACY_DATA_FILE = Path("pill_data.json")
DATA_FILE = Path.home() / ".pill_reminder.json"
SNOOZE_FORMAT = "%Y-%m-%d %H:%M"
ONE_TIME_FORMAT = "%Y-%m-%d %H:%M"
CHECK_INTERVAL_MS = 15000


def load_data():
    if DATA_FILE.exists():
        data_file = DATA_FILE
    elif LEGACY_DATA_FILE.exists():
        data_file = LEGACY_DATA_FILE
    else:
        return {}

    try:
        return json.loads(data_file.read_text())
    except json.JSONDecodeError:
        return {}


def save_data():
    DATA_FILE.write_text(json.dumps(app_data, indent=2))


def is_valid_time(value):
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        return False

    return True


def time_to_minutes(value):
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def parse_one_time_reminder(value):
    return datetime.strptime(value, ONE_TIME_FORMAT)


def get_saved_reminders():
    saved_reminders = app_data.get("reminders")

    if isinstance(saved_reminders, list):
        valid_reminders = [time for time in saved_reminders if is_valid_time(time)]

        if valid_reminders:
            return sorted(set(valid_reminders))

    old_reminder_time = app_data.get("reminder_time", "21:00")

    if is_valid_time(old_reminder_time):
        return [old_reminder_time]

    return ["21:00"]


def get_reminders_text():
    reminders = app_data.get("reminders", ["21:00"])
    return "\n".join(reminders)


def get_valid_snoozes():
    snoozes = app_data.get("snoozes", [])
    valid_snoozes = []

    if not isinstance(snoozes, list):
        return valid_snoozes

    for snooze in snoozes:
        try:
            valid_snoozes.append(datetime.strptime(snooze, SNOOZE_FORMAT))
        except ValueError:
            continue

    return sorted(valid_snoozes)


def save_snoozes(snoozes):
    app_data["snoozes"] = [snooze.strftime(SNOOZE_FORMAT) for snooze in sorted(snoozes)]
    save_data()


def get_valid_one_time_reminders():
    reminders = app_data.get("one_time_reminders", [])
    valid_reminders = []

    if not isinstance(reminders, list):
        return valid_reminders

    for reminder in reminders:
        try:
            valid_reminders.append(parse_one_time_reminder(reminder))
        except ValueError:
            continue

    return sorted(valid_reminders)


def save_one_time_reminders(reminders):
    app_data["one_time_reminders"] = [reminder.strftime(ONE_TIME_FORMAT) for reminder in sorted(reminders)]
    save_data()


def get_upcoming_reminder_items():
    now = datetime.now()
    today = date.today()
    items = []

    for snooze in get_valid_snoozes():
        if snooze >= now:
            items.append((snooze, "Snoozed reminder", snooze.strftime(SNOOZE_FORMAT)))

    for reminder in get_valid_one_time_reminders():
        if reminder >= now:
            items.append((reminder, "One-time reminder", reminder.strftime(ONE_TIME_FORMAT)))

    for reminder in app_data.get("reminders", ["21:00"]):
        hour, minute = reminder.split(":")
        reminder_time = datetime(today.year, today.month, today.day, int(hour), int(minute))

        if app_data.get("last_taken") == today.isoformat() or reminder_time <= now:
            reminder_time += timedelta(days=1)

        items.append((reminder_time, "Daily reminder", reminder))

    return sorted(items, key=lambda item: item[0])


def get_next_reminder_text():
    next_time, reminder_type, _ = get_upcoming_reminder_items()[0]
    today = date.today()
    day_text = "today" if next_time.date() == today else "tomorrow"

    if reminder_type == "Snoozed reminder":
        return f"Next reminder: snoozed until {day_text} at {next_time:%H:%M}"

    return f"Next reminder: {day_text} at {next_time:%H:%M}"


def refresh_reminder_list():
    reminder_listbox.delete(0, tk.END)

    for reminder in app_data.get("reminders", ["21:00"]):
        reminder_listbox.insert(tk.END, reminder)


def get_history_entries():
    history = app_data.get("history", [])

    if not isinstance(history, list):
        return []

    return history


def refresh_history_list():
    history_listbox.delete(0, tk.END)
    history = get_history_entries()

    if not history:
        history_listbox.insert(tk.END, "No pills marked taken yet.")
        return

    for entry in reversed(history):
        history_listbox.insert(tk.END, entry)


def refresh_upcoming_list():
    global upcoming_reminder_items

    upcoming_reminder_items = get_upcoming_reminder_items()
    upcoming_listbox.delete(0, tk.END)

    for reminder_time, reminder_type, _ in upcoming_reminder_items[:12]:
        upcoming_listbox.insert(tk.END, f"{reminder_time:%Y-%m-%d %H:%M} - {reminder_type}")


def update_next_reminder_label():
    next_reminder_label.config(text=get_next_reminder_text())

    if "upcoming_listbox" in globals():
        refresh_upcoming_list()


def add_reminder_time(reminder_time):
    reminders = app_data.get("reminders", [])

    if reminder_time in reminders:
        return False

    reminders.append(reminder_time)
    app_data["reminders"] = sorted(reminders)
    app_data["reminder_time"] = reminder_time
    save_data()
    refresh_reminder_list()
    update_next_reminder_label()
    return True


def send_mac_notification(message):
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "Pill Reminder"',
            ],
            check=False,
        )
    except FileNotFoundError:
        pass


def show_reminder(reminder_time=None):
    message = "Time to take your birth control pill."
    send_mac_notification(message)

    popup = tk.Toplevel(window)
    popup.title("Pill Reminder")
    popup.geometry("320x180")
    popup.resizable(False, False)

    tk.Label(popup, text=message, font=("Helvetica", 14, "bold")).pack(pady=(18, 6))

    if reminder_time:
        tk.Label(popup, text=f"Reminder time: {reminder_time}").pack(pady=(0, 14))
    else:
        tk.Label(popup, text="Test reminder").pack(pady=(0, 14))

    button_frame = tk.Frame(popup)
    button_frame.pack(pady=8)

    if reminder_time:
        tk.Button(button_frame, text="Taken", command=lambda: [mark_taken(), popup.destroy()]).pack(side="left", padx=4)
        tk.Button(button_frame, text="Snooze 10 Min", command=lambda: [snooze_reminder(), popup.destroy()]).pack(
            side="left",
            padx=4,
        )

    tk.Button(button_frame, text="Dismiss", command=popup.destroy).pack(side="left", padx=4)


app_data = load_data()
app_data["reminders"] = get_saved_reminders()
reminder_time = app_data["reminders"][0]
reminder_hour, reminder_minute = reminder_time.split(":")
default_one_time = datetime.now() + timedelta(hours=1)
last_taken = app_data.get("last_taken")
last_taken_time = app_data.get("last_taken_time")

window = tk.Tk()
window.title("Pill Reminder")
window.geometry("760x900")

title_label = tk.Label(window, text="Pill Reminder", font=("Helvetica", 20, "bold"))
title_label.pack(pady=(20, 8))

instructions_label = tk.Label(window, text="Add your pill reminder times and mark the pill when you take it.")
instructions_label.pack(pady=(0, 16))

open_note_label = tk.Label(window, text="Keep this app open so reminders can appear.", fg="#555555")
open_note_label.pack(pady=(0, 10))

time_frame = tk.Frame(window)
time_frame.pack(pady=4)

time_label = tk.Label(time_frame, text="Add reminder:")
time_label.pack(side="left", padx=(0, 8))

daily_label = tk.Label(time_frame, text="Daily")
daily_label.pack(side="left", padx=(0, 8))

hour_spinbox = tk.Spinbox(time_frame, from_=0, to=23, width=3, format="%02.0f")
hour_spinbox.delete(0, tk.END)
hour_spinbox.insert(0, reminder_hour)
hour_spinbox.pack(side="left")

time_separator = tk.Label(time_frame, text=":")
time_separator.pack(side="left", padx=4)

minute_spinbox = tk.Spinbox(time_frame, from_=0, to=59, width=3, format="%02.0f")
minute_spinbox.delete(0, tk.END)
minute_spinbox.insert(0, reminder_minute)
minute_spinbox.pack(side="left")

tip_label = tk.Label(window, text="Daily reminders repeat every day at the selected time.")
tip_label.pack(pady=(8, 10))

one_time_frame = tk.Frame(window)
one_time_frame.pack(pady=4)

one_time_label = tk.Label(one_time_frame, text="One-time reminder:")
one_time_label.pack(side="left", padx=(0, 8))

one_time_date_entry = tk.Entry(one_time_frame, width=11)
one_time_date_entry.insert(0, default_one_time.strftime("%Y-%m-%d"))
one_time_date_entry.pack(side="left")

one_time_hour_spinbox = tk.Spinbox(one_time_frame, from_=0, to=23, width=3, format="%02.0f")
one_time_hour_spinbox.delete(0, tk.END)
one_time_hour_spinbox.insert(0, default_one_time.strftime("%H"))
one_time_hour_spinbox.pack(side="left", padx=(8, 0))

one_time_separator = tk.Label(one_time_frame, text=":")
one_time_separator.pack(side="left", padx=4)

one_time_minute_spinbox = tk.Spinbox(one_time_frame, from_=0, to=59, width=3, format="%02.0f")
one_time_minute_spinbox.delete(0, tk.END)
one_time_minute_spinbox.insert(0, default_one_time.strftime("%M"))
one_time_minute_spinbox.pack(side="left")

one_time_tip_label = tk.Label(window, text="Use YYYY-MM-DD for one-time reminders, then choose any time.")
one_time_tip_label.pack(pady=(8, 10))

one_time_actions_frame = tk.Frame(window)
one_time_actions_frame.pack(pady=(0, 12))

reminders_frame = tk.Frame(window)
reminders_frame.pack(pady=(0, 14))

reminders_title = tk.Label(reminders_frame, text="Daily reminder times")
reminders_title.pack(anchor="w")

reminder_listbox = tk.Listbox(reminders_frame, height=4, width=18)
reminder_listbox.pack(side="left")

reminder_scrollbar = tk.Scrollbar(reminders_frame, orient="vertical", command=reminder_listbox.yview)
reminder_scrollbar.pack(side="left", fill="y")
reminder_listbox.config(yscrollcommand=reminder_scrollbar.set)
refresh_reminder_list()

reminder_actions_frame = tk.Frame(window)
reminder_actions_frame.pack(pady=(0, 12))

next_reminder_label = tk.Label(window, text=get_next_reminder_text())
next_reminder_label.pack(pady=(0, 10))

upcoming_frame = tk.Frame(window)
upcoming_frame.pack(pady=(0, 14))

upcoming_title = tk.Label(upcoming_frame, text="Upcoming reminders")
upcoming_title.pack(anchor="w")

upcoming_listbox = tk.Listbox(upcoming_frame, height=7, width=48)
upcoming_listbox.pack(side="left")

upcoming_scrollbar = tk.Scrollbar(upcoming_frame, orient="vertical", command=upcoming_listbox.yview)
upcoming_scrollbar.pack(side="left", fill="y")
upcoming_listbox.config(yscrollcommand=upcoming_scrollbar.set)
refresh_upcoming_list()

upcoming_actions_frame = tk.Frame(window)
upcoming_actions_frame.pack(pady=(0, 12))

if last_taken == date.today().isoformat():
    status_text = f"Status: taken today at {last_taken_time}"
elif last_taken_time:
    status_text = f"Last taken: {last_taken_time}"
else:
    status_text = "Status: not taken today"

status_label = tk.Label(window, text=status_text)
status_label.pack(pady=6)

today_actions_frame = tk.Frame(window)
today_actions_frame.pack(pady=(0, 10))

taken_history_frame = tk.Frame(window)
taken_history_frame.pack(pady=(8, 12))

taken_history_title = tk.Label(taken_history_frame, text="Taken history")
taken_history_title.pack(anchor="w")

history_listbox = tk.Listbox(taken_history_frame, height=7, width=30)
history_listbox.pack(side="left")

history_scrollbar = tk.Scrollbar(taken_history_frame, orient="vertical", command=history_listbox.yview)
history_scrollbar.pack(side="left", fill="y")
history_listbox.config(yscrollcommand=history_scrollbar.set)
refresh_history_list()

tool_actions_frame = tk.Frame(window)
tool_actions_frame.pack(pady=(0, 10))


def add_new_reminder():
    hour = hour_spinbox.get().strip().zfill(2)
    minute = minute_spinbox.get().strip().zfill(2)
    reminder_time = f"{hour}:{minute}"

    if not is_valid_time(reminder_time):
        messagebox.showerror("Invalid time", "Please enter time as HH:MM, like 21:00.")
        return

    if not add_reminder_time(reminder_time):
        messagebox.showinfo("Already Added", f"{reminder_time} is already in your reminders.")
        return

    messagebox.showinfo("Added", f"New reminder added for {reminder_time}.")


def add_one_time_reminder():
    date_text = one_time_date_entry.get().strip()
    hour = one_time_hour_spinbox.get().strip().zfill(2)
    minute = one_time_minute_spinbox.get().strip().zfill(2)
    reminder_text = f"{date_text} {hour}:{minute}"

    try:
        reminder_datetime = parse_one_time_reminder(reminder_text)
    except ValueError:
        messagebox.showerror("Invalid date/time", "Use a date like 2026-07-07 and a 24-hour time.")
        return

    if reminder_datetime <= datetime.now():
        messagebox.showerror("Past reminder", "Choose a future date and time.")
        return

    reminders = get_valid_one_time_reminders()

    if reminder_datetime in reminders:
        messagebox.showinfo("Already Added", "That one-time reminder already exists.")
        return

    reminders.append(reminder_datetime)
    save_one_time_reminders(reminders)
    update_next_reminder_label()
    messagebox.showinfo("Added", f"One-time reminder added for {reminder_datetime:%Y-%m-%d at %H:%M}.")


def remove_selected_reminder():
    selected_indexes = reminder_listbox.curselection()

    if not selected_indexes:
        messagebox.showinfo("No Reminder Selected", "Select a reminder time to remove.")
        return

    selected_time = reminder_listbox.get(selected_indexes[0])
    reminders = app_data.get("reminders", [])

    if len(reminders) == 1:
        messagebox.showinfo("Keep One Reminder", "You need at least one reminder time.")
        return

    app_data["reminders"] = [reminder for reminder in reminders if reminder != selected_time]
    app_data["reminder_time"] = app_data["reminders"][0]
    save_data()
    refresh_reminder_list()
    update_next_reminder_label()
    messagebox.showinfo("Removed", f"Removed reminder for {selected_time}.")


def remove_selected_upcoming_reminder():
    selected_indexes = upcoming_listbox.curselection()

    if not selected_indexes:
        messagebox.showinfo("No Reminder Selected", "Select an upcoming reminder to remove.")
        return

    _, reminder_type, reminder_id = upcoming_reminder_items[selected_indexes[0]]

    if reminder_type == "One-time reminder":
        reminders = [reminder for reminder in get_valid_one_time_reminders() if reminder.strftime(ONE_TIME_FORMAT) != reminder_id]
        save_one_time_reminders(reminders)
        update_next_reminder_label()
        messagebox.showinfo("Removed", "Removed the selected one-time reminder.")
        return

    if reminder_type == "Snoozed reminder":
        snoozes = [snooze for snooze in get_valid_snoozes() if snooze.strftime(SNOOZE_FORMAT) != reminder_id]
        save_snoozes(snoozes)
        update_next_reminder_label()
        messagebox.showinfo("Removed", "Removed the selected snoozed reminder.")
        return

    reminders = app_data.get("reminders", [])

    if len(reminders) == 1:
        messagebox.showinfo("Keep One Reminder", "You need at least one daily reminder time.")
        return

    app_data["reminders"] = [reminder for reminder in reminders if reminder != reminder_id]
    app_data["reminder_time"] = app_data["reminders"][0]
    save_data()
    refresh_reminder_list()
    update_next_reminder_label()
    messagebox.showinfo("Removed", "Removed the selected daily reminder.")


def mark_taken():
    time_taken = datetime.now()
    today = time_taken.date().isoformat()
    formatted_time = time_taken.strftime("%Y-%m-%d at %H:%M")

    if app_data.get("last_taken") == today:
        messagebox.showinfo("Already Marked", "You already marked today's pill as taken.")
        return

    app_data["last_taken"] = today
    app_data["last_taken_time"] = formatted_time
    app_data["snoozes"] = []
    history = get_history_entries()
    history.append(formatted_time)
    app_data["history"] = history[-60:]
    save_data()
    status_label.config(text=f"Taken: {formatted_time}")
    refresh_history_list()
    update_next_reminder_label()


def reset_today():
    app_data.pop("last_taken", None)
    app_data.pop("last_taken_time", None)
    app_data.pop("reminder_shown_for", None)
    app_data["reminders_shown"] = []
    app_data["snoozes"] = []
    save_data()
    status_label.config(text="Status: not taken today")
    update_next_reminder_label()


def clear_history():
    app_data["history"] = []
    save_data()
    refresh_history_list()
    messagebox.showinfo("History Cleared", "Recent taken history has been cleared.")


def snooze_reminder():
    snooze_time = datetime.now() + timedelta(minutes=10)
    snooze_time = snooze_time.replace(second=0, microsecond=0)
    reminder_time = snooze_time.strftime("%H:%M")
    hour, minute = reminder_time.split(":")
    snoozes = get_valid_snoozes()
    snoozes.append(snooze_time)
    save_snoozes(snoozes)
    hour_spinbox.delete(0, tk.END)
    hour_spinbox.insert(0, hour)
    minute_spinbox.delete(0, tk.END)
    minute_spinbox.insert(0, minute)
    update_next_reminder_label()
    messagebox.showinfo("Snoozed", f"Reminder snoozed until {reminder_time}.")


def check_reminder():
    now = datetime.now()
    today = now.date().isoformat()
    current_minutes = now.hour * 60 + now.minute

    already_taken = app_data.get("last_taken") == today
    reminders_shown = app_data.get("reminders_shown", [])

    if not already_taken:
        snoozes = get_valid_snoozes()
        due_snoozes = [snooze for snooze in snoozes if snooze <= now]

        if due_snoozes:
            due_snooze = due_snoozes[0]
            save_snoozes([snooze for snooze in snoozes if snooze != due_snooze])
            update_next_reminder_label()
            show_reminder(due_snooze.strftime("%H:%M"))
            window.after(CHECK_INTERVAL_MS, check_reminder)
            return

        one_time_reminders = get_valid_one_time_reminders()
        due_one_time_reminders = [reminder for reminder in one_time_reminders if reminder <= now]

        if due_one_time_reminders:
            due_reminder = due_one_time_reminders[0]
            save_one_time_reminders([reminder for reminder in one_time_reminders if reminder != due_reminder])
            update_next_reminder_label()
            show_reminder(due_reminder.strftime("%H:%M"))
            window.after(CHECK_INTERVAL_MS, check_reminder)
            return

        for reminder in app_data.get("reminders", ["21:00"]):
            reminder_key = f"{today}:{reminder}"

            if time_to_minutes(reminder) <= current_minutes and reminder_key not in reminders_shown:
                reminders_shown.append(reminder_key)
                app_data["reminders_shown"] = reminders_shown[-20:]
                save_data()
                update_next_reminder_label()
                show_reminder(reminder)
                window.after(CHECK_INTERVAL_MS, check_reminder)
                return

    update_next_reminder_label()

    window.after(CHECK_INTERVAL_MS, check_reminder)


one_time_button = tk.Button(one_time_actions_frame, text="Add One-Time Reminder", command=add_one_time_reminder)
one_time_button.pack(side="left", padx=4)

save_button = tk.Button(reminder_actions_frame, text="Add Daily Reminder", command=add_new_reminder)
save_button.pack(side="left", padx=4)

remove_button = tk.Button(reminder_actions_frame, text="Remove Selected Daily Reminder", command=remove_selected_reminder)
remove_button.pack(side="left", padx=4)

remove_upcoming_button = tk.Button(
    upcoming_actions_frame,
    text="Remove Selected Upcoming Reminder",
    command=remove_selected_upcoming_reminder,
)
remove_upcoming_button.pack(side="left", padx=4)

taken_button = tk.Button(today_actions_frame, text="Taken Today", command=mark_taken)
taken_button.pack(side="left", padx=4)

reset_button = tk.Button(today_actions_frame, text="Reset Today", command=reset_today)
reset_button.pack(side="left", padx=4)

clear_history_button = tk.Button(tool_actions_frame, text="Clear History", command=clear_history)
clear_history_button.pack(side="left", padx=4)

test_button = tk.Button(tool_actions_frame, text="Test Notification", command=show_reminder)
test_button.pack(side="left", padx=4)

check_reminder()

window.mainloop()

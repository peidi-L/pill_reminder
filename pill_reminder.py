# Pill Reminder App
# This is a simple pill reminder application that helps users keep track of their medication schedule.
# Keep the app open for the reminder popup to appear at the saved time.

import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
import json
import subprocess
from tkinter import messagebox

DATA_FILE = Path("pill_data.json")


def load_data():
    if not DATA_FILE.exists():
        return {}

    try:
        return json.loads(DATA_FILE.read_text())
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
    return "Reminder times: " + ", ".join(reminders)


def add_reminder_time(reminder_time):
    reminders = app_data.get("reminders", [])

    if reminder_time in reminders:
        return False

    reminders.append(reminder_time)
    app_data["reminders"] = sorted(reminders)
    app_data["reminder_time"] = reminder_time
    save_data()
    reminder_label.config(text=get_reminders_text())
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
last_taken = app_data.get("last_taken")
last_taken_time = app_data.get("last_taken_time")

window = tk.Tk()
window.title("Pill Reminder")
window.geometry("460x500")

title_label = tk.Label(window, text="Pill Reminder", font=("Helvetica", 20, "bold"))
title_label.pack(pady=(20, 8))

instructions_label = tk.Label(window, text="Set your reminder time and mark when you take it.")
instructions_label.pack(pady=(0, 16))

time_frame = tk.Frame(window)
time_frame.pack(pady=4)

time_label = tk.Label(time_frame, text="Reminder time:")
time_label.pack(side="left", padx=(0, 8))

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

reminder_label = tk.Label(window, text=get_reminders_text())
reminder_label.pack(pady=(8, 16))

if last_taken == date.today().isoformat():
    status_text = f"Status: taken today at {last_taken_time}"
elif last_taken_time:
    status_text = f"Last taken: {last_taken_time}"
else:
    status_text = "Status: not taken today"

status_label = tk.Label(window, text=status_text)
status_label.pack(pady=6)

tip_label = tk.Label(window, text="Choose a 24-hour time, like 09:00 or 21:30.")
tip_label.pack(pady=(0, 10))


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


def mark_taken():
    time_taken = datetime.now()
    today = time_taken.date().isoformat()
    formatted_time = time_taken.strftime("%Y-%m-%d at %H:%M")

    if app_data.get("last_taken") == today:
        messagebox.showinfo("Already Marked", "You already marked today's pill as taken.")
        return

    app_data["last_taken"] = today
    app_data["last_taken_time"] = formatted_time
    history = app_data.get("history", [])
    history.append(formatted_time)
    app_data["history"] = history[-5:]
    save_data()
    status_label.config(text=f"Taken: {formatted_time}")
    history_label.config(text=get_history_text())


def reset_today():
    app_data.pop("last_taken", None)
    app_data.pop("last_taken_time", None)
    app_data.pop("reminder_shown_for", None)
    app_data["reminders_shown"] = []
    save_data()
    status_label.config(text="Status: not taken today")


def clear_history():
    app_data["history"] = []
    save_data()
    history_label.config(text=get_history_text())
    messagebox.showinfo("History Cleared", "Recent taken history has been cleared.")


def snooze_reminder():
    snooze_time = datetime.now() + timedelta(minutes=10)
    reminder_time = snooze_time.strftime("%H:%M")
    hour, minute = reminder_time.split(":")
    add_reminder_time(reminder_time)
    hour_spinbox.delete(0, tk.END)
    hour_spinbox.insert(0, hour)
    minute_spinbox.delete(0, tk.END)
    minute_spinbox.insert(0, minute)
    messagebox.showinfo("Snoozed", f"Reminder snoozed until {reminder_time}.")


def get_history_text():
    history = app_data.get("history", [])

    if not history:
        return "Recent history: none yet"

    return "Recent history:\n" + "\n".join(history[-5:])


def check_reminder():
    now = datetime.now()
    today = now.date().isoformat()
    current_time = now.strftime("%H:%M")

    already_taken = app_data.get("last_taken") == today
    reminder_key = f"{today}:{current_time}"
    reminders_shown = app_data.get("reminders_shown", [])

    if current_time in app_data.get("reminders", ["21:00"]) and not already_taken and reminder_key not in reminders_shown:
        reminders_shown.append(reminder_key)
        app_data["reminders_shown"] = reminders_shown[-20:]
        save_data()
        show_reminder(current_time)

    window.after(30000, check_reminder)


save_button = tk.Button(window, text="Add Reminder", command=add_new_reminder)
save_button.pack(pady=4)

taken_button = tk.Button(window, text="Taken Today", command=mark_taken)
taken_button.pack(pady=8)

reset_button = tk.Button(window, text="Reset Today", command=reset_today)
reset_button.pack(pady=4)

clear_history_button = tk.Button(window, text="Clear History", command=clear_history)
clear_history_button.pack(pady=4)

test_button = tk.Button(window, text="Test Reminder", command=show_reminder)
test_button.pack(pady=4)

history_label = tk.Label(window, text=get_history_text(), justify="left")
history_label.pack(pady=(8, 0))

check_reminder()

window.mainloop()

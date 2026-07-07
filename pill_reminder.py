# Pill Reminder App
# This is a simple pill reminder application that helps users keep track of their medication schedule.
# Keep the app open for the reminder popup to appear at the saved time.

import tkinter as tk
from datetime import date, datetime
from pathlib import Path
import json
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


app_data = load_data()
reminder_time = app_data.get("reminder_time", "21:00")
last_taken = app_data.get("last_taken")
last_taken_time = app_data.get("last_taken_time")

window = tk.Tk()
window.title("Pill Reminder")
window.geometry("440x360")

title_label = tk.Label(window, text="Pill Reminder", font=("Helvetica", 20, "bold"))
title_label.pack(pady=(20, 8))

instructions_label = tk.Label(window, text="Set your reminder time and mark when you take it.")
instructions_label.pack(pady=(0, 16))

time_frame = tk.Frame(window)
time_frame.pack(pady=4)

time_label = tk.Label(time_frame, text="Reminder time:")
time_label.pack(side="left", padx=(0, 8))

time_entry = tk.Entry(time_frame, width=8)
time_entry.insert(0, reminder_time)
time_entry.pack(side="left")

reminder_label = tk.Label(window, text=f"Next reminder: {reminder_time}")
reminder_label.pack(pady=(8, 16))

if last_taken == date.today().isoformat():
    status_text = f"Status: taken today at {last_taken_time}"
elif last_taken_time:
    status_text = f"Last taken: {last_taken_time}"
else:
    status_text = "Status: not taken today"

status_label = tk.Label(window, text=status_text)
status_label.pack(pady=6)

tip_label = tk.Label(window, text="Use 24-hour time, like 09:00 or 21:30.")
tip_label.pack(pady=(0, 10))


def save_reminder_time():
    reminder_time = time_entry.get().strip()

    if not is_valid_time(reminder_time):
        messagebox.showerror("Invalid time", "Please enter time as HH:MM, like 21:00.")
        return

    app_data["reminder_time"] = reminder_time
    save_data()
    reminder_label.config(text=f"Next reminder: {reminder_time}")
    messagebox.showinfo("Saved", f"Reminder time saved for {reminder_time}.")


def mark_taken():
    time_taken = datetime.now()
    app_data["last_taken"] = time_taken.date().isoformat()
    app_data["last_taken_time"] = time_taken.strftime("%Y-%m-%d at %H:%M")
    save_data()
    status_label.config(text=f"Taken: {time_taken:%Y-%m-%d at %H:%M}")


def reset_today():
    app_data.pop("last_taken", None)
    app_data.pop("last_taken_time", None)
    app_data.pop("reminder_shown_for", None)
    save_data()
    status_label.config(text="Status: not taken today")


def check_reminder():
    now = datetime.now()
    today = now.date().isoformat()
    current_time = now.strftime("%H:%M")

    already_taken = app_data.get("last_taken") == today
    already_reminded = app_data.get("reminder_shown_for") == today

    if current_time == app_data.get("reminder_time", "21:00") and not already_taken and not already_reminded:
        app_data["reminder_shown_for"] = today
        save_data()
        messagebox.showinfo("Pill Reminder", "Time to take your birth control pill.")

    window.after(30000, check_reminder)


save_button = tk.Button(window, text="Save Reminder Time", command=save_reminder_time)
save_button.pack(pady=4)

taken_button = tk.Button(window, text="Taken Today", command=mark_taken)
taken_button.pack(pady=8)

reset_button = tk.Button(window, text="Reset Today", command=reset_today)
reset_button.pack(pady=4)

check_reminder()

window.mainloop()

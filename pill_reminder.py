# Pill Reminder App
# This is a simple pill reminder application that helps users keep track of their medication schedule. The app allows users to set reminders for taking their pills at specific times and provides notifications to ensure they don't miss a dose.

import tkinter as tk
from datetime import date, datetime
from pathlib import Path
import json

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


app_data = load_data()
reminder_time = app_data.get("reminder_time", "21:00")
last_taken = app_data.get("last_taken")

window = tk.Tk()
window.title("Pill Reminder")
window.geometry("420x320")

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
    status_text = "Status: taken today"
elif last_taken:
    status_text = f"Last taken: {last_taken}"
else:
    status_text = "Status: not taken today"

status_label = tk.Label(window, text=status_text)
status_label.pack(pady=6)


def save_reminder_time():
    reminder_time = time_entry.get()
    app_data["reminder_time"] = reminder_time
    save_data()
    reminder_label.config(text=f"Next reminder: {reminder_time}")


def mark_taken():
    time_taken = datetime.now()
    app_data["last_taken"] = time_taken.date().isoformat()
    app_data["last_taken_time"] = time_taken.strftime("%Y-%m-%d at %H:%M")
    save_data()
    status_label.config(text=f"Taken: {time_taken:%Y-%m-%d at %H:%M}")


save_button = tk.Button(window, text="Save Reminder Time", command=save_reminder_time)
save_button.pack(pady=4)

taken_button = tk.Button(window, text="Taken Today", command=mark_taken)
taken_button.pack(pady=8)

window.mainloop()

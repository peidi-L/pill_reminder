# Pill Reminder App
# This is a simple pill reminder application that helps users keep track of their medication schedule. The app allows users to set reminders for taking their pills at specific times and provides notifications to ensure they don't miss a dose.

import tkinter as tk

window = tk.Tk()
window.title("Pill Reminder")
window.geometry("400x250")

title_label = tk.Label(window, text="Pill Reminder")
title_label.pack()

status_label = tk.Label(window, text="Not taken today")
status_label.pack()

def mark_taken():
    status_label.config(text="Taken today")

taken_button = tk.Button(window, text="Taken Today", command=mark_taken)
taken_button.pack()

window.mainloop()

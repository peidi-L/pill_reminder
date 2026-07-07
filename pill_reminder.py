# Pill Reminder App
# This is a simple pill reminder application that helps users keep track of their medication schedule. The app allows users to set reminders for taking their pills at specific times and provides notifications to ensure they don't miss a dose.

import tkinter as tk

window = tk.Tk()
window.title("Pill Reminder")
window.geometry("400x250")

title_label = tk.Label(window, text="Pill Reminder")
title_label.pack()

window.mainloop()

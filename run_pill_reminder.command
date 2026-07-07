#!/bin/zsh

cd "$(dirname "$0")"
export TK_SILENCE_DEPRECATION=1
exec /usr/bin/python3 pill_reminder.py

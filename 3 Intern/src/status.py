# status.py

_callback = print  # Default: terminal output

def set_callback(func):
    global _callback
    _callback = func

def update(message):
    print(message)  # Always terminal
    if _callback:
        _callback(message)  # GUI or other display

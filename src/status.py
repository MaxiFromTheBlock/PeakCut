# status.py

_callback = print  # Standardmäßig Terminalausgabe

def set_callback(func):
    global _callback
    _callback = func

def update(message):
    print(message)  # Immer Terminal
    if _callback:
        _callback(message)  # GUI oder andere Anzeige

import tkinter as tk
from PIL import Image, ImageTk
import os

from sync import run_sync
from peaks import run_peak_analysis, get_peaks, play_current_peak, go_back, go_forward, repeat_current, switch_mode, ignore_current_peak, stop_playback
from export import run_export
from status import set_callback

info_label = None
is_playing = False  # State for Play/Stop toggle

def update_info(message):
    print(message)
    if info_label:
        info_label.config(text=message)

def on_back():
    go_back()

def on_forward():
    go_forward()

def on_repeat():
    repeat_current()

def on_switch_mode():
    switch_mode()

def on_ignore():
    ignore_current_peak()

def on_play_stop():
    global is_playing
    if is_playing:
        stop_playback()
        update_info("⏹ Playback stopped.")
        play_button.config(text="Play")
        is_playing = False
    else:
        play_current_peak()
        play_button.config(text="Stop")
        is_playing = True

def start_gui():
    global info_label, play_button

    root = tk.Tk()
    root.title("PeakCut V3")
    root.geometry("1050x250")
    root.configure(bg="#0A1D3D")

    logo_path = os.path.join("assets", "pictures", "peakcut_logo.png")
    if os.path.exists(logo_path):
        logo_img = Image.open(logo_path)
        logo_img = logo_img.resize((150, 150), Image.Resampling.LANCZOS)
        logo_photo = ImageTk.PhotoImage(logo_img)
        logo_label = tk.Label(root, image=logo_photo, bg="#0A1D3D")
        logo_label.image = logo_photo
        logo_label.place(x=20, y=20)
    else:
        print("⚠ Logo not found")

    info_frame = tk.Frame(root, bg="#1B2A4E", width=600, height=150)
    info_frame.place(x=200, y=20)
    info_label = tk.Label(info_frame, text="WELCOME TO PEAKCUT V3", font=("Arial", 14), fg="white", bg="#1B2A4E")
    info_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    set_callback(update_info)

    button_frame = tk.Frame(root, bg="#0A1D3D")
    button_frame.place(x=200, y=200)

    tk.Button(button_frame, text="Back", command=on_back).grid(row=0, column=0, padx=5, pady=5)
    tk.Button(button_frame, text="Next", command=on_forward).grid(row=0, column=1, padx=5, pady=5)
    tk.Button(button_frame, text="Repeat", command=on_repeat).grid(row=0, column=2, padx=5, pady=5)
    tk.Button(button_frame, text="Switch", command=on_switch_mode).grid(row=0, column=3, padx=5, pady=5)
    play_button = tk.Button(button_frame, text="Play", command=on_play_stop)
    play_button.grid(row=0, column=4, padx=5, pady=5)
    tk.Button(button_frame, text="Ignore", command=on_ignore).grid(row=0, column=5, padx=5, pady=5)

    right_frame = tk.Frame(root, bg="#0A1D3D")
    right_frame.place(x=850, y=30)

    tk.Button(right_frame, text="Sync", command=run_sync).pack(padx=5, pady=5)

    def custom_peak_analysis():
        run_peak_analysis()
        update_info("✅ Analysis complete. Press Play")

    tk.Button(right_frame, text="Analyze Peaks", command=custom_peak_analysis).pack(padx=5, pady=5)
    tk.Button(right_frame, text="Export", command=run_export).pack(padx=5, pady=5)

    root.mainloop()

import tkinter as tk
from tkinter import scrolledtext
from PIL import Image, ImageTk
import os

from utils import ASSETS_DIR
from sync import run_sync
from peaks import run_peak_analysis, get_peaks, play_current_peak, go_back, go_forward, repeat_current, switch_mode, ignore_current_peak, stop_playback
from export import run_export
from screenshots import extract_screenshots
from status import set_callback

status_text = None
is_playing = False
play_button = None


def stop_if_playing():
    """Stop playback if currently playing."""
    global is_playing
    if is_playing:
        stop_playback()
        play_button.config(text="Play")
        is_playing = False


def update_status(message):
    """Add message to status display."""
    if status_text:
        status_text.config(state=tk.NORMAL)
        status_text.insert(tk.END, message + "\n")
        status_text.see(tk.END)  # Auto-scroll to bottom
        status_text.config(state=tk.DISABLED)
        status_text.update()  # Force UI update


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
        update_status("⏹ Playback stopped.")
        play_button.config(text="Play")
        is_playing = False
    else:
        play_current_peak()
        play_button.config(text="Stop")
        is_playing = True


def on_analyze():
    """Run sync (if videos present) and peak analysis."""
    stop_if_playing()
    run_sync()
    run_peak_analysis()
    update_status("✅ Analysis complete. Press Play")


def on_export():
    """Export audio with peaks."""
    stop_if_playing()
    run_export()


def on_screenshots():
    """Extract screenshots from videos."""
    stop_if_playing()
    extract_screenshots()


def start_gui():
    global status_text, play_button

    root = tk.Tk()
    root.title("PeakCut (Legacy)")
    root.geometry("1050x250")
    root.configure(bg="#0A1D3D")

    # Logo
    logo_path = os.path.join(ASSETS_DIR, "pictures", "peakcut_logo.png")
    if os.path.exists(logo_path):
        logo_img = Image.open(logo_path)
        logo_img = logo_img.resize((150, 150), Image.Resampling.LANCZOS)
        logo_photo = ImageTk.PhotoImage(logo_img)
        logo_label = tk.Label(root, image=logo_photo, bg="#0A1D3D")
        logo_label.image = logo_photo
        logo_label.place(x=20, y=20)
    else:
        print("⚠ Logo not found")

    # Status display (scrollable)
    status_text = scrolledtext.ScrolledText(
        root,
        width=70,
        height=8,
        font=("Arial", 11),
        bg="#1B2A4E",
        fg="white",
        state=tk.DISABLED,
        wrap=tk.WORD
    )
    status_text.place(x=200, y=20)

    set_callback(update_status)
    update_status("WELCOME TO PEAKCUT")
    update_status("─" * 50)
    update_status("1. Put files in '1 Material' folder")
    update_status("2. Click 'Analyze' to detect peaks")
    update_status("3. Use Play/Next/Back to review")
    update_status("4. Click 'Export' when ready")
    update_status("─" * 50)

    # Playback controls
    button_frame = tk.Frame(root, bg="#0A1D3D")
    button_frame.place(x=200, y=200)

    tk.Button(button_frame, text="Back", command=on_back).grid(row=0, column=0, padx=5, pady=5)
    tk.Button(button_frame, text="Next", command=on_forward).grid(row=0, column=1, padx=5, pady=5)
    tk.Button(button_frame, text="Repeat", command=on_repeat).grid(row=0, column=2, padx=5, pady=5)
    tk.Button(button_frame, text="Switch", command=on_switch_mode).grid(row=0, column=3, padx=5, pady=5)
    play_button = tk.Button(button_frame, text="Play", command=on_play_stop)
    play_button.grid(row=0, column=4, padx=5, pady=5)
    tk.Button(button_frame, text="Ignore", command=on_ignore).grid(row=0, column=5, padx=5, pady=5)

    # Main action buttons
    right_frame = tk.Frame(root, bg="#0A1D3D")
    right_frame.place(x=850, y=30)

    tk.Button(right_frame, text="Analyze", command=on_analyze, width=10).pack(padx=5, pady=10)
    tk.Button(right_frame, text="Export", command=on_export, width=10).pack(padx=5, pady=10)
    tk.Button(right_frame, text="Screenshots", command=on_screenshots, width=10).pack(padx=5, pady=10)

    root.mainloop()

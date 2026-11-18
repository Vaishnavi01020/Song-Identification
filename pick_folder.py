"""Open the Windows folder chooser (File Explorer style) so you don't have to type a path."""
from pathlib import Path


def pick_folder(title="Choose a folder", start_dir=None):
    """Returns the chosen folder as a Path, or None if you close the window.
    If the chooser cannot open (no tkinter / no display), asks for the path in the terminal."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return _ask_in_terminal(title)

    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)  # show the window in front of the terminal
        chosen = filedialog.askdirectory(title=title, initialdir=start_dir or str(Path.home()), mustexist=False)
        root.destroy()
    except tk.TclError:
        return _ask_in_terminal(title)
    return Path(chosen) if chosen else None


def _ask_in_terminal(title):
    text = input(f"{title} (type the folder path): ").strip().strip('"').strip("'")
    return Path(text) if text else None
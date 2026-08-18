#!/usr/bin/env python3
import sys
import os
import json
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdl3_gamepad import SDL3Gamepad, BUTTON_NAMES, AXIS_NAMES

try:
    from evdev import ecodes as e
except ImportError:
    print("The 'evdev' module is required: pip install evdev --break-system-packages")
    sys.exit(1)

CONFIG_PATH = os.path.expanduser("~/.config/sc2_mapper/config.json")

DEFAULT_CONFIG = {
    "BUTTON_MAP": {
        "SOUTH": "KEY_F11", "EAST": "KEY_F10", "WEST": "KEY_F12", "NORTH": "KEY_F9",
        "BACK": "KEY_F6", "START": "KEY_F5", "GUIDE": "",
        "LEFT_STICK": "KEY_LEFTSHIFT", "RIGHT_STICK": "BTN_RIGHT",
        "LEFT_SHOULDER": "KEY_F7", "RIGHT_SHOULDER": "KEY_F8",
        "DPAD_UP": "KEY_F1", "DPAD_DOWN": "KEY_F3", "DPAD_LEFT": "KEY_F4", "DPAD_RIGHT": "KEY_F2",
        "LEFT_PADDLE1": "KEY_G", "RIGHT_PADDLE1": "KEY_M",
        "LEFT_PADDLE2": "KEY_TAB", "RIGHT_PADDLE2": "KEY_F",
        "TOUCHPAD": "",
    },
    "LEFT_STICK_MODE": "wasd",
    "LEFT_STICK_KEYS": ["KEY_W", "KEY_S", "KEY_A", "KEY_D"],
    "RIGHT_STICK_MODE": "mouse",
    "RIGHT_STICK_MOUSE_SENSITIVITY": 18,
    "TRIGGER_MAP": {
        "LEFT_TRIGGER": ["KEY_LEFTSHIFT", 8000],
        "RIGHT_TRIGGER": ["KEY_LEFTCTRL", 8000],
    },
    "TOUCHPAD_ENABLED": True,
    "TOUCHPAD_MAP": {"0": "BTN_RIGHT", "1": "BTN_LEFT"},
    "TOUCHPAD_MOVE_ENABLED": True,
    "TOUCHPAD_MOVE_PADS": [0, 1],
    "TOUCHPAD_MOUSE_SENSITIVITY": 900,
    "TOUCHPAD_HAPTIC_ENABLED": True,
    "TOUCHPAD_HAPTIC_STRENGTH": 20000,
    "TOUCHPAD_HAPTIC_DURATION_MS": 15,
    "GYRO_ENABLED": False,
    "GYRO_SENSITIVITY": 4.0,
    "DEADZONE": 8000,
}

BUTTON_LABELS = {
    "SOUTH": "A (bottom)", "EAST": "B (right)", "WEST": "X (left)", "NORTH": "Y (top)",
    "BACK": "Back / Select", "START": "Start / Menu", "GUIDE": "Steam button",
    "LEFT_STICK": "Left stick click", "RIGHT_STICK": "Right stick click",
    "LEFT_SHOULDER": "LB", "RIGHT_SHOULDER": "RB",
    "DPAD_UP": "D-pad Up", "DPAD_DOWN": "D-pad Down",
    "DPAD_LEFT": "D-pad Left", "DPAD_RIGHT": "D-pad Right",
    "LEFT_PADDLE1": "Back grip L4", "RIGHT_PADDLE1": "Back grip R4",
    "LEFT_PADDLE2": "Back grip L5", "RIGHT_PADDLE2": "Back grip R5",
    "TOUCHPAD": "Touchpad click (generic)",
}
BUTTON_ORDER = [
    "SOUTH", "EAST", "WEST", "NORTH", "BACK", "START", "GUIDE",
    "LEFT_SHOULDER", "RIGHT_SHOULDER",
    "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
    "LEFT_STICK", "RIGHT_STICK",
    "LEFT_PADDLE1", "RIGHT_PADDLE1", "LEFT_PADDLE2", "RIGHT_PADDLE2",
]

AZERTY_CHAR_TO_KEYCODE = {
    "a": "KEY_Q", "b": "KEY_B", "c": "KEY_C", "d": "KEY_D", "e": "KEY_E",
    "f": "KEY_F", "g": "KEY_G", "h": "KEY_H", "i": "KEY_I", "j": "KEY_J",
    "k": "KEY_K", "l": "KEY_L", "m": "KEY_SEMICOLON", "n": "KEY_N", "o": "KEY_O",
    "p": "KEY_P", "q": "KEY_A", "r": "KEY_R", "s": "KEY_S", "t": "KEY_T",
    "u": "KEY_U", "v": "KEY_V", "w": "KEY_Z", "x": "KEY_X", "y": "KEY_Y", "z": "KEY_W",
    "0": "KEY_0", "1": "KEY_1", "2": "KEY_2", "3": "KEY_3", "4": "KEY_4",
    "5": "KEY_5", "6": "KEY_6", "7": "KEY_7", "8": "KEY_8", "9": "KEY_9",
}
KEYSYM_TO_KEYCODE = {
    "space": "KEY_SPACE", "tab": "KEY_TAB", "escape": "KEY_ESC", "return": "KEY_ENTER",
    "backspace": "KEY_BACKSPACE", "caps_lock": "KEY_CAPSLOCK",
    "up": "KEY_UP", "down": "KEY_DOWN", "left": "KEY_LEFT", "right": "KEY_RIGHT",
    "shift_l": "KEY_LEFTSHIFT", "shift_r": "KEY_RIGHTSHIFT",
    "control_l": "KEY_LEFTCTRL", "control_r": "KEY_RIGHTCTRL",
    "alt_l": "KEY_LEFTALT", "alt_r": "KEY_RIGHTALT",
    "f1": "KEY_F1", "f2": "KEY_F2", "f3": "KEY_F3", "f4": "KEY_F4",
    "f5": "KEY_F5", "f6": "KEY_F6", "f7": "KEY_F7", "f8": "KEY_F8",
    "f9": "KEY_F9", "f10": "KEY_F10", "f11": "KEY_F11", "f12": "KEY_F12",
}


def keysym_to_evdev(keysym):
    low = keysym.lower()
    if low in KEYSYM_TO_KEYCODE:
        return KEYSYM_TO_KEYCODE[low]
    if low in AZERTY_CHAR_TO_KEYCODE:
        return AZERTY_CHAR_TO_KEYCODE[low]
    return None


def valid_evdev_name(name):
    if not name:
        return True
    return hasattr(e, name)


class MapperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Steam Controller 2026 - Mapping Configuration")
        self.config_data = self.load_config()
        self.capture_target = None

        self.gp = None
        self.gp_name = None
        self.gp_error = None
        try:
            candidate = SDL3Gamepad(enable_gyro=True)
            name = candidate.open_first()
            self.gp = candidate
            self.gp_name = name
        except RuntimeError as exc:
            self.gp = None
            self.gp_error = str(exc)

        self._build_widgets()
        self.root.bind("<KeyPress>", self._on_keypress)

        if self.gp:
            self._poll_visual()

    def load_config(self):
        if os.path.isfile(CONFIG_PATH):
            try:
                with open(CONFIG_PATH) as f:
                    data = json.load(f)
                merged = json.loads(json.dumps(DEFAULT_CONFIG))
                merged.update(data)
                return merged
            except (json.JSONDecodeError, OSError):
                pass
        return json.loads(json.dumps(DEFAULT_CONFIG))

    def save_config(self):
        cfg, invalid = self._validate_and_gather()
        if invalid:
            messagebox.showerror(
                "Invalid key name",
                "These values do not match any known evdev code:\n\n" + "\n".join(invalid)
            )
            return
        self._write_config(cfg)
        messagebox.showinfo("Saved", f"Config saved to:\n{CONFIG_PATH}\n\n"
                                      "It will be picked up automatically the next time "
                                      "sc2_sdl3_mapper.py runs.")

    def _validate_and_gather(self):
        cfg = self._gather_from_widgets()
        invalid = []
        for bname, var in self.button_vars.items():
            if not valid_evdev_name(var.get().strip()):
                invalid.append(f"{BUTTON_LABELS.get(bname, bname)}: '{var.get()}'")
        for var in self.left_stick_vars:
            if not valid_evdev_name(var.get().strip()):
                invalid.append(f"Left stick: '{var.get()}'")
        for var, _ in self.trigger_vars.values():
            if not valid_evdev_name(var.get().strip()):
                invalid.append(f"Trigger: '{var.get()}'")
        for var in self.touchpad_vars.values():
            if not valid_evdev_name(var.get().strip()):
                invalid.append(f"Touchpad: '{var.get()}'")
        if invalid:
            return None, invalid
        return cfg, None

    def _write_config(self, cfg):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    def _gather_from_widgets(self):
        return {
            "BUTTON_MAP": {k: (v.get().strip() or None) for k, v in self.button_vars.items()},
            "LEFT_STICK_MODE": self.left_stick_mode_var.get(),
            "LEFT_STICK_KEYS": [v.get().strip() for v in self.left_stick_vars],
            "RIGHT_STICK_MODE": self.right_stick_mode_var.get(),
            "RIGHT_STICK_MOUSE_SENSITIVITY": self._safe_int(self.right_stick_sens_var.get(), 18),
            "TRIGGER_MAP": {
                name: [var.get().strip(), self._safe_int(thresh_var.get(), 8000)]
                for name, (var, thresh_var) in self.trigger_vars.items()
            },
            "TOUCHPAD_ENABLED": self.touchpad_enabled_var.get(),
            "TOUCHPAD_MAP": {k: (v.get().strip() or None) for k, v in self.touchpad_vars.items()},
            "TOUCHPAD_MOVE_ENABLED": self.touchpad_move_enabled_var.get(),
            "TOUCHPAD_MOVE_PADS": [int(k) for k, v in self.touchpad_move_vars.items() if v.get()],
            "TOUCHPAD_MOUSE_SENSITIVITY": self._safe_int(self.touchpad_sens_var.get(), 900),
            "TOUCHPAD_HAPTIC_ENABLED": self.touchpad_haptic_enabled_var.get(),
            "TOUCHPAD_HAPTIC_STRENGTH": self._safe_int(self.touchpad_haptic_strength_var.get(), 20000),
            "TOUCHPAD_HAPTIC_DURATION_MS": self._safe_int(self.touchpad_haptic_duration_var.get(), 15),
            "GYRO_ENABLED": self.gyro_enabled_var.get(),
            "GYRO_SENSITIVITY": self._safe_float(self.gyro_sens_var.get(), 4.0),
            "DEADZONE": self._safe_int(self.deadzone_var.get(), 8000),
        }

    @staticmethod
    def _safe_int(val, default):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_float(val, default):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def reset_defaults(self):
        if not messagebox.askyesno("Reset", "Revert to default values (not saved until you click Save)?"):
            return
        self.config_data = json.loads(json.dumps(DEFAULT_CONFIG))
        self._populate_widgets()

    def _launch_mapping(self):
        cfg, invalid = self._validate_and_gather()
        if invalid:
            messagebox.showerror(
                "Invalid key name",
                "Fix these values before launching the mapping:\n\n" + "\n".join(invalid)
            )
            return
        self._write_config(cfg)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        wrapper = os.path.join(script_dir, "start_sc2_mapper.sh")
        if not os.path.isfile(wrapper):
            messagebox.showerror(
                "Not found",
                f"{wrapper} does not exist.\nPlace start_sc2_mapper.sh in the same folder as this script."
            )
            return

        terminal_cmd = None
        for term, prefix in [("konsole", ["-e", "bash", "-c"]),
                              ("gnome-terminal", ["--", "bash", "-c"]),
                              ("xterm", ["-e", "bash", "-c"])]:
            if shutil.which(term):
                terminal_cmd = [term] + prefix
                break
        if terminal_cmd is None:
            messagebox.showerror(
                "No terminal found",
                "No graphical terminal found (konsole/gnome-terminal/xterm).\n"
                "Run manually: " + wrapper
            )
            return

        inner = f'"{wrapper}"; echo; read -p "Press Enter to close..."'
        try:
            subprocess.Popen(terminal_cmd + [inner])
        except Exception as exc:
            messagebox.showerror("Error", f"Could not launch mapping:\n{exc}")
            return

        self.capture_label.config(text="Mapping launched in a terminal (sudo password prompt if needed).")

    def _stop_mapping(self):
        subprocess.run(["pkill", "-f", "sc2_sdl3_mapper.py"])
        self.capture_label.config(text="Stop requested.")

    def _poll_mapper_status(self):
        try:
            running = subprocess.run(
                ["pgrep", "-f", "sc2_sdl3_mapper.py"],
                capture_output=True
            ).returncode == 0
        except FileNotFoundError:
            running = False
        if running:
            self.mapping_status_label.config(text="Mapping: active", foreground="#4CAF50")
        else:
            self.mapping_status_label.config(text="Mapping: inactive", foreground="#888")
        self.root.after(2000, self._poll_mapper_status)

    def _build_widgets(self):
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = min(1500, int(screen_w * 0.90))
        win_h = min(980, int(screen_h * 0.90))
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2)
        self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.root.minsize(950, 650)

        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        top = ttk.Frame(main)
        top.pack(fill="x")

        status_text = f"Gamepad: {self.gp_name}" if self.gp else f"Error: {self.gp_error}"
        self.status_label = ttk.Label(top, text=status_text, font=("", 10, "bold"))
        self.status_label.pack(anchor="center", pady=(0, 4))

        canvas_holder = ttk.Frame(top)
        canvas_holder.pack(anchor="center")
        self.canvas = tk.Canvas(canvas_holder, width=480, height=600, bg="#1e1e1e", highlightthickness=1,
                                 highlightbackground="#555")
        self.canvas.pack()
        self._init_canvas_items()

        ttk.Separator(main).pack(fill="x", pady=8)

        bottom_container = ttk.Frame(main)
        bottom_container.pack(fill="both", expand=True)

        canvas_scroll = tk.Canvas(bottom_container, borderwidth=0)
        scrollbar = ttk.Scrollbar(bottom_container, orient="vertical", command=canvas_scroll.yview)
        scroll_frame = ttk.Frame(canvas_scroll)
        scroll_frame.bind("<Configure>", lambda ev: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all")))
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        canvas_scroll.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _center_scroll_frame(event):
            canvas_scroll.itemconfig(scroll_window_id, width=max(event.width, scroll_frame.winfo_reqwidth()))
        scroll_window_id = canvas_scroll.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas_scroll.bind("<Configure>", _center_scroll_frame)

        def _on_mousewheel(event):
            if event.num == 4:
                canvas_scroll.yview_scroll(-3, "units")
            elif event.num == 5:
                canvas_scroll.yview_scroll(3, "units")
            else:
                canvas_scroll.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas_scroll.bind_all("<MouseWheel>", _on_mousewheel)
        canvas_scroll.bind_all("<Button-4>", _on_mousewheel)
        canvas_scroll.bind_all("<Button-5>", _on_mousewheel)

        self._build_config_panel(scroll_frame)

        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Save", command=self.save_config).pack(side="right", padx=4)
        ttk.Button(bottom, text="Reset to defaults", command=self.reset_defaults).pack(side="right", padx=4)
        ttk.Button(bottom, text="Stop mapping", command=self._stop_mapping).pack(side="right", padx=4)
        ttk.Button(bottom, text="Launch mapping", command=self._launch_mapping).pack(side="right", padx=4)
        self.mapping_status_label = ttk.Label(bottom, text="Mapping: inactive", foreground="#888")
        self.mapping_status_label.pack(side="left", padx=(0, 12))
        self.capture_label = ttk.Label(bottom, text="", foreground="orange")
        self.capture_label.pack(side="left")

        self._poll_mapper_status()

    def _build_config_panel(self, parent):
        self.button_vars = {}
        self.left_stick_vars = []
        self.trigger_vars = {}
        self.touchpad_vars = {}
        self.touchpad_move_vars = {}

        row = 0
        FULL_SPAN = 9

        ttk.Label(parent, text="Buttons", font=("", 11, "bold")).grid(row=row, column=0, columnspan=FULL_SPAN, sticky="w", pady=(4, 2))
        row += 1
        n_cols = 3
        k, m = divmod(len(BUTTON_ORDER), n_cols)
        groups = [
            BUTTON_ORDER[i * k + min(i, m):(i + 1) * k + min(i + 1, m)]
            for i in range(n_cols)
        ]
        button_row_start = row
        for gi, group in enumerate(groups):
            col_label, col_entry, col_btn = gi * 3, gi * 3 + 1, gi * 3 + 2
            for i, bname in enumerate(group):
                r = button_row_start + i
                var = tk.StringVar(value=self.config_data["BUTTON_MAP"].get(bname, "") or "")
                self.button_vars[bname] = var
                ttk.Label(parent, text=BUTTON_LABELS.get(bname, bname), width=18).grid(row=r, column=col_label, sticky="w")
                ttk.Entry(parent, textvariable=var, width=16).grid(row=r, column=col_entry, sticky="w", padx=4)
                ttk.Button(parent, text="Capture", width=9, command=lambda v=var: self._start_capture(v)).grid(row=r, column=col_btn, padx=(0, 16), pady=1)
        row = button_row_start + max(len(g) for g in groups)

        ttk.Separator(parent).grid(row=row, column=0, columnspan=FULL_SPAN, sticky="ew", pady=8)
        row += 1

        ttk.Label(parent, text="Left stick", font=("", 11, "bold")).grid(row=row, column=0, columnspan=3, sticky="w")
        ttk.Label(parent, text="Right stick", font=("", 11, "bold")).grid(row=row, column=3, columnspan=3, sticky="w")
        row += 1
        stick_row_start = row

        self.left_stick_mode_var = tk.StringVar(value=self.config_data["LEFT_STICK_MODE"])
        ttk.Label(parent, text="Mode").grid(row=row, column=0, sticky="w")
        ttk.Combobox(parent, textvariable=self.left_stick_mode_var, values=["wasd", "none"], width=14, state="readonly").grid(row=row, column=1, sticky="w")

        self.right_stick_mode_var = tk.StringVar(value=self.config_data["RIGHT_STICK_MODE"])
        ttk.Label(parent, text="Mode").grid(row=row, column=3, sticky="w")
        ttk.Combobox(parent, textvariable=self.right_stick_mode_var, values=["mouse", "none"], width=14, state="readonly").grid(row=row, column=4, sticky="w")
        row += 1

        for label, keyname in zip(["Up", "Down", "Left", "Right"], self.config_data["LEFT_STICK_KEYS"]):
            var = tk.StringVar(value=keyname)
            self.left_stick_vars.append(var)
            ttk.Label(parent, text=f"  {label}").grid(row=row, column=0, sticky="w")
            ttk.Entry(parent, textvariable=var, width=16).grid(row=row, column=1, sticky="w", padx=4)
            ttk.Button(parent, text="Capture", width=9, command=lambda v=var: self._start_capture(v)).grid(row=row, column=2)
            row += 1

        self.right_stick_sens_var = tk.StringVar(value=str(self.config_data["RIGHT_STICK_MOUSE_SENSITIVITY"]))
        ttk.Label(parent, text="  Mouse sensitivity").grid(row=stick_row_start + 1, column=3, sticky="w")
        ttk.Entry(parent, textvariable=self.right_stick_sens_var, width=16).grid(row=stick_row_start + 1, column=4, sticky="w", padx=4)

        ttk.Separator(parent).grid(row=row, column=0, columnspan=FULL_SPAN, sticky="ew", pady=8)
        row += 1

        ttk.Label(parent, text="Triggers", font=("", 11, "bold")).grid(row=row, column=0, columnspan=FULL_SPAN, sticky="w")
        row += 1
        for tname, tlabel, col_off in [("LEFT_TRIGGER", "Left", 0), ("RIGHT_TRIGGER", "Right", 3)]:
            keyname, threshold = self.config_data["TRIGGER_MAP"].get(tname, ["", 8000])
            kvar = tk.StringVar(value=keyname or "")
            tvar = tk.StringVar(value=str(threshold))
            self.trigger_vars[tname] = (kvar, tvar)
            ttk.Label(parent, text=tlabel).grid(row=row, column=col_off, sticky="w")
            ttk.Entry(parent, textvariable=kvar, width=16).grid(row=row, column=col_off + 1, sticky="w", padx=4)
            ttk.Button(parent, text="Capture", width=9, command=lambda v=kvar: self._start_capture(v)).grid(row=row, column=col_off + 2)
            ttk.Label(parent, text="  Threshold (0-32767)").grid(row=row + 1, column=col_off, sticky="w")
            ttk.Entry(parent, textvariable=tvar, width=16).grid(row=row + 1, column=col_off + 1, sticky="w", padx=4)
        row += 2

        ttk.Separator(parent).grid(row=row, column=0, columnspan=FULL_SPAN, sticky="ew", pady=8)
        row += 1

        ttk.Label(parent, text="Touchpads", font=("", 11, "bold")).grid(row=row, column=0, columnspan=FULL_SPAN, sticky="w")
        row += 1
        self.touchpad_enabled_var = tk.BooleanVar(value=self.config_data["TOUCHPAD_ENABLED"])
        ttk.Checkbutton(parent, text="Enabled", variable=self.touchpad_enabled_var).grid(row=row, column=0, sticky="w")
        row += 1
        for pad_idx, pad_label, col_off in [("0", "Left - click", 0), ("1", "Right - click", 3)]:
            var = tk.StringVar(value=self.config_data["TOUCHPAD_MAP"].get(pad_idx, "") or "")
            self.touchpad_vars[pad_idx] = var
            ttk.Label(parent, text=pad_label).grid(row=row, column=col_off, sticky="w")
            ttk.Entry(parent, textvariable=var, width=16).grid(row=row, column=col_off + 1, sticky="w", padx=4)
            ttk.Button(parent, text="Capture", width=9, command=lambda v=var: self._start_capture(v)).grid(row=row, column=col_off + 2)
        row += 1

        self.touchpad_move_enabled_var = tk.BooleanVar(value=self.config_data["TOUCHPAD_MOVE_ENABLED"])
        ttk.Checkbutton(parent, text="Dragging moves the mouse", variable=self.touchpad_move_enabled_var).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1
        move_pads_set = set(self.config_data.get("TOUCHPAD_MOVE_PADS", [0, 1]))
        for pad_idx, pad_label, col_off in [(0, "  Left pad moves", 0), (1, "  Right pad moves", 3)]:
            var = tk.BooleanVar(value=pad_idx in move_pads_set)
            self.touchpad_move_vars[str(pad_idx)] = var
            ttk.Checkbutton(parent, text=pad_label, variable=var).grid(row=row, column=col_off, columnspan=3, sticky="w")
        row += 1
        self.touchpad_sens_var = tk.StringVar(value=str(self.config_data["TOUCHPAD_MOUSE_SENSITIVITY"]))
        ttk.Label(parent, text="  Drag sensitivity").grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.touchpad_sens_var, width=16).grid(row=row, column=1, sticky="w", padx=4)
        row += 1

        self.touchpad_haptic_enabled_var = tk.BooleanVar(value=self.config_data.get("TOUCHPAD_HAPTIC_ENABLED", True))
        ttk.Checkbutton(parent, text="Vibrate on click (haptic feedback)", variable=self.touchpad_haptic_enabled_var).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1
        self.touchpad_haptic_strength_var = tk.StringVar(value=str(self.config_data.get("TOUCHPAD_HAPTIC_STRENGTH", 20000)))
        ttk.Label(parent, text="  Strength (0-65535)").grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.touchpad_haptic_strength_var, width=16).grid(row=row, column=1, sticky="w", padx=4)
        row += 1
        self.touchpad_haptic_duration_var = tk.StringVar(value=str(self.config_data.get("TOUCHPAD_HAPTIC_DURATION_MS", 15)))
        ttk.Label(parent, text="  Duration (ms)").grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.touchpad_haptic_duration_var, width=16).grid(row=row, column=1, sticky="w", padx=4)
        ttk.Button(parent, text="Test", width=9, command=self._test_haptic).grid(row=row, column=2)
        row += 1

        ttk.Separator(parent).grid(row=row, column=0, columnspan=FULL_SPAN, sticky="ew", pady=8)
        row += 1

        ttk.Label(parent, text="Gyro", font=("", 11, "bold")).grid(row=row, column=0, columnspan=3, sticky="w")
        ttk.Label(parent, text="Misc", font=("", 11, "bold")).grid(row=row, column=3, columnspan=3, sticky="w")
        row += 1
        self.gyro_enabled_var = tk.BooleanVar(value=self.config_data["GYRO_ENABLED"])
        ttk.Checkbutton(parent, text="Enabled (mouse aim)", variable=self.gyro_enabled_var).grid(row=row, column=0, columnspan=2, sticky="w")

        self.deadzone_var = tk.StringVar(value=str(self.config_data["DEADZONE"]))
        ttk.Label(parent, text="Stick deadzone (0-32767)").grid(row=row, column=3, sticky="w")
        ttk.Entry(parent, textvariable=self.deadzone_var, width=16).grid(row=row, column=4, sticky="w", padx=4)
        row += 1

        self.gyro_sens_var = tk.StringVar(value=str(self.config_data["GYRO_SENSITIVITY"]))
        ttk.Label(parent, text="  Sensitivity").grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.gyro_sens_var, width=16).grid(row=row, column=1, sticky="w", padx=4)
        row += 1

    def _populate_widgets(self):
        for bname, var in self.button_vars.items():
            var.set(self.config_data["BUTTON_MAP"].get(bname, "") or "")
        for var, val in zip(self.left_stick_vars, self.config_data["LEFT_STICK_KEYS"]):
            var.set(val)
        self.left_stick_mode_var.set(self.config_data["LEFT_STICK_MODE"])
        self.right_stick_mode_var.set(self.config_data["RIGHT_STICK_MODE"])
        self.right_stick_sens_var.set(str(self.config_data["RIGHT_STICK_MOUSE_SENSITIVITY"]))
        for tname, (kvar, tvar) in self.trigger_vars.items():
            keyname, threshold = self.config_data["TRIGGER_MAP"].get(tname, ["", 8000])
            kvar.set(keyname or "")
            tvar.set(str(threshold))
        self.touchpad_enabled_var.set(self.config_data["TOUCHPAD_ENABLED"])
        for pad_idx, var in self.touchpad_vars.items():
            var.set(self.config_data["TOUCHPAD_MAP"].get(pad_idx, "") or "")
        self.touchpad_move_enabled_var.set(self.config_data["TOUCHPAD_MOVE_ENABLED"])
        move_pads_set = set(self.config_data.get("TOUCHPAD_MOVE_PADS", [0, 1]))
        for pad_idx, var in self.touchpad_move_vars.items():
            var.set(int(pad_idx) in move_pads_set)
        self.touchpad_sens_var.set(str(self.config_data["TOUCHPAD_MOUSE_SENSITIVITY"]))
        self.touchpad_haptic_enabled_var.set(self.config_data.get("TOUCHPAD_HAPTIC_ENABLED", True))
        self.touchpad_haptic_strength_var.set(str(self.config_data.get("TOUCHPAD_HAPTIC_STRENGTH", 20000)))
        self.touchpad_haptic_duration_var.set(str(self.config_data.get("TOUCHPAD_HAPTIC_DURATION_MS", 15)))
        self.gyro_enabled_var.set(self.config_data["GYRO_ENABLED"])
        self.gyro_sens_var.set(str(self.config_data["GYRO_SENSITIVITY"]))
        self.deadzone_var.set(str(self.config_data["DEADZONE"]))

    def _start_capture(self, var):
        self.capture_target = var
        self.capture_label.config(text="Press a key on your keyboard... (Esc to cancel)")

    def _on_keypress(self, event):
        if self.capture_target is None:
            return
        if event.keysym.lower() == "escape":
            self.capture_label.config(text="Capture cancelled.")
            self.capture_target = None
            return
        code = keysym_to_evdev(event.keysym)
        if code is None:
            self.capture_label.config(text=f"Key '{event.keysym}' not recognized, type the evdev code manually.")
        else:
            self.capture_target.set(code)
            self.capture_label.config(text=f"Captured: {code}")
        self.capture_target = None

    def _test_haptic(self):
        if self.gp is None:
            self.capture_label.config(text="No gamepad connected, cannot test.")
            return
        strength = self._safe_int(self.touchpad_haptic_strength_var.get(), 20000)
        duration = self._safe_int(self.touchpad_haptic_duration_var.get(), 15)
        self.gp.rumble(strength, strength, duration)
        self.capture_label.config(text=f"Vibration tested (strength={strength}, duration={duration}ms)")

    def _init_canvas_items(self):
        c = self.canvas
        self.button_shapes = {}

        positions = {
            "LEFT_SHOULDER": (60, 30), "RIGHT_SHOULDER": (420, 30),
            "DPAD_UP": (110, 90), "DPAD_LEFT": (75, 125), "DPAD_RIGHT": (145, 125), "DPAD_DOWN": (110, 160),
            "BACK": (190, 100), "GUIDE": (240, 130), "START": (290, 100),
            "NORTH": (400, 90), "WEST": (365, 125), "EAST": (435, 125), "SOUTH": (400, 160),
        }
        for name, (x, y) in positions.items():
            shape = c.create_oval(x - 18, y - 18, x + 18, y + 18, fill="#333", outline="#888", width=2)
            c.create_text(x, y + 30, text=name.replace("_", " "), fill="#aaa", font=("", 8))
            self.button_shapes[name] = shape

        self.left_stick_box = c.create_rectangle(60, 220, 180, 320, outline="#555", width=2)
        c.create_text(120, 332, text="Left stick (outline = click)", fill="#aaa", font=("", 8))
        self.left_stick_dot = c.create_oval(114, 264, 126, 276, fill="cyan")

        self.right_stick_box = c.create_rectangle(300, 220, 420, 320, outline="#555", width=2)
        c.create_text(360, 332, text="Right stick (outline = click)", fill="#aaa", font=("", 8))
        self.right_stick_dot = c.create_oval(354, 264, 366, 276, fill="cyan")

        c.create_rectangle(15, 220, 35, 320, outline="#555", width=2)
        c.create_text(25, 332, text="LT", fill="#aaa", font=("", 8))
        self.lt_bar = c.create_rectangle(15, 320, 35, 320, fill="orange")

        c.create_rectangle(445, 220, 465, 320, outline="#555", width=2)
        c.create_text(455, 332, text="RT", fill="#aaa", font=("", 8))
        self.rt_bar = c.create_rectangle(445, 320, 465, 320, fill="orange")

        grip_positions = {
            "LEFT_PADDLE1": (60, 355), "LEFT_PADDLE2": (100, 355),
            "RIGHT_PADDLE1": (380, 355), "RIGHT_PADDLE2": (420, 355),
        }
        grip_labels = {"LEFT_PADDLE1": "L4", "LEFT_PADDLE2": "L5", "RIGHT_PADDLE1": "R4", "RIGHT_PADDLE2": "R5"}
        for name, (x, y) in grip_positions.items():
            shape = c.create_rectangle(x - 15, y - 12, x + 15, y + 12, fill="#333", outline="#888", width=2)
            c.create_text(x, y, text=grip_labels[name], fill="#ccc", font=("", 8, "bold"))
            self.button_shapes[name] = shape

        self.touch0_rect = c.create_rectangle(30, 400, 225, 520, outline="#555", width=2)
        c.create_text(127, 532, text="Left pad (outline = click)", fill="#aaa", font=("", 8))
        self.touch0_dot = c.create_oval(122, 455, 132, 465, fill="", outline="")

        self.touch1_rect = c.create_rectangle(255, 400, 450, 520, outline="#555", width=2)
        c.create_text(352, 532, text="Right pad (outline = click)", fill="#aaa", font=("", 8))
        self.touch1_dot = c.create_oval(347, 455, 357, 465, fill="", outline="")

        self.gyro_text = c.create_text(240, 560, text="", fill="#aaa", font=("", 8))

    def _poll_visual(self):
        if self.gp is None:
            return
        self.gp.pump()
        c = self.canvas

        for name, shape in self.button_shapes.items():
            pressed = self.gp.button(name)
            fill = "#4CAF50" if pressed else "#333"
            c.itemconfig(shape, fill=fill)

        c.itemconfig(self.left_stick_box, outline="#4CAF50" if self.gp.button("LEFT_STICK") else "#555")
        c.itemconfig(self.right_stick_box, outline="#4CAF50" if self.gp.button("RIGHT_STICK") else "#555")

        lx, ly = self.gp.axis("LEFTX"), self.gp.axis("LEFTY")
        cx, cy = 120 + (lx / 32767.0) * 50, 270 + (ly / 32767.0) * 40
        c.coords(self.left_stick_dot, cx - 6, cy - 6, cx + 6, cy + 6)

        rx, ry = self.gp.axis("RIGHTX"), self.gp.axis("RIGHTY")
        cx2, cy2 = 360 + (rx / 32767.0) * 50, 270 + (ry / 32767.0) * 40
        c.coords(self.right_stick_dot, cx2 - 6, cy2 - 6, cx2 + 6, cy2 + 6)

        lt = max(0, self.gp.axis("LEFT_TRIGGER"))
        rt = max(0, self.gp.axis("RIGHT_TRIGGER"))
        lt_h = (lt / 32767.0) * 100
        rt_h = (rt / 32767.0) * 100
        c.coords(self.lt_bar, 15, 320 - lt_h, 35, 320)
        c.coords(self.rt_bar, 445, 320 - rt_h, 465, 320)

        num_pads = self.gp.num_touchpads()
        for pad_idx, dot, (x0, y0, x1, y1) in [
            (0, self.touch0_dot, (30, 400, 225, 520)),
            (1, self.touch1_dot, (255, 400, 450, 520)),
        ]:
            if pad_idx < num_pads:
                ok, down, tx, ty, pressure = self.gp.touchpad_finger(pad_idx)
                if ok and down:
                    px = x0 + tx * (x1 - x0)
                    py = y0 + ty * (y1 - y0)
                    c.coords(dot, px - 7, py - 7, px + 7, py + 7)
                    c.itemconfig(dot, fill="#4CAF50", outline="white")
                else:
                    c.itemconfig(dot, fill="", outline="")

        c.itemconfig(self.touch0_rect, outline="#4CAF50" if self.gp.button("TOUCHPAD") else "#555")
        c.itemconfig(self.touch1_rect, outline="#4CAF50" if self.gp.button("MISC2") else "#555")

        ok, gx, gy, gz = self.gp.gyro()
        if ok:
            c.itemconfig(self.gyro_text, text=f"Gyro x={gx:.2f} y={gy:.2f} z={gz:.2f}")

        self.root.after(16, self._poll_visual)

    def on_close(self):
        if self.gp:
            self.gp.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MapperGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()

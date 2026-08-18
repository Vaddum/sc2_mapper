#!/usr/bin/env python3
import sys
import os
import json
import ctypes
import ctypes.util
import time
import signal
import subprocess
import shutil
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from evdev import UInput, ecodes as e
except ImportError:
    print("The 'evdev' module is required: pip install evdev --break-system-packages")
    sys.exit(1)

CONFIG_PATH = os.path.expanduser("~/.config/sc2_mapper/config.json")

SDL_INIT_GAMEPAD = 0x00002000
SDL_INIT_SENSOR = 0x00008000
SDL_SENSOR_GYRO = 2

BUTTON_NAMES = [
    "SOUTH", "EAST", "WEST", "NORTH", "BACK", "GUIDE", "START",
    "LEFT_STICK", "RIGHT_STICK", "LEFT_SHOULDER", "RIGHT_SHOULDER",
    "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
    "MISC1", "RIGHT_PADDLE1", "LEFT_PADDLE1", "RIGHT_PADDLE2", "LEFT_PADDLE2",
    "TOUCHPAD", "MISC2", "MISC3", "MISC4", "MISC5", "MISC6",
]
AXIS_NAMES = ["LEFTX", "LEFTY", "RIGHTX", "RIGHTY", "LEFT_TRIGGER", "RIGHT_TRIGGER"]
TOUCHPAD_CLICK_BUTTONS = {0: "TOUCHPAD", 1: "MISC2"}


class SDL3Gamepad:
    def __init__(self, enable_gyro=False):
        libname = ctypes.util.find_library("SDL3") or "libSDL3.so.0"
        try:
            self.sdl = ctypes.CDLL(libname)
        except OSError as exc:
            raise RuntimeError(
                f"Could not load {libname}. Install the 'sdl3' package (pacman -S sdl3)."
            ) from exc

        self.enable_gyro = enable_gyro
        self.gamepad = None
        self._bind_functions()

    def _bind_functions(self):
        sdl = self.sdl
        sdl.SDL_Init.argtypes = [ctypes.c_uint32]
        sdl.SDL_Init.restype = ctypes.c_bool

        sdl.SDL_GetError.restype = ctypes.c_char_p

        sdl.SDL_GetGamepads.argtypes = [ctypes.POINTER(ctypes.c_int)]
        sdl.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)

        sdl.SDL_OpenGamepad.argtypes = [ctypes.c_uint32]
        sdl.SDL_OpenGamepad.restype = ctypes.c_void_p

        sdl.SDL_CloseGamepad.argtypes = [ctypes.c_void_p]

        sdl.SDL_GetGamepadName.argtypes = [ctypes.c_void_p]
        sdl.SDL_GetGamepadName.restype = ctypes.c_char_p

        sdl.SDL_GetGamepadButton.argtypes = [ctypes.c_void_p, ctypes.c_int]
        sdl.SDL_GetGamepadButton.restype = ctypes.c_bool

        sdl.SDL_GetGamepadAxis.argtypes = [ctypes.c_void_p, ctypes.c_int]
        sdl.SDL_GetGamepadAxis.restype = ctypes.c_int16

        sdl.SDL_PumpEvents.argtypes = []

        sdl.SDL_GamepadHasSensor.argtypes = [ctypes.c_void_p, ctypes.c_int]
        sdl.SDL_GamepadHasSensor.restype = ctypes.c_bool

        sdl.SDL_SetGamepadSensorEnabled.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_bool]
        sdl.SDL_SetGamepadSensorEnabled.restype = ctypes.c_bool

        sdl.SDL_GetGamepadSensorData.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_float), ctypes.c_int
        ]
        sdl.SDL_GetGamepadSensorData.restype = ctypes.c_bool

        sdl.SDL_GetNumGamepadTouchpads.argtypes = [ctypes.c_void_p]
        sdl.SDL_GetNumGamepadTouchpads.restype = ctypes.c_int

        sdl.SDL_GetGamepadTouchpadFinger.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_bool), ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
        ]
        sdl.SDL_GetGamepadTouchpadFinger.restype = ctypes.c_bool

        sdl.SDL_RumbleGamepad.argtypes = [
            ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint32
        ]
        sdl.SDL_RumbleGamepad.restype = ctypes.c_bool

        sdl.SDL_Quit.argtypes = []

    def open_first(self):
        flags = SDL_INIT_GAMEPAD | (SDL_INIT_SENSOR if self.enable_gyro else 0)
        if not self.sdl.SDL_Init(flags):
            raise RuntimeError("SDL_Init failed: " + self.sdl.SDL_GetError().decode(errors="replace"))

        count = ctypes.c_int(0)
        ids = self.sdl.SDL_GetGamepads(ctypes.byref(count))
        if count.value == 0:
            raise RuntimeError("No gamepad detected by SDL3.")

        self.gamepad = self.sdl.SDL_OpenGamepad(ids[0])
        if not self.gamepad:
            raise RuntimeError("Failed to open gamepad: " + self.sdl.SDL_GetError().decode(errors="replace"))

        name = self.sdl.SDL_GetGamepadName(self.gamepad)
        name_str = name.decode(errors="replace") if name else "unknown"

        if self.enable_gyro:
            if self.sdl.SDL_GamepadHasSensor(self.gamepad, SDL_SENSOR_GYRO):
                self.sdl.SDL_SetGamepadSensorEnabled(self.gamepad, SDL_SENSOR_GYRO, True)

        return name_str

    def pump(self):
        self.sdl.SDL_PumpEvents()

    def button(self, name):
        idx = BUTTON_NAMES.index(name)
        return bool(self.sdl.SDL_GetGamepadButton(self.gamepad, idx))

    def axis(self, name):
        idx = AXIS_NAMES.index(name)
        return self.sdl.SDL_GetGamepadAxis(self.gamepad, idx)

    def num_touchpads(self):
        return self.sdl.SDL_GetNumGamepadTouchpads(self.gamepad)

    def touchpad_finger(self, pad_idx, finger=0):
        down = ctypes.c_bool(False)
        x = ctypes.c_float(0.0)
        y = ctypes.c_float(0.0)
        pressure = ctypes.c_float(0.0)
        ok = self.sdl.SDL_GetGamepadTouchpadFinger(
            self.gamepad, pad_idx, finger,
            ctypes.byref(down), ctypes.byref(x), ctypes.byref(y), ctypes.byref(pressure)
        )
        return bool(ok), down.value, x.value, y.value, pressure.value

    def gyro(self):
        if not self.enable_gyro:
            return False, 0.0, 0.0, 0.0
        data = (ctypes.c_float * 3)()
        ok = self.sdl.SDL_GetGamepadSensorData(self.gamepad, SDL_SENSOR_GYRO, data, 3)
        return bool(ok), data[0], data[1], data[2]

    def rumble(self, low_freq, high_freq, duration_ms):
        return bool(self.sdl.SDL_RumbleGamepad(self.gamepad, low_freq, high_freq, duration_ms))

    def close(self):
        if self.gamepad:
            self.sdl.SDL_CloseGamepad(self.gamepad)
        self.sdl.SDL_Quit()


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


def load_saved_config():
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
            merged.update(data)
        except (json.JSONDecodeError, OSError):
            pass
    return merged


def key_code(name):
    if not name:
        return None
    return getattr(e, name)


def prepare_environment():
    try:
        if subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0:
            print("Steam is running - closing it to release the gamepad...")
            subprocess.run(["killall", "steam"], capture_output=True)
            for _ in range(10):
                if subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode != 0:
                    break
                time.sleep(1)
            if subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0:
                print("Steam did not close properly. Close it manually then rerun this script.")
                sys.exit(1)
            print("Steam closed.")
        else:
            print("Steam is not running, continuing.")
    except FileNotFoundError:
        pass

    try:
        lsmod_output = subprocess.run(["lsmod"], capture_output=True, text=True).stdout
        if "uinput" not in lsmod_output:
            print("Loading uinput module...")
            subprocess.run(["sudo", "modprobe", "uinput"])
    except FileNotFoundError:
        pass


def run_mapping(debug=False):
    prepare_environment()

    cfg = load_saved_config()
    print(f"Config loaded from {CONFIG_PATH}" if os.path.isfile(CONFIG_PATH) else "No saved config found, using default values.")

    button_map_codes = {k: key_code(v) for k, v in cfg["BUTTON_MAP"].items()}
    left_stick_mode = cfg["LEFT_STICK_MODE"]
    left_stick_keys_codes = [key_code(k) for k in cfg["LEFT_STICK_KEYS"]]
    right_stick_mode = cfg["RIGHT_STICK_MODE"]
    right_stick_sensitivity = cfg["RIGHT_STICK_MOUSE_SENSITIVITY"]
    trigger_map_codes = {k: (key_code(v[0]), v[1]) for k, v in cfg["TRIGGER_MAP"].items()}
    touchpad_enabled = cfg["TOUCHPAD_ENABLED"]
    touchpad_map_codes = {int(k): key_code(v) for k, v in cfg["TOUCHPAD_MAP"].items()}
    touchpad_move_enabled = cfg["TOUCHPAD_MOVE_ENABLED"]
    touchpad_move_pads = set(int(x) for x in cfg["TOUCHPAD_MOVE_PADS"])
    touchpad_sensitivity = cfg["TOUCHPAD_MOUSE_SENSITIVITY"]
    touchpad_haptic_enabled = cfg["TOUCHPAD_HAPTIC_ENABLED"]
    touchpad_haptic_strength = cfg["TOUCHPAD_HAPTIC_STRENGTH"]
    touchpad_haptic_duration = cfg["TOUCHPAD_HAPTIC_DURATION_MS"]
    gyro_enabled = cfg["GYRO_ENABLED"]
    gyro_sensitivity = cfg["GYRO_SENSITIVITY"]
    deadzone = cfg["DEADZONE"]

    gp = SDL3Gamepad(enable_gyro=gyro_enabled)
    try:
        name = gp.open_first()
    except RuntimeError as exc:
        print(str(exc))
        sys.exit(1)

    print(f"Gamepad detected: {name}")
    if gyro_enabled:
        print("Gyro enabled.")

    capabilities = {
        e.EV_KEY: sorted(set(
            [k for k in button_map_codes.values() if k is not None]
            + [k for k in left_stick_keys_codes if k is not None]
            + [k for k, _ in trigger_map_codes.values() if k is not None]
            + [k for k in touchpad_map_codes.values() if k is not None]
            + [e.BTN_LEFT, e.BTN_RIGHT]
        )),
        e.EV_REL: [e.REL_X, e.REL_Y],
    }

    if not debug:
        ui = UInput(capabilities, name="sc2-sdl3-mapper-virtual")
        print("Virtual uinput device created.")
    else:
        ui = None
        print("DEBUG mode: no key will be sent, raw output only.")

    num_touchpads = gp.num_touchpads() if touchpad_enabled else 0
    if touchpad_enabled:
        print(f"Touchpads detected: {num_touchpads}")

    running = True
    def handle_sigint(sig, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, handle_sigint)

    prev_buttons = {n: False for n in BUTTON_NAMES}
    prev_triggers = {n: False for n in trigger_map_codes}
    prev_touchpads = {idx: False for idx in touchpad_map_codes}
    prev_touch_pos = {idx: None for idx in touchpad_map_codes}
    prev_left_stick = {k: False for k in left_stick_keys_codes} if left_stick_mode == "wasd" else {}

    print("Mapping active. Ctrl+C to quit.\n")

    try:
        while running:
            gp.pump()

            for bname in BUTTON_NAMES:
                if bname in ("TOUCHPAD", "MISC2"):
                    continue
                pressed = gp.button(bname)
                if pressed != prev_buttons[bname]:
                    key = button_map_codes.get(bname)
                    if debug:
                        print(f"[button] {bname}: {'pressed' if pressed else 'released'}")
                    elif key is not None:
                        ui.write(e.EV_KEY, key, 1 if pressed else 0)
                        ui.syn()
                    prev_buttons[bname] = pressed

            if left_stick_mode == "wasd":
                lx = gp.axis("LEFTX")
                ly = gp.axis("LEFTY")
                up, down, left, right = left_stick_keys_codes
                want = {
                    up:    ly < -deadzone,
                    down:  ly > deadzone,
                    left:  lx < -deadzone,
                    right: lx > deadzone,
                }
                for key, active in want.items():
                    if active != prev_left_stick[key]:
                        if debug:
                            print(f"[left stick] key {key}: {'pressed' if active else 'released'}")
                        else:
                            ui.write(e.EV_KEY, key, 1 if active else 0)
                        prev_left_stick[key] = active
                if not debug:
                    ui.syn()

            if right_stick_mode == "mouse":
                rx = gp.axis("RIGHTX")
                ry = gp.axis("RIGHTY")
                if abs(rx) > deadzone or abs(ry) > deadzone:
                    dx = int((rx / 32767.0) * right_stick_sensitivity)
                    dy = int((ry / 32767.0) * right_stick_sensitivity)
                    if debug:
                        print(f"[right stick] dx={dx} dy={dy}")
                    else:
                        ui.write(e.EV_REL, e.REL_X, dx)
                        ui.write(e.EV_REL, e.REL_Y, dy)
                        ui.syn()

            for tname, (key, threshold) in trigger_map_codes.items():
                val = gp.axis(tname)
                active = val > threshold
                if active != prev_triggers[tname]:
                    if debug:
                        print(f"[trigger] {tname}: {'active' if active else 'released'} (val={val})")
                    elif key is not None:
                        ui.write(e.EV_KEY, key, 1 if active else 0)
                        ui.syn()
                    prev_triggers[tname] = active

            if touchpad_enabled:
                for pad_idx in touchpad_map_codes:
                    if pad_idx >= num_touchpads:
                        continue
                    ok, down_val, x, y, pressure = gp.touchpad_finger(pad_idx)
                    if not ok:
                        continue

                    if touchpad_move_enabled and pad_idx in touchpad_move_pads:
                        if down_val:
                            if prev_touch_pos[pad_idx] is not None:
                                px, py = prev_touch_pos[pad_idx]
                                dx = (x - px) * touchpad_sensitivity
                                dy = (y - py) * touchpad_sensitivity
                                if abs(dx) > 0.4 or abs(dy) > 0.4:
                                    if debug:
                                        print(f"[touchpad {pad_idx}] move dx={dx:.1f} dy={dy:.1f}")
                                    else:
                                        ui.write(e.EV_REL, e.REL_X, int(dx))
                                        ui.write(e.EV_REL, e.REL_Y, int(dy))
                                        ui.syn()
                            prev_touch_pos[pad_idx] = (x, y)
                        else:
                            prev_touch_pos[pad_idx] = None

            for pad_idx, bname in TOUCHPAD_CLICK_BUTTONS.items():
                key = touchpad_map_codes.get(pad_idx)
                pressed = gp.button(bname)
                if pressed != prev_touchpads[pad_idx]:
                    if debug:
                        print(f"[touchpad {pad_idx}] click ({bname}): {'pressed' if pressed else 'released'}")
                    elif key is not None:
                        ui.write(e.EV_KEY, key, 1 if pressed else 0)
                        ui.syn()
                    if pressed and touchpad_haptic_enabled:
                        gp.rumble(touchpad_haptic_strength, touchpad_haptic_strength, touchpad_haptic_duration)
                    prev_touchpads[pad_idx] = pressed

            if gyro_enabled:
                ok, gx, gy, gz = gp.gyro()
                if ok and (abs(gz) > 0.05 or abs(gx) > 0.05):
                    dx = int(gz * gyro_sensitivity * -100)
                    dy = int(gx * gyro_sensitivity * 100)
                    if debug:
                        print(f"[gyro] dx={dx} dy={dy}")
                    else:
                        ui.write(e.EV_REL, e.REL_X, dx)
                        ui.write(e.EV_REL, e.REL_Y, dy)
                        ui.syn()

            time.sleep(0.008)

    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping...")
        gp.close()
        if ui:
            ui.close()
        print("Done.")


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
        return load_saved_config()

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
                                      "mapping is launched.")

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
                "Run manually: python3 " + os.path.abspath(__file__) + " --run-mapping"
            )
            return

        script_path = os.path.abspath(__file__)
        runner = "python3" if os.access("/dev/uinput", os.W_OK) else "sudo python3"
        inner = f'{runner} "{script_path}" --run-mapping; echo; read -p "Press Enter to close..."'
        try:
            subprocess.Popen(terminal_cmd + [inner])
        except Exception as exc:
            messagebox.showerror("Error", f"Could not launch mapping:\n{exc}")
            return

        self.capture_label.config(text="Mapping launched in a terminal (sudo password prompt if needed).")

    def _poll_mapper_status(self):
        try:
            running = subprocess.run(
                ["pgrep", "-f", "--run-mapping"],
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
        win_w = min(2200, int(screen_w * 0.98))
        win_h = min(1400, int(screen_h * 0.98))
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2)
        self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.root.minsize(1400, 950)

        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        top = ttk.Frame(main)
        top.pack(fill="x")

        status_text = f"Gamepad: {self.gp_name}" if self.gp else f"Error: {self.gp_error}"
        status_color = "black" if self.gp else "red"
        self.status_label = ttk.Label(top, text=status_text, font=("", 10, "bold"), foreground=status_color)
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
        ttk.Button(bottom, text="Launch mapping", command=self._launch_mapping).pack(side="right", padx=4)
        ttk.Button(bottom, text="Exit", command=self.on_close).pack(side="right", padx=4)
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


def main_gui():
    root = tk.Tk()
    app = MapperGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    if "--run-mapping" in sys.argv:
        run_mapping(debug="--debug" in sys.argv)
    else:
        main_gui()

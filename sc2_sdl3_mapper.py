#!/usr/bin/env python3
import sys
import os
import json
import time
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdl3_gamepad import SDL3Gamepad, BUTTON_NAMES, AXIS_NAMES

try:
    from evdev import UInput, ecodes as e
except ImportError:
    print("The 'evdev' module is required: pip install evdev --break-system-packages")
    sys.exit(1)

DEBUG = "--debug" in sys.argv
CONFIG_PATH = os.path.expanduser("~/.config/sc2_mapper/config.json")

BUTTON_MAP = {
    "SOUTH": "KEY_F11", "EAST": "KEY_F10", "WEST": "KEY_F12", "NORTH": "KEY_F9",
    "BACK": "KEY_F6", "START": "KEY_F5", "GUIDE": None,
    "LEFT_STICK": "KEY_LEFTSHIFT", "RIGHT_STICK": "BTN_RIGHT",
    "LEFT_SHOULDER": "KEY_F7", "RIGHT_SHOULDER": "KEY_F8",
    "DPAD_UP": "KEY_F1", "DPAD_DOWN": "KEY_F3", "DPAD_LEFT": "KEY_F4", "DPAD_RIGHT": "KEY_F2",
    "LEFT_PADDLE1": "KEY_G", "RIGHT_PADDLE1": "KEY_M",
    "LEFT_PADDLE2": "KEY_TAB", "RIGHT_PADDLE2": "KEY_F",
    "TOUCHPAD": None,
}
LEFT_STICK_MODE = "wasd"
LEFT_STICK_KEYS = ["KEY_W", "KEY_S", "KEY_A", "KEY_D"]
RIGHT_STICK_MODE = "mouse"
RIGHT_STICK_MOUSE_SENSITIVITY = 18
TRIGGER_MAP = {
    "LEFT_TRIGGER": ["KEY_LEFTSHIFT", 8000],
    "RIGHT_TRIGGER": ["KEY_LEFTCTRL", 8000],
}
TOUCHPAD_ENABLED = True
TOUCHPAD_MAP = {"0": "BTN_RIGHT", "1": "BTN_LEFT"}
TOUCHPAD_MOVE_ENABLED = True
TOUCHPAD_MOVE_PADS = [0, 1]
TOUCHPAD_MOUSE_SENSITIVITY = 900
TOUCHPAD_HAPTIC_ENABLED = True
TOUCHPAD_HAPTIC_STRENGTH = 20000
TOUCHPAD_HAPTIC_DURATION_MS = 15
GYRO_ENABLED = False
GYRO_SENSITIVITY = 4.0
DEADZONE = 8000

if os.path.isfile(CONFIG_PATH):
    try:
        with open(CONFIG_PATH) as f:
            saved = json.load(f)
        BUTTON_MAP = saved.get("BUTTON_MAP", BUTTON_MAP)
        LEFT_STICK_MODE = saved.get("LEFT_STICK_MODE", LEFT_STICK_MODE)
        LEFT_STICK_KEYS = saved.get("LEFT_STICK_KEYS", LEFT_STICK_KEYS)
        RIGHT_STICK_MODE = saved.get("RIGHT_STICK_MODE", RIGHT_STICK_MODE)
        RIGHT_STICK_MOUSE_SENSITIVITY = saved.get("RIGHT_STICK_MOUSE_SENSITIVITY", RIGHT_STICK_MOUSE_SENSITIVITY)
        TRIGGER_MAP = saved.get("TRIGGER_MAP", TRIGGER_MAP)
        TOUCHPAD_ENABLED = saved.get("TOUCHPAD_ENABLED", TOUCHPAD_ENABLED)
        TOUCHPAD_MAP = saved.get("TOUCHPAD_MAP", TOUCHPAD_MAP)
        TOUCHPAD_MOVE_ENABLED = saved.get("TOUCHPAD_MOVE_ENABLED", TOUCHPAD_MOVE_ENABLED)
        TOUCHPAD_MOVE_PADS = saved.get("TOUCHPAD_MOVE_PADS", TOUCHPAD_MOVE_PADS)
        TOUCHPAD_MOUSE_SENSITIVITY = saved.get("TOUCHPAD_MOUSE_SENSITIVITY", TOUCHPAD_MOUSE_SENSITIVITY)
        TOUCHPAD_HAPTIC_ENABLED = saved.get("TOUCHPAD_HAPTIC_ENABLED", TOUCHPAD_HAPTIC_ENABLED)
        TOUCHPAD_HAPTIC_STRENGTH = saved.get("TOUCHPAD_HAPTIC_STRENGTH", TOUCHPAD_HAPTIC_STRENGTH)
        TOUCHPAD_HAPTIC_DURATION_MS = saved.get("TOUCHPAD_HAPTIC_DURATION_MS", TOUCHPAD_HAPTIC_DURATION_MS)
        GYRO_ENABLED = saved.get("GYRO_ENABLED", GYRO_ENABLED)
        GYRO_SENSITIVITY = saved.get("GYRO_SENSITIVITY", GYRO_SENSITIVITY)
        DEADZONE = saved.get("DEADZONE", DEADZONE)
        print(f"Config loaded from {CONFIG_PATH}")
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Could not read {CONFIG_PATH} ({exc}), using default values.")
else:
    print("No saved config found, using default values.")


def key_code(name):
    if name is None:
        return None
    return getattr(e, name)


BUTTON_MAP_CODES = {k: key_code(v) for k, v in BUTTON_MAP.items()}
LEFT_STICK_KEYS_CODES = [key_code(k) for k in LEFT_STICK_KEYS]
TRIGGER_MAP_CODES = {k: (key_code(v[0]), v[1]) for k, v in TRIGGER_MAP.items()}
TOUCHPAD_MAP_CODES = {int(k): key_code(v) for k, v in TOUCHPAD_MAP.items()}
TOUCHPAD_MOVE_PADS_SET = set(int(x) for x in TOUCHPAD_MOVE_PADS)

TOUCHPAD_CLICK_BUTTONS = {0: "TOUCHPAD", 1: "MISC2"}

gp = SDL3Gamepad(enable_gyro=GYRO_ENABLED)
try:
    name = gp.open_first()
except RuntimeError as exc:
    print(str(exc))
    sys.exit(1)

print(f"Gamepad detected: {name}")
if GYRO_ENABLED:
    print("Gyro enabled.")

capabilities = {
    e.EV_KEY: sorted(set(
        [k for k in BUTTON_MAP_CODES.values() if k is not None]
        + [k for k in LEFT_STICK_KEYS_CODES if k is not None]
        + [k for k, _ in TRIGGER_MAP_CODES.values() if k is not None]
        + [k for k in TOUCHPAD_MAP_CODES.values() if k is not None]
        + [e.BTN_LEFT, e.BTN_RIGHT]
    )),
    e.EV_REL: [e.REL_X, e.REL_Y],
}

if not DEBUG:
    ui = UInput(capabilities, name="sc2-sdl3-mapper-virtual")
    print("Virtual uinput device created.")
else:
    ui = None
    print("DEBUG mode: no key will be sent, raw output only.")

num_touchpads = gp.num_touchpads() if TOUCHPAD_ENABLED else 0
if TOUCHPAD_ENABLED:
    print(f"Touchpads detected: {num_touchpads}")

running = True
def handle_sigint(sig, frame):
    global running
    running = False
signal.signal(signal.SIGINT, handle_sigint)

prev_buttons = {n: False for n in BUTTON_NAMES}
prev_triggers = {n: False for n in TRIGGER_MAP_CODES}
prev_touchpads = {idx: False for idx in TOUCHPAD_MAP_CODES}
prev_touch_pos = {idx: None for idx in TOUCHPAD_MAP_CODES}
prev_left_stick = {k: False for k in LEFT_STICK_KEYS_CODES} if LEFT_STICK_MODE == "wasd" else {}

print("Mapping active. Ctrl+C to quit.\n")

try:
    while running:
        gp.pump()

        for bname in BUTTON_NAMES:
            if bname in ("TOUCHPAD", "MISC2"):
                continue
            pressed = gp.button(bname)
            if pressed != prev_buttons[bname]:
                key = BUTTON_MAP_CODES.get(bname)
                if DEBUG:
                    print(f"[button] {bname}: {'pressed' if pressed else 'released'}")
                elif key is not None:
                    ui.write(e.EV_KEY, key, 1 if pressed else 0)
                    ui.syn()
                prev_buttons[bname] = pressed

        if LEFT_STICK_MODE == "wasd":
            lx = gp.axis("LEFTX")
            ly = gp.axis("LEFTY")
            up, down, left, right = LEFT_STICK_KEYS_CODES
            want = {
                up:    ly < -DEADZONE,
                down:  ly > DEADZONE,
                left:  lx < -DEADZONE,
                right: lx > DEADZONE,
            }
            for key, active in want.items():
                if active != prev_left_stick[key]:
                    if DEBUG:
                        print(f"[left stick] key {key}: {'pressed' if active else 'released'}")
                    else:
                        ui.write(e.EV_KEY, key, 1 if active else 0)
                    prev_left_stick[key] = active
            if not DEBUG:
                ui.syn()

        if RIGHT_STICK_MODE == "mouse":
            rx = gp.axis("RIGHTX")
            ry = gp.axis("RIGHTY")
            if abs(rx) > DEADZONE or abs(ry) > DEADZONE:
                dx = int((rx / 32767.0) * RIGHT_STICK_MOUSE_SENSITIVITY)
                dy = int((ry / 32767.0) * RIGHT_STICK_MOUSE_SENSITIVITY)
                if DEBUG:
                    print(f"[right stick] dx={dx} dy={dy}")
                else:
                    ui.write(e.EV_REL, e.REL_X, dx)
                    ui.write(e.EV_REL, e.REL_Y, dy)
                    ui.syn()

        for tname, (key, threshold) in TRIGGER_MAP_CODES.items():
            val = gp.axis(tname)
            active = val > threshold
            if active != prev_triggers[tname]:
                if DEBUG:
                    print(f"[trigger] {tname}: {'active' if active else 'released'} (val={val})")
                elif key is not None:
                    ui.write(e.EV_KEY, key, 1 if active else 0)
                    ui.syn()
                prev_triggers[tname] = active

        if TOUCHPAD_ENABLED:
            for pad_idx in TOUCHPAD_MAP_CODES:
                if pad_idx >= num_touchpads:
                    continue
                ok, down_val, x, y, pressure = gp.touchpad_finger(pad_idx)
                if not ok:
                    continue

                if TOUCHPAD_MOVE_ENABLED and pad_idx in TOUCHPAD_MOVE_PADS_SET:
                    if down_val:
                        if prev_touch_pos[pad_idx] is not None:
                            px, py = prev_touch_pos[pad_idx]
                            dx = (x - px) * TOUCHPAD_MOUSE_SENSITIVITY
                            dy = (y - py) * TOUCHPAD_MOUSE_SENSITIVITY
                            if abs(dx) > 0.4 or abs(dy) > 0.4:
                                if DEBUG:
                                    print(f"[touchpad {pad_idx}] move dx={dx:.1f} dy={dy:.1f}")
                                else:
                                    ui.write(e.EV_REL, e.REL_X, int(dx))
                                    ui.write(e.EV_REL, e.REL_Y, int(dy))
                                    ui.syn()
                        prev_touch_pos[pad_idx] = (x, y)
                    else:
                        prev_touch_pos[pad_idx] = None

        for pad_idx, bname in TOUCHPAD_CLICK_BUTTONS.items():
            key = TOUCHPAD_MAP_CODES.get(pad_idx)
            pressed = gp.button(bname)
            if pressed != prev_touchpads[pad_idx]:
                if DEBUG:
                    print(f"[touchpad {pad_idx}] click ({bname}): {'pressed' if pressed else 'released'}")
                elif key is not None:
                    ui.write(e.EV_KEY, key, 1 if pressed else 0)
                    ui.syn()
                if pressed and TOUCHPAD_HAPTIC_ENABLED:
                    gp.rumble(TOUCHPAD_HAPTIC_STRENGTH, TOUCHPAD_HAPTIC_STRENGTH, TOUCHPAD_HAPTIC_DURATION_MS)
                prev_touchpads[pad_idx] = pressed

        if GYRO_ENABLED:
            ok, gx, gy, gz = gp.gyro()
            if ok and (abs(gz) > 0.05 or abs(gx) > 0.05):
                dx = int(gz * GYRO_SENSITIVITY * -100)
                dy = int(gx * GYRO_SENSITIVITY * 100)
                if DEBUG:
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

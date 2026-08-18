#!/usr/bin/env python3
"""
sdl3_gamepad.py
Liaisons ctypes minimalistes vers libSDL3 pour lire l'état d'une manette
(boutons, axes, pavés tactiles, gyroscope). Utilisé par sc2_sdl3_mapper.py
(mapping en conditions réelles) et sc2_mapper_gui.py (interface de config).
"""

import ctypes
import ctypes.util

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


class SDL3Gamepad:
    """Enveloppe simple autour d'une manette SDL3 ouverte."""

    def __init__(self, enable_gyro=False):
        libname = ctypes.util.find_library("SDL3") or "libSDL3.so.0"
        try:
            self.sdl = ctypes.CDLL(libname)
        except OSError as exc:
            raise RuntimeError(
                f"Impossible de charger {libname}. Installe le paquet 'sdl3' (pacman -S sdl3)."
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
        """Initialise SDL, ouvre la première manette détectée. Retourne son nom."""
        flags = SDL_INIT_GAMEPAD | (SDL_INIT_SENSOR if self.enable_gyro else 0)
        if not self.sdl.SDL_Init(flags):
            raise RuntimeError("Échec SDL_Init : " + self.sdl.SDL_GetError().decode(errors="replace"))

        count = ctypes.c_int(0)
        ids = self.sdl.SDL_GetGamepads(ctypes.byref(count))
        if count.value == 0:
            raise RuntimeError("Aucune manette détectée par SDL3.")

        self.gamepad = self.sdl.SDL_OpenGamepad(ids[0])
        if not self.gamepad:
            raise RuntimeError("Échec ouverture manette : " + self.sdl.SDL_GetError().decode(errors="replace"))

        name = self.sdl.SDL_GetGamepadName(self.gamepad)
        name_str = name.decode(errors="replace") if name else "inconnue"

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
        """Retourne (ok, down, x, y, pressure) pour un doigt sur un pavé donné."""
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
        """Retourne (ok, gx, gy, gz) en rad/s."""
        if not self.enable_gyro:
            return False, 0.0, 0.0, 0.0
        data = (ctypes.c_float * 3)()
        ok = self.sdl.SDL_GetGamepadSensorData(self.gamepad, SDL_SENSOR_GYRO, data, 3)
        return bool(ok), data[0], data[1], data[2]

    def rumble(self, low_freq, high_freq, duration_ms):
        """Déclenche une vibration (retour haptique). Intensités 0-65535."""
        return bool(self.sdl.SDL_RumbleGamepad(self.gamepad, low_freq, high_freq, duration_ms))

    def close(self):
        if self.gamepad:
            self.sdl.SDL_CloseGamepad(self.gamepad)
        self.sdl.SDL_Quit()

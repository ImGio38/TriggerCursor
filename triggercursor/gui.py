#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import threading
import urllib.request
import urllib.error
import json
import shutil
import shlex
import customtkinter as ctk
from tkinter import messagebox

HOST = "http://127.0.0.1:8080"

# Standard Keyboard Keys Mapping (Key Name: (Linux Code, Windows Code))
KEY_MAP = {
    "Space": (57, 0x20),
    "Enter": (28, 0x0D),
    "Esc": (1, 0x1B),
    "Backspace": (14, 0x08),
    "Tab": (15, 0x09),
    "Left Shift": (42, 0xA0),
    "Left Ctrl": (29, 0xA2),
    "Left Alt": (56, 0xA4),
    "Right Shift": (54, 0xA1),
    "Right Ctrl": (97, 0xA3),
    "Right Alt": (100, 0xA5),
    "Windows/Super": (125, 0x5B),
    "Up": (103, 0x26),
    "Down": (108, 0x28),
    "Left": (105, 0x25),
    "Right": (106, 0x27),
}

# Add letters A-Z
linux_letter_map = {
    'a': 30, 'b': 48, 'c': 46, 'd': 32, 'e': 18, 'f': 33, 'g': 34, 'h': 35, 'i': 23, 'j': 36,
    'k': 37, 'l': 38, 'm': 50, 'n': 49, 'o': 24, 'p': 25, 'q': 16, 'r': 19, 's': 31, 't': 20,
    'u': 22, 'v': 47, 'w': 17, 'x': 45, 'y': 21, 'z': 44
}
for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    KEY_MAP[char] = (linux_letter_map[char.lower()], ord(char))

# Add numbers 0-9
for num in "1234567890":
    val = int(num)
    linux_code = 11 if val == 0 else val + 1
    KEY_MAP[num] = (linux_code, ord(num))

# Add F1-F12 keys
linux_f_map = {1:59, 2:60, 3:61, 4:62, 5:63, 6:64, 7:65, 8:66, 9:67, 10:68, 11:87, 12:88}
for i in range(1, 13):
    KEY_MAP[f"F{i}"] = (linux_f_map[i], 0x70 + i - 1)


def parse_macro_string(macro_str, is_windows=None):
    if is_windows is None:
        is_windows = sys.platform.startswith("win32")
    idx = 1 if is_windows else 0

    macro_str = macro_str.strip()
    if not macro_str:
        return [], []

    # Comma-separated action list: e.g. Down:Left Ctrl, Delay:50, Down:C, Up:C, Up:Left Ctrl
    if any(prefix in macro_str for prefix in ["Down:", "Up:", "Delay:", "Key:"]):
        press_actions = []
        parts = [p.strip() for p in macro_str.split(",")]
        for part in parts:
            if ":" not in part:
                continue
            action_type, val_name = part.split(":", 1)
            action_type = action_type.strip().lower()
            val_name = val_name.strip()
            
            if action_type == "delay":
                try:
                    press_actions.append(f"5:{int(val_name)}")
                except ValueError:
                    pass
            elif action_type == "down":
                if val_name in KEY_MAP:
                    press_actions.append(f"3:{KEY_MAP[val_name][idx]}")
                elif val_name.lower() == "left click":
                    press_actions.append("1:1")
                elif val_name.lower() == "right click":
                    press_actions.append("1:2")
                elif val_name.lower() == "middle click":
                    press_actions.append("1:3")
            elif action_type == "up":
                if val_name in KEY_MAP:
                    press_actions.append(f"4:{KEY_MAP[val_name][idx]}")
                elif val_name.lower() == "left click":
                    press_actions.append("2:1")
                elif val_name.lower() == "right click":
                    press_actions.append("2:2")
                elif val_name.lower() == "middle click":
                    press_actions.append("2:3")
            elif action_type == "key":
                if val_name in KEY_MAP:
                    press_actions.append(f"3:{KEY_MAP[val_name][idx]}")
                    press_actions.append("5:10")
                    press_actions.append(f"4:{KEY_MAP[val_name][idx]}")
        return press_actions, []

    # Standard combinations (e.g. Ctrl+C or Alt+Tab)
    if "+" in macro_str:
        keys = [k.strip() for k in macro_str.split("+")]
        valid = True
        for k in keys:
            matched = False
            for km_name in KEY_MAP:
                if km_name.lower() == k.lower():
                    matched = True
                    break
            if not matched:
                valid = False
                break
        
        if valid:
            press_actions = []
            release_actions = []
            for k in keys:
                for km_name in KEY_MAP:
                    if km_name.lower() == k.lower():
                        code = KEY_MAP[km_name][idx]
                        press_actions.append(f"3:{code}")
                        release_actions.insert(0, f"4:{code}")
                        break
            return press_actions + ["5:10"] + release_actions, []

    # Single hold key (e.g. Space)
    for km_name in KEY_MAP:
        if km_name.lower() == macro_str.lower():
            code = KEY_MAP[km_name][idx]
            return [f"3:{code}"], [f"4:{code}"]

    # String typing sequence
    press_actions = []
    for char in macro_str:
        char_upper = char.upper()
        if char_upper in KEY_MAP:
            code = KEY_MAP[char_upper][idx]
            press_actions.append(f"3:{code}")
            press_actions.append("5:10")
            press_actions.append(f"4:{code}")
            press_actions.append("5:20")
    return press_actions, []


def actions_to_summary(press_list, release_list):
    is_windows = sys.platform.startswith("win32")
    idx = 1 if is_windows else 0
    
    def key_name(code):
        for name, codes in KEY_MAP.items():
            if codes[idx] == code:
                return name
        return f"Key {code}"

    if press_list == ["1:1"] and release_list == ["2:1"]:
        return "Left Click"
    if press_list == ["1:2"] and release_list == ["2:2"]:
        return "Right Click"
    if press_list == ["1:3"] and release_list == ["2:3"]:
        return "Middle Click"
    
    if len(press_list) == 1 and len(release_list) == 1:
        try:
            p_type, p_val = map(int, press_list[0].split(":"))
            r_type, r_val = map(int, release_list[0].split(":"))
            if p_type == 3 and r_type == 4 and p_val == r_val:
                return f"Key Hold ({key_name(p_val)})"
        except Exception:
            pass
            
    if len(release_list) == 0 and len(press_list) > 2:
        try:
            downs = []
            ups = []
            for act in press_list:
                t, v = map(int, act.split(":"))
                if t == 3: downs.append(v)
                elif t == 4: ups.append(v)
            if len(downs) == len(ups) and downs == ups[::-1]:
                names = [key_name(d) for d in downs]
                return " + ".join(names)
        except Exception:
            pass

    if not press_list and not release_list:
        return "Disabled"
        
    return "Custom Macro"


def actions_to_entry_str(press_list, release_list):
    is_windows = sys.platform.startswith("win32")
    idx = 1 if is_windows else 0
    
    def key_name(code):
        for name, codes in KEY_MAP.items():
            if codes[idx] == code:
                return name
        return f"Key {code}"

    if len(release_list) == 0 and len(press_list) > 2:
        try:
            downs = []
            ups = []
            for act in press_list:
                t, v = map(int, act.split(":"))
                if t == 3: downs.append(v)
                elif t == 4: ups.append(v)
            if len(downs) == len(ups) and downs == ups[::-1]:
                names = [key_name(d) for d in downs]
                return "+".join(names)
        except Exception:
            pass
            
    res = []
    for act in press_list:
        try:
            t, v = map(int, act.split(":"))
            if t == 1: res.append("Down:Left Click" if v==1 else ("Down:Right Click" if v==2 else "Down:Middle Click"))
            elif t == 2: res.append("Up:Left Click" if v==1 else ("Up:Right Click" if v==2 else "Up:Middle Click"))
            elif t == 3: res.append(f"Down:{key_name(v)}")
            elif t == 4: res.append(f"Up:{key_name(v)}")
            elif t == 5: res.append(f"Delay:{v}")
        except Exception:
            pass
    return ", ".join(res)


BUTTONS = [
    "Button A (South)",
    "Button B (East)",
    "Button X (West)",
    "Button Y (North)",
    "Left Bumper (LB)",
    "Right Bumper (RB)",
    "Left Trigger (LT)",
    "Right Trigger (RT)",
    "Left Stick Click (LS)",
    "Right Stick Click (RS)",
    "Back / Share",
    "Start / Options",
    "D-pad Up",
    "D-pad Down",
    "D-pad Left",
    "D-pad Right"
]

BUTTON_CANVAS_CONFIG = {
    # idx: (type, coords, label)
    0: ("circle", (250, 100, 9), "A"),
    1: ("circle", (270, 80, 9), "B"),
    2: ("circle", (230, 80, 9), "X"),
    3: ("circle", (250, 60, 9), "Y"),
    4: ("rect", (75, 30, 140, 45), "LB"),
    5: ("rect", (260, 30, 325, 45), "RB"),
    6: ("poly", (75, 8, 130, 8, 120, 24, 85, 24), "LT"),
    7: ("poly", (270, 8, 325, 8, 315, 24, 280, 24), "RT"),
    8: ("circle", (120, 80, 14), "LS"),
    9: ("circle", (210, 125, 14), "RS"),
    10: ("oval", (165, 75, 177, 83), "◀"),
    11: ("oval", (223, 75, 235, 83), "▶"),
    12: ("rect", (150, 105, 160, 118), "▲"),
    13: ("rect", (150, 132, 160, 145), "▼"),
    14: ("rect", (130, 120, 143, 130), "◀"),
    15: ("rect", (167, 120, 180, 130), "▶"),
}


def get_user_data_dir():
    if sys.platform.startswith("win32"):
        base = os.getenv("APPDATA", os.path.expanduser("~"))
        path = os.path.join(base, "TriggerCursor")
    else:
        base = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        path = os.path.join(base, "triggercursor")
    os.makedirs(path, exist_ok=True)
    return path


class ScrollableDropdown(ctk.CTkToplevel):
    def __init__(self, parent_widget, values, callback, width=200, height=180):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.withdraw()
        self.overrideredirect(True)
        self.values = values
        self.callback = callback
        
        self.frame = ctk.CTkScrollableFrame(self, width=width, height=height, corner_radius=8, fg_color="#1e293b", label_text="")
        self.frame.pack(fill="both", expand=True)
        
        for val in self.values:
            btn = ctk.CTkButton(
                self.frame, 
                text=val, 
                fg_color="transparent", 
                hover_color="#334155", 
                text_color="#f8fafc",
                anchor="w",
                corner_radius=4,
                height=26,
                command=lambda v=val: self.select_val(v)
            )
            btn.pack(fill="x", pady=1)

        # Close when focus is lost
        self.bind("<FocusOut>", lambda e: self.close_menu())
        
        # Position and display
        self.after(10, self.show_menu)

    def show_menu(self):
        self.deiconify()
        self.focus_force()

    def select_val(self, val):
        self.callback(val)
        self.close_menu()

    def close_menu(self):
        try:
            self.parent_widget.dropdown_closed()
            self.destroy()
        except Exception:
            pass


class ScrollableOptionMenu(ctk.CTkButton):
    def __init__(self, master, values, command=None, **kwargs):
        self.values = values
        self.command = command
        self.current_value = values[0] if values else ""
        self.last_close_time = 0
        
        super().__init__(
            master, 
            text=self.current_value + "   ▼", 
            command=self.open_dropdown, 
            fg_color="#334155",
            hover_color="#475569",
            anchor="w",
            **kwargs
        )
        self.dropdown_window = None

    def open_dropdown(self):
        if time.time() - self.last_close_time < 0.15:
            return

        if self.dropdown_window and self.dropdown_window.winfo_exists():
            self.dropdown_window.close_menu()
            return

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = self.winfo_width()
        
        self.dropdown_window = ScrollableDropdown(self, self.values, self.on_select, width=w-20, height=180)
        self.dropdown_window.geometry(f"{w}x180+{x}+{y}")

    def on_select(self, val):
        self.current_value = val
        self.configure(text=val + "   ▼")
        if self.command:
            self.command(val)

    def dropdown_closed(self):
        self.last_close_time = time.time()

    def set(self, val):
        self.current_value = val
        self.configure(text=val + "   ▼")

    def get(self):
        return self.current_value


class TriggerCursorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configure Window
        self.title("TriggerCursor Dashboard")
        self.geometry("480x800")
        self.resizable(False, True)
        self.minsize(480, 500)
        
        # Set Modern Dark Theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        self.daemon_proc = None
        self.selected_button_idx = 0
        self.hovered_button_idx = -1
        self._updating_sliders = False
        self._update_timer = None
        
        # Determine standard directories
        self.package_dir = os.path.dirname(os.path.abspath(__file__))
        self.user_data_dir = get_user_data_dir()
        self.build_dir = os.path.join(self.user_data_dir, "build")
        
        # Determine CMake project source directory
        parent_dir = os.path.dirname(self.package_dir)
        if os.path.exists(os.path.join(parent_dir, "CMakeLists.txt")):
            self.source_dir = parent_dir
        elif os.path.exists(os.path.join(self.package_dir, "CMakeLists.txt")):
            self.source_dir = self.package_dir
        else:
            self.source_dir = parent_dir
            
        # 1. Compile C++ Daemon if missing
        self.ensure_daemon_binary()
        
        # 2. Register Linux Desktop Launcher (.desktop file)
        if sys.platform.startswith("linux"):
            self.register_desktop_launcher()

        # 3. Check for Linux Permissions
        self.permissions_ok = True
        if sys.platform.startswith("linux"):
            self.permissions_ok = os.access("/dev/uinput", os.W_OK)

        # 4. Start Daemon in background
        self.start_daemon()

        # 5. Build Desktop GUI Grid
        self.create_widgets()
        
        # Initialize Canvas Graphics
        self.init_controller_canvas()

        # Hook window close event
        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        
        # Start state poll loop
        self.after(500, self.poll_daemon)

    def is_user_in_input_group(self):
        try:
            groups_output = subprocess.check_output(["groups"]).decode()
            return "input" in groups_output.split()
        except Exception:
            return False

    def ensure_daemon_binary(self):
        if sys.platform.startswith("win32"):
            self.binary_path = os.path.join(self.build_dir, "Release", "trigger_cursor_daemon.exe")
            if not os.path.exists(self.binary_path):
                self.binary_path = os.path.join(self.build_dir, "trigger_cursor_daemon.exe")
            if not os.path.exists(self.binary_path):
                self.binary_path = os.path.join(self.build_dir, "Debug", "trigger_cursor_daemon.exe")
        else:
            self.binary_path = os.path.join(self.build_dir, "trigger_cursor_daemon")

        if not os.path.exists(self.binary_path):
            print("[TriggerCursor] Daemon binary not found. Compiling now...")
            try:
                os.makedirs(self.build_dir, exist_ok=True)
                if sys.platform.startswith("win32"):
                    subprocess.run(["cmake", "-B", self.build_dir, "-S", self.source_dir], cwd=self.build_dir, check=True)
                    subprocess.run(["cmake", "--build", self.build_dir, "--config", "Release"], cwd=self.build_dir, check=True)
                    self.binary_path = os.path.join(self.build_dir, "Release", "trigger_cursor_daemon.exe")
                else:
                    subprocess.run(["cmake", "-B", self.build_dir, "-S", self.source_dir, "-DCMAKE_BUILD_TYPE=Release"], cwd=self.build_dir, check=True)
                    subprocess.run(["cmake", "--build", self.build_dir], cwd=self.build_dir, check=True)
                print("[TriggerCursor] Compilation successful!")
            except Exception as e:
                print(f"[TriggerCursor] Failed to compile daemon: {e}")

    def register_desktop_launcher(self):
        desktop_dir = os.path.expanduser("~/.local/share/applications")
        os.makedirs(desktop_dir, exist_ok=True)
        launcher_path = os.path.join(desktop_dir, "trigger-cursor.desktop")
        
        if shutil.which("triggercursor"):
            exec_command = "triggercursor"
        else:
            script_path = os.path.abspath(__file__)
            exec_command = f"python3 {script_path}"
            
        desktop_entry = f"""[Desktop Entry]
Type=Application
Name=TriggerCursor
Comment=Low-latency Controller to Mouse Emulator
Exec={exec_command}
Icon=input-gaming
Terminal=false
Categories=Utility;
"""
        try:
            with open(launcher_path, "w") as f:
                f.write(desktop_entry)
            if not shutil.which("triggercursor"):
                script_path = os.path.abspath(__file__)
                os.chmod(script_path, 0o755)
        except Exception as e:
            print(f"[TriggerCursor] Failed to register desktop launcher: {e}")

    def start_daemon(self):
        if not os.path.exists(self.binary_path):
            return
            
        print("[TriggerCursor] Starting background C++ daemon...")
        
        # Clean up any orphaned daemon processes first
        if sys.platform.startswith("win32"):
            try:
                subprocess.run(["taskkill", "/F", "/IM", "trigger_cursor_daemon.exe"], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        else:
            try:
                subprocess.run(["killall", "-9", "trigger_cursor_daemon"], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        try:
            log_file = os.path.join(self.user_data_dir, "daemon.log")
            self.daemon_log = open(log_file, "a")
            
            if sys.platform.startswith("win32"):
                self.daemon_proc = subprocess.Popen(
                    [self.binary_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=self.user_data_dir
                )
            else:
                if self.permissions_ok:
                    self.daemon_proc = subprocess.Popen(
                        [self.binary_path],
                        stdout=self.daemon_log,
                        stderr=self.daemon_log,
                        cwd=self.user_data_dir
                    )
                else:
                    self.daemon_proc = subprocess.Popen(
                        ["pkexec", self.binary_path],
                        stdout=self.daemon_log,
                        stderr=self.daemon_log,
                        cwd=self.user_data_dir
                    )
        except Exception as e:
            print(f"[TriggerCursor] Failed to start daemon: {e}")

    def fix_permissions(self):
        cmd = 'echo "KERNEL==\\"uinput\\", GROUP=\\"input\\", MODE=\\"0660\\", TAG+=\\"uaccess\\"" > /etc/udev/rules.d/99-trigger-cursor.rules && udevadm control --reload-rules && udevadm trigger'
        try:
            subprocess.run(["pkexec", "sh", "-c", cmd], check=True)
            self.permissions_ok = True
            
            if hasattr(self, 'warning_frame'):
                self.warning_frame.pack_forget()
            
            if self.daemon_proc:
                self.daemon_proc.terminate()
                self.daemon_proc.wait()
            self.start_daemon()
            
        except Exception as e:
            print(f"[TriggerCursor] Failed to apply permissions: {e}")

    def create_widgets(self):
        # Main Scrollable Container to fit all screen sizes and resolutions
        self.scrollable_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_container.pack(fill="both", expand=True, padx=0, pady=0)

        # Header Label
        self.header = ctk.CTkLabel(self.scrollable_container, text="TRIGGER CURSOR", font=ctk.CTkFont(family="Outfit", size=24, weight="bold"))
        self.header.pack(pady=(15, 2))
        
        self.sub_header = ctk.CTkLabel(self.scrollable_container, text="Zero-Overhead Input Emulator", font=ctk.CTkFont(family="Outfit", size=12), text_color="#94a3b8")
        self.sub_header.pack(pady=(0, 10))

        # Permission Warning Bar
        self.warning_frame = ctk.CTkFrame(self.scrollable_container, fg_color="#7f1d1d", height=45, corner_radius=8)
        self.warning_lbl = ctk.CTkLabel(
            self.warning_frame, 
            text="⚠️ Permissions missing (run as root).",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#fca5a5"
        )
        self.warning_lbl.pack(side="left", padx=15, pady=5)
        
        self.fix_btn = ctk.CTkButton(
            self.warning_frame,
            text="Authorize",
            width=80,
            height=24,
            fg_color="#ef4444",
            hover_color="#dc2626",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self.fix_permissions
        )
        self.fix_btn.pack(side="right", padx=15, pady=5)

        if not self.permissions_ok:
            self.warning_frame.pack(fill="x", padx=20, pady=(0, 8))

        # Emulation Toggle Switch Card
        self.status_card = ctk.CTkFrame(self.scrollable_container, fg_color="#1e1b4b", corner_radius=12)
        self.status_card.pack(fill="x", padx=20, pady=4)

        self.status_title = ctk.CTkLabel(self.status_card, text="Emulation Active", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_title.pack(side="left", padx=20, pady=10)

        self.toggle_switch = ctk.CTkSwitch(self.status_card, text="", command=self.toggle_daemon, onvalue=True, offvalue=False)
        self.toggle_switch.pack(side="right", padx=20, pady=10)

        # Sliders Settings Card
        self.sliders_card = ctk.CTkFrame(self.scrollable_container, corner_radius=12)
        self.sliders_card.pack(fill="x", padx=20, pady=4)

        # Slider 1: Sensitivity
        self.sens_lbl = ctk.CTkLabel(self.sliders_card, text="Sensitivity: 5.0", font=ctk.CTkFont(weight="bold"))
        self.sens_lbl.pack(anchor="w", padx=20, pady=(10, 0))
        self.sens_slider = ctk.CTkSlider(self.sliders_card, from_=0.5, to=20.0, number_of_steps=39, command=self.on_slider_change)
        self.sens_slider.pack(fill="x", padx=20, pady=(2, 8))

        # Slider 2: Deadzone
        self.dz_lbl = ctk.CTkLabel(self.sliders_card, text="Deadzone: 20%", font=ctk.CTkFont(weight="bold"))
        self.dz_lbl.pack(anchor="w", padx=20)
        self.dz_slider = ctk.CTkSlider(self.sliders_card, from_=0.05, to=0.50, number_of_steps=45, command=self.on_slider_change)
        self.dz_slider.pack(fill="x", padx=20, pady=(2, 8))

        # Slider 3: Acceleration Curve Exponent
        self.curve_lbl = ctk.CTkLabel(self.sliders_card, text="Curve Power: 2.0 (Quadratic)", font=ctk.CTkFont(weight="bold"))
        self.curve_lbl.pack(anchor="w", padx=20)
        self.curve_slider = ctk.CTkSlider(self.sliders_card, from_=1.0, to=3.0, number_of_steps=20, command=self.on_slider_change)
        self.curve_slider.pack(fill="x", padx=20, pady=(2, 8))

        # Axis Inversion Toggles
        self.invert_frame = ctk.CTkFrame(self.sliders_card, fg_color="transparent")
        self.invert_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.invert_x_switch = ctk.CTkSwitch(self.invert_frame, text="Invert X Axis", command=self.trigger_config_update)
        self.invert_x_switch.pack(side="left")
        
        self.invert_y_switch = ctk.CTkSwitch(self.invert_frame, text="Invert Y Axis", command=self.trigger_config_update)
        self.invert_y_switch.pack(side="right")

        # Controller Button Programmer Card
        self.prog_card = ctk.CTkFrame(self.scrollable_container, corner_radius=12)
        self.prog_card.pack(fill="x", padx=20, pady=4)

        self.prog_title = ctk.CTkLabel(self.prog_card, text="Button Mapping Programmer", font=ctk.CTkFont(size=14, weight="bold"))
        self.prog_title.pack(anchor="w", padx=20, pady=(10, 2))

        # Controller Info & Refresh Frame
        self.controller_info_frame = ctk.CTkFrame(self.prog_card, fg_color="transparent")
        self.controller_info_frame.pack(fill="x", padx=20, pady=(0, 5))

        self.controller_info_lbl = ctk.CTkLabel(
            self.controller_info_frame, 
            text="Controller: Detecting...", 
            font=ctk.CTkFont(size=11), 
            text_color="#94a3b8"
        )
        self.controller_info_lbl.pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            self.controller_info_frame,
            text="⟳ Refresh",
            width=65,
            height=20,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self.refresh_controller
        )
        self.refresh_btn.pack(side="right")

        # Graphical Controller Canvas Map
        self.canvas = ctk.CTkCanvas(self.prog_card, width=400, height=200, bg="#0f172a", highlightthickness=0)
        self.canvas.pack(padx=20, pady=8)

        # Target Button Dropdown Select
        self.btn_select_lbl = ctk.CTkLabel(self.prog_card, text="Selected Button:", font=ctk.CTkFont(size=11, weight="bold"))
        self.btn_select_lbl.pack(anchor="w", padx=20)
        self.btn_select_menu = ScrollableOptionMenu(self.prog_card, values=BUTTONS, command=self.on_button_dropdown_change)
        self.btn_select_menu.pack(fill="x", padx=20, pady=(2, 6))

        # Preset Select
        self.preset_lbl = ctk.CTkLabel(self.prog_card, text="Preset Action:", font=ctk.CTkFont(size=11, weight="bold"))
        self.preset_lbl.pack(anchor="w", padx=20)
        self.preset_menu = ScrollableOptionMenu(
            self.prog_card, 
            values=["Disabled", "Left Click", "Right Click", "Middle Click", "Keyboard Key (Hold)", "Key Combo / Macro"],
            command=self.on_preset_dropdown_change
        )
        self.preset_menu.pack(fill="x", padx=20, pady=(2, 6))

        # Container for dynamic options
        self.dynamic_options_frame = ctk.CTkFrame(self.prog_card, fg_color="transparent")
        self.dynamic_options_frame.pack(fill="x", padx=20, pady=0)
        self.dynamic_options_frame.columnconfigure(0, weight=1)

        # 1. Key Hold option widgets
        self.key_frame = ctk.CTkFrame(self.dynamic_options_frame, fg_color="transparent")
        self.key_frame.grid(row=0, column=0, sticky="nsew")
        self.key_frame_lbl = ctk.CTkLabel(self.key_frame, text="Select Keyboard Key:", font=ctk.CTkFont(size=11, weight="bold"))
        self.key_frame_lbl.pack(anchor="w")
        self.key_select_menu = ScrollableOptionMenu(self.key_frame, values=list(KEY_MAP.keys()), command=lambda _: self.apply_selected_mapping())
        self.key_select_menu.pack(fill="x", pady=(2, 6))

        # 2. Key Combo / Macro option widgets
        self.macro_frame = ctk.CTkFrame(self.dynamic_options_frame, fg_color="transparent")
        self.macro_frame.grid(row=0, column=0, sticky="nsew")
        self.macro_frame_lbl = ctk.CTkLabel(self.macro_frame, text="Macro Input (e.g. Ctrl+C or A,Delay:100,B):", font=ctk.CTkFont(size=11, weight="bold"))
        self.macro_frame_lbl.pack(anchor="w")
        
        self.macro_entry = ctk.CTkEntry(self.macro_frame, placeholder_text="e.g. Ctrl+C or Space or Down:Left Ctrl, Delay:50, Up:Left Ctrl")
        self.macro_entry.pack(fill="x", pady=2)
        self.macro_entry.bind("<KeyRelease>", self.on_macro_text_change)
        self.macro_entry.bind("<Return>", lambda e: self.apply_selected_mapping())
        self.macro_entry.bind("<FocusOut>", lambda e: self.apply_selected_mapping())

        self.macro_preview_lbl = ctk.CTkLabel(self.macro_frame, text="Preview: []", font=ctk.CTkFont(size=10), text_color="#94a3b8", wraplength=400, justify="left")
        self.macro_preview_lbl.pack(anchor="w", pady=(2, 6))

        # Hide elements by default
        self.key_frame.grid_remove()
        self.macro_frame.grid_remove()

        # Uninstall Button
        self.uninstall_btn = ctk.CTkButton(
            self.scrollable_container,
            text="Uninstall Software",
            fg_color="#7f1d1d",
            hover_color="#b91c1c",
            text_color="#fca5a5",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.confirm_uninstall
        )
        self.uninstall_btn.pack(fill="x", padx=20, pady=(8, 12))

    def init_controller_canvas(self):
        self.canvas.delete("all")
        
        # Controller body outline
        body_points = [
            (80, 45), (120, 38), (280, 38), (320, 45), 
            (355, 90), (365, 140), (320, 185), (280, 170), 
            (200, 178), (120, 170), (80, 185), (35, 140), (45, 90)
        ]
        flat_body = [coord for pt in body_points for coord in pt]
        self.canvas.create_polygon(flat_body, fill="#1e293b", outline="#475569", width=2, smooth=True)
        
        # D-pad backing (grey cross)
        self.canvas.create_rectangle(148, 120, 162, 130, fill="#334155", outline="")
        self.canvas.create_rectangle(153, 115, 157, 135, fill="#334155", outline="")

        self.button_shapes = {}
        self.button_texts = {}

        # Draw all interactive button shapes once
        for idx in range(16):
            if idx not in BUTTON_CANVAS_CONFIG:
                continue
                
            btype, coords, label = BUTTON_CANVAS_CONFIG[idx]
            tag = f"btn_{idx}"
            
            if btype == "circle":
                x, y, r = coords
                shape_id = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="#334155", outline="#475569", width=1.5, tags=tag)
                text_id = self.canvas.create_text(x, y, text=label, fill="#94a3b8", font=("Outfit", 8, "bold"), tags=tag)
            elif btype == "oval":
                x1, y1, x2, y2 = coords
                shape_id = self.canvas.create_oval(x1, y1, x2, y2, fill="#334155", outline="#475569", width=1.5, tags=tag)
                text_id = self.canvas.create_text((x1+x2)/2, (y1+y2)/2, text=label, fill="#94a3b8", font=("Outfit", 6, "bold"), tags=tag)
            elif btype == "rect":
                x1, y1, x2, y2 = coords
                shape_id = self.canvas.create_rectangle(x1, y1, x2, y2, fill="#334155", outline="#475569", width=1.5, tags=tag)
                text_id = self.canvas.create_text((x1+x2)/2, (y1+y2)/2, text=label, fill="#94a3b8", font=("Outfit", 7, "bold"), tags=tag)
            elif btype == "poly":
                shape_id = self.canvas.create_polygon(coords, fill="#334155", outline="#475569", width=1.5, tags=tag)
                xs = coords[0::2]
                ys = coords[1::2]
                cx = sum(xs)/len(xs)
                cy = sum(ys)/len(ys)
                text_id = self.canvas.create_text(cx, cy, text=label, fill="#94a3b8", font=("Outfit", 7, "bold"), tags=tag)

            self.button_shapes[idx] = shape_id
            self.button_texts[idx] = text_id

            # Bind events once
            self.canvas.tag_bind(tag, "<Button-1>", lambda event, i=idx: self.select_button_from_canvas(i))
            self.canvas.tag_bind(tag, "<Enter>", lambda event, i=idx: self.hover_button_canvas(i, True))
            self.canvas.tag_bind(tag, "<Leave>", lambda event, i=idx: self.hover_button_canvas(i, False))
            
        self.update_controller_canvas()

    def update_controller_canvas(self):
        if not hasattr(self, "button_shapes"):
            return
            
        for idx in range(16):
            if idx not in self.button_shapes:
                continue
                
            is_selected = (idx == self.selected_button_idx)
            is_hovered = (self.hovered_button_idx == idx)
            
            if is_selected:
                fill_color = "#10b981" # emerald-500
                outline_color = "#60a5fa" # blue-400
                text_color = "#ffffff"
            elif is_hovered:
                fill_color = "#475569" # slate-600
                outline_color = "#3b82f6" # blue-500
                text_color = "#f8fafc"
            else:
                fill_color = "#334155" # slate-700
                outline_color = "#475569" # slate-600
                text_color = "#94a3b8"

            self.canvas.itemconfig(self.button_shapes[idx], fill=fill_color, outline=outline_color)
            self.canvas.itemconfig(self.button_texts[idx], fill=text_color)

    def hover_button_canvas(self, idx, is_hovered):
        if is_hovered:
            self.hovered_button_idx = idx
        else:
            if self.hovered_button_idx == idx:
                self.hovered_button_idx = -1
        self.update_controller_canvas()

    def select_button_from_canvas(self, idx):
        self.selected_button_idx = idx
        self.btn_select_menu.set(BUTTONS[idx])
        self.update_controller_canvas()
        self.update_programmer_ui_from_current()

    def on_button_dropdown_change(self, choice):
        self.selected_button_idx = BUTTONS.index(choice)
        self.update_controller_canvas()
        self.update_programmer_ui_from_current()

    def on_preset_dropdown_change(self, choice):
        self.show_preset_controls(choice)
        if choice in ("Disabled", "Left Click", "Right Click", "Middle Click"):
            self.apply_selected_mapping()

    def on_macro_text_change(self, event):
        self.update_macro_preview(self.macro_entry.get())

    def update_macro_preview(self, text):
        press_list, release_list = parse_macro_string(text)
        if not press_list and not release_list:
            self.macro_preview_lbl.configure(text="Preview: [Empty/Disabled]")
            return
            
        is_windows = sys.platform.startswith("win32")
        idx = 1 if is_windows else 0
        
        def act_name(act_str):
            t, v = map(int, act_str.split(":"))
            if t == 1: return "Mouse Down:" + ("Left" if v==1 else ("Right" if v==2 else "Middle"))
            if t == 2: return "Mouse Up:" + ("Left" if v==1 else ("Right" if v==2 else "Middle"))
            if t == 3:
                for name, codes in KEY_MAP.items():
                    if codes[idx] == v: return f"Key Down:{name}"
                return f"Key Down:{v}"
            if t == 4:
                for name, codes in KEY_MAP.items():
                    if codes[idx] == v: return f"Key Up:{name}"
                return f"Key Up:{v}"
            if t == 5: return f"Delay:{v}ms"
            return "Unknown"

        preview_parts = [act_name(p) for p in press_list]
        if release_list:
            preview_parts.append("--- On Release ---")
            preview_parts.extend([act_name(r) for r in release_list])
            
        self.macro_preview_lbl.configure(text="Preview: [" + ", ".join(preview_parts) + "]")

    def show_preset_controls(self, preset_type):
        self.key_frame.grid_remove()
        self.macro_frame.grid_remove()
        
        if preset_type == "Keyboard Key (Hold)":
            self.key_frame.grid()
        elif preset_type == "Key Combo / Macro":
            self.macro_frame.grid()

    def update_programmer_ui_from_current(self):
        if not hasattr(self, "current_mappings") or self.selected_button_idx >= len(self.current_mappings):
            return
            
        mapping = self.current_mappings[self.selected_button_idx]
        press_str = mapping.get("press", "")
        release_str = mapping.get("release", "")
        
        press_list = [p for p in press_str.split(",") if p]
        release_list = [r for r in release_str.split(",") if r]
        
        summary = actions_to_summary(press_list, release_list)
        
        if summary == "Disabled":
            self.preset_menu.set("Disabled")
            self.show_preset_controls("Disabled")
        elif summary in ("Left Click", "Right Click", "Middle Click"):
            self.preset_menu.set(summary)
            self.show_preset_controls(summary)
        elif summary.startswith("Key Hold"):
            self.preset_menu.set("Keyboard Key (Hold)")
            key_name = summary.split("(")[1].split(")")[0]
            if key_name in KEY_MAP:
                self.key_select_menu.set(key_name)
            self.show_preset_controls("Keyboard Key (Hold)")
        else:
            self.preset_menu.set("Key Combo / Macro")
            entry_str = actions_to_entry_str(press_list, release_list)
            self.macro_entry.delete(0, "end")
            self.macro_entry.insert(0, entry_str)
            self.show_preset_controls("Key Combo / Macro")
            self.update_macro_preview(entry_str)

    def apply_selected_mapping(self):
        preset = self.preset_menu.get()
        btn_idx = self.selected_button_idx
        
        press_list = []
        release_list = []
        
        if preset == "Disabled":
            pass
        elif preset == "Left Click":
            press_list = ["1:1"]
            release_list = ["2:1"]
        elif preset == "Right Click":
            press_list = ["1:2"]
            release_list = ["2:2"]
        elif preset == "Middle Click":
            press_list = ["1:3"]
            release_list = ["2:3"]
        elif preset == "Keyboard Key (Hold)":
            key = self.key_select_menu.get()
            is_windows = sys.platform.startswith("win32")
            idx = 1 if is_windows else 0
            code = KEY_MAP[key][idx]
            press_list = [f"3:{code}"]
            release_list = [f"4:{code}"]
        elif preset == "Key Combo / Macro":
            macro_text = self.macro_entry.get()
            press_list, release_list = parse_macro_string(macro_text)
            
        press_param = ",".join(press_list) if press_list else "none"
        release_param = ",".join(release_list) if release_list else "none"
        
        url = f"{HOST}/set_mapping?btn={btn_idx}&press={press_param}&release={release_param}"
        
        def do_save():
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    pass
                self.after(0, lambda: self.handle_save_success(btn_idx, press_list, release_list))
            except Exception as e:
                print(f"[TriggerCursor] Failed to save mapping: {e}")
                
        threading.Thread(target=do_save, daemon=True).start()

    def handle_save_success(self, btn_idx, press_list, release_list):
        if hasattr(self, "current_mappings") and btn_idx < len(self.current_mappings):
            self.current_mappings[btn_idx]["press"] = ",".join(press_list)
            self.current_mappings[btn_idx]["release"] = ",".join(release_list)
        self.update_controller_canvas()

    def confirm_uninstall(self):
        confirmed = messagebox.askyesno(
            "Uninstall TriggerCursor",
            "Are you sure you want to completely uninstall this software?\n\n"
            "This will:\n"
            "- Stop and terminate the C++ daemon\n"
            "- Remove the application menu desktop shortcut launcher\n"
            "- Delete the udev rules for controller access (requires authorization)\n"
            "- Completely delete all project source code, configurations, and binaries."
        )
        if confirmed:
            self.perform_uninstall()

    def perform_uninstall(self):
        import shlex
        
        # 1. Stop Daemon Process
        if self.daemon_proc:
            print("[TriggerCursor] Terminating background C++ daemon...")
            try:
                if sys.platform.startswith("linux") and not self.permissions_ok:
                    subprocess.run(["pkexec", "kill", str(self.daemon_proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    self.daemon_proc.terminate()
                    self.daemon_proc.wait()
            except Exception as e:
                print(f"[TriggerCursor] Failed to stop daemon: {e}")

        # Force kill any remaining daemons
        if sys.platform.startswith("win32"):
            try:
                subprocess.run(["taskkill", "/F", "/IM", "trigger_cursor_daemon.exe"], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        else:
            try:
                subprocess.run(["killall", "-9", "trigger_cursor_daemon"], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        # 2. Remove desktop launcher
        if sys.platform.startswith("linux"):
            desktop_path = os.path.expanduser("~/.local/share/applications/trigger-cursor.desktop")
            if os.path.exists(desktop_path):
                try:
                    os.remove(desktop_path)
                    print("[TriggerCursor] Removed desktop entry.")
                except Exception as e:
                    print(f"[TriggerCursor] Failed to remove desktop entry: {e}")

        # 3. Remove udev rules on Linux
        if sys.platform.startswith("linux"):
            udev_rule = "/etc/udev/rules.d/99-trigger-cursor.rules"
            if os.path.exists(udev_rule):
                print("[TriggerCursor] Removing udev rules (requires authorization)...")
                cmd = f"rm -f {udev_rule} && udevadm control --reload-rules && udevadm trigger"
                try:
                    subprocess.run(["pkexec", "sh", "-c", cmd], check=True)
                    print("[TriggerCursor] Removed udev rules successfully.")
                except Exception as e:
                    print(f"[TriggerCursor] Failed to remove udev rules: {e}")

        # 4. Show success message
        messagebox.showinfo(
            "Uninstall Complete",
            "Uninstall complete! The application directory will now be deleted, and the program will exit."
        )

        # 5. Self-destruct package directory and config folder
        try:
            quoted_package_dir = shlex.quote(self.package_dir)
            quoted_user_data_dir = shlex.quote(self.user_data_dir)
            if sys.platform.startswith("win32"):
                cmd = f'ping 127.0.0.1 -n 2 > nul & rmdir /s /q "{self.package_dir}" & rmdir /s /q "{self.user_data_dir}"'
                subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                cmd = f"sleep 0.2 && rm -rf {quoted_package_dir} && rm -rf {quoted_user_data_dir}"
                subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[TriggerCursor] Failed to launch self-destruct command: {e}")
            try:
                shutil.rmtree(self.package_dir)
                shutil.rmtree(self.user_data_dir)
            except Exception:
                pass

        self.destroy()

    def toggle_daemon(self):
        def do_toggle():
            try:
                req = urllib.request.Request(f"{HOST}/toggle")
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    self.after(0, lambda: self.update_switch_ui(data["enabled"]))
            except Exception:
                pass
        threading.Thread(target=do_toggle, daemon=True).start()

    def refresh_controller(self):
        def do_refresh():
            try:
                req = urllib.request.Request(f"{HOST}/refresh")
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    pass
            except Exception:
                pass
            self.after(0, self.poll_daemon)
        threading.Thread(target=do_refresh, daemon=True).start()

    def update_switch_ui(self, enabled):
        if enabled:
            self.status_title.configure(text="Emulation Active", text_color="#34d399")
            self.toggle_switch.select()
        else:
            self.status_title.configure(text="Emulation Paused (Sleep)", text_color="#ef4444")
            self.toggle_switch.deselect()

    def on_slider_change(self, val):
        if hasattr(self, "_updating_sliders") and self._updating_sliders:
            return
            
        sens = self.sens_slider.get()
        dz = self.dz_slider.get()
        curve = self.curve_slider.get()

        self.sens_lbl.configure(text=f"Sensitivity: {sens:.1f}")
        self.dz_lbl.configure(text=f"Deadzone: {int(dz*100)}%")

        curve_name = "(Linear)" if curve == 1.0 else ("(Quadratic)" if curve == 2.0 else ("(Cubic)" if curve == 3.0 else ""))
        self.curve_lbl.configure(text=f"Curve Power: {curve:.1f} {curve_name}")

        self.trigger_config_update()

    def trigger_config_update(self, *args):
        if hasattr(self, "_update_timer") and self._update_timer is not None:
            try:
                self.after_cancel(self._update_timer)
            except Exception:
                pass
        self._update_timer = self.after(50, self.push_config_updates)

    def push_config_updates(self, *args):
        self._update_timer = None
        sens = self.sens_slider.get()
        dz = self.dz_slider.get()
        curve = self.curve_slider.get()

        inv_x = 1 if self.invert_x_switch.get() else 0
        inv_y = 1 if self.invert_y_switch.get() else 0

        url = f"{HOST}/set?deadzone={dz:.2f}&sensitivity={sens:.1f}&curve_power={curve:.1f}&invert_x={inv_x}&invert_y={inv_y}"
        
        def do_update():
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=0.2) as resp:
                    pass
            except Exception:
                pass
                
        threading.Thread(target=do_update, daemon=True).start()

    def poll_daemon(self):
        if hasattr(self, "_polling") and self._polling:
            return
        self._polling = True

        def do_poll():
            try:
                req = urllib.request.Request(f"{HOST}/status")
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    self.after(0, lambda: self.handle_poll_response(data))
            except Exception as e:
                self.after(0, lambda: self.handle_poll_error(e))

        threading.Thread(target=do_poll, daemon=True).start()

    def handle_poll_response(self, data):
        self._polling = False
        try:
            self.update_switch_ui(data["enabled"])
            
            self._updating_sliders = True
            
            self.sens_slider.set(data["sensitivity"])
            self.sens_lbl.configure(text=f"Sensitivity: {data['sensitivity']:.1f}")
            
            self.dz_slider.set(data["deadzone"])
            self.dz_lbl.configure(text=f"Deadzone: {int(data['deadzone']*100)}%")
            
            if "curve_power" in data:
                self.curve_slider.set(data["curve_power"])
                curve = data["curve_power"]
                curve_name = "(Linear)" if curve == 1.0 else ("(Quadratic)" if curve == 2.0 else ("(Cubic)" if curve == 3.0 else ""))
                self.curve_lbl.configure(text=f"Curve Power: {curve:.1f} {curve_name}")
            
            if "invert_x" in data:
                if data["invert_x"]:
                    self.invert_x_switch.select()
                else:
                    self.invert_x_switch.deselect()
            if "invert_y" in data:
                if data["invert_y"]:
                    self.invert_y_switch.select()
                else:
                    self.invert_y_switch.deselect()
                    
            self._updating_sliders = False

            if "controller_name" in data and "controller_type" in data:
                c_name = data["controller_name"]
                c_type = data["controller_type"]
                if c_name != "None":
                    self.controller_info_lbl.configure(
                        text=f"Controller: {c_name} ({c_type} style)",
                        text_color="#34d399"
                    )
                else:
                    self.controller_info_lbl.configure(
                        text="Controller: No Controller Connected",
                        text_color="#ef4444"
                    )

            if "mappings" in data:
                first_load = not hasattr(self, "current_mappings")
                self.current_mappings = data["mappings"]
                if first_load:
                    self.update_programmer_ui_from_current()

            if hasattr(self, 'warning_frame'):
                self.warning_frame.pack_forget()
        except Exception:
            pass
        
        self.after(2000, self.poll_daemon)

    def handle_poll_error(self, err):
        self._polling = False
        try:
            self.status_title.configure(text="Connecting to Daemon...", text_color="#e2e8f0")
            if not self.permissions_ok and hasattr(self, 'warning_frame'):
                if not self.warning_frame.winfo_manager():
                    self.warning_frame.pack(fill="x", padx=20, pady=(0, 10), before=self.status_card)
        except Exception:
            pass
            
        self.after(2000, self.poll_daemon)

    def on_exit(self):
        print("[TriggerCursor] Stopping background C++ daemon...")
        if self.daemon_proc:
            try:
                self.daemon_proc.terminate()
                self.daemon_proc.wait()
            except Exception:
                pass
                
        # Force kill to ensure no orphaned daemon process remains on port 8080
        if sys.platform.startswith("win32"):
            try:
                subprocess.run(["taskkill", "/F", "/IM", "trigger_cursor_daemon.exe"], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        else:
            try:
                subprocess.run(["killall", "-9", "trigger_cursor_daemon"], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        if hasattr(self, "daemon_log"):
            try:
                self.daemon_log.close()
            except Exception:
                pass
        self.destroy()


def main():
    app = None
    try:
        app = TriggerCursorApp()
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[TriggerCursor] Interrupted by user. Exiting...")
        if app:
            app.on_exit()
    except Exception as e:
        print(f"[TriggerCursor] Unhandled exception: {e}")
        if app:
            try:
                app.on_exit()
            except Exception:
                pass
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import urllib.request
import urllib.error
import json
import shutil
import customtkinter as ctk
from tkinter import messagebox

HOST = "http://127.0.0.1:8080"

ACTIONS = {
    0: "Disabled",
    1: "Left Click",
    2: "Right Click",
    3: "Middle Click"
}
ACTION_REVERSE = {v: k for k, v in ACTIONS.items()}

def get_user_data_dir():
    if sys.platform.startswith("win32"):
        base = os.getenv("APPDATA", os.path.expanduser("~"))
        path = os.path.join(base, "TriggerCursor")
    else:
        base = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        path = os.path.join(base, "triggercursor")
    os.makedirs(path, exist_ok=True)
    return path

class TriggerCursorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configure Window
        self.title("TriggerCursor Dashboard")
        self.geometry("480x750")
        self.resizable(False, False)
        
        # Set Modern Dark Theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue") # Clean modern theme
        
        self.daemon_proc = None
        
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
            self.source_dir = parent_dir # Fallback
            
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
        
        # Hook window close event to shut down daemon cleanly
        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        
        # Start state poll loop
        self.after(500, self.poll_daemon)

    def is_user_in_input_group(self):
        try:
            # Check groups of current user
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
        
        try:
            log_file = os.path.join(self.user_data_dir, "daemon.log")
            self.daemon_log = open(log_file, "a") # Open in append mode
            
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
            # Execute with pkexec to prompt password natively in the GUI
            subprocess.run(["pkexec", "sh", "-c", cmd], check=True)
            self.permissions_ok = True
            
            # Hide the warning banner
            if hasattr(self, 'warning_frame'):
                self.warning_frame.pack_forget()
            
            # Restart daemon cleanly
            if self.daemon_proc:
                self.daemon_proc.terminate()
                self.daemon_proc.wait()
            self.start_daemon()
            
        except Exception as e:
            print(f"[TriggerCursor] Failed to apply permissions: {e}")

    def create_widgets(self):
        # Header Label
        self.header = ctk.CTkLabel(self, text="TRIGGER CURSOR", font=ctk.CTkFont(family="Outfit", size=24, weight="bold"))
        self.header.pack(pady=(20, 2))
        
        self.sub_header = ctk.CTkLabel(self, text="Zero-Overhead Input Emulator", font=ctk.CTkFont(family="Outfit", size=12), text_color="#94a3b8")
        self.sub_header.pack(pady=(0, 15))

        # Permission Warning Bar
        self.warning_frame = ctk.CTkFrame(self, fg_color="#7f1d1d", height=45, corner_radius=8)
        
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
            self.warning_frame.pack(fill="x", padx=20, pady=(0, 10))

        # Emulation Toggle Switch Card
        self.status_card = ctk.CTkFrame(self, fg_color="#1e1b4b", corner_radius=12)
        self.status_card.pack(fill="x", padx=20, pady=10)

        self.status_title = ctk.CTkLabel(self.status_card, text="Emulation Active", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_title.pack(side="left", padx=20, pady=15)

        self.toggle_switch = ctk.CTkSwitch(self.status_card, text="", command=self.toggle_daemon, onvalue=True, offvalue=False)
        self.toggle_switch.pack(side="right", padx=20, pady=15)

        # Sliders Settings Card
        self.sliders_card = ctk.CTkFrame(self, corner_radius=12)
        self.sliders_card.pack(fill="x", padx=20, pady=10)

        # Slider 1: Sensitivity
        self.sens_lbl = ctk.CTkLabel(self.sliders_card, text="Sensitivity: 5.0", font=ctk.CTkFont(weight="bold"))
        self.sens_lbl.pack(anchor="w", padx=20, pady=(15, 0))
        self.sens_slider = ctk.CTkSlider(self.sliders_card, from_=0.5, to=20.0, number_of_steps=39, command=self.on_slider_change)
        self.sens_slider.pack(fill="x", padx=20, pady=(5, 15))

        # Slider 2: Deadzone
        self.dz_lbl = ctk.CTkLabel(self.sliders_card, text="Deadzone: 20%", font=ctk.CTkFont(weight="bold"))
        self.dz_lbl.pack(anchor="w", padx=20, pady=(0, 0))
        self.dz_slider = ctk.CTkSlider(self.sliders_card, from_=0.05, to=0.50, number_of_steps=45, command=self.on_slider_change)
        self.dz_slider.pack(fill="x", padx=20, pady=(5, 15))

        # Slider 3: Acceleration Curve Exponent
        self.curve_lbl = ctk.CTkLabel(self.sliders_card, text="Curve Power: 2.0 (Quadratic)", font=ctk.CTkFont(weight="bold"))
        self.curve_lbl.pack(anchor="w", padx=20, pady=(0, 0))
        self.curve_slider = ctk.CTkSlider(self.sliders_card, from_=1.0, to=3.0, number_of_steps=20, command=self.on_slider_change)
        self.curve_slider.pack(fill="x", padx=20, pady=(5, 15))

        # Axis Inversion Toggles
        self.invert_frame = ctk.CTkFrame(self.sliders_card, fg_color="transparent")
        self.invert_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        self.invert_x_switch = ctk.CTkSwitch(self.invert_frame, text="Invert X Axis", command=self.push_config_updates)
        self.invert_x_switch.pack(side="left")
        
        self.invert_y_switch = ctk.CTkSwitch(self.invert_frame, text="Invert Y Axis", command=self.push_config_updates)
        self.invert_y_switch.pack(side="right")

        # Key Bindings Card
        self.bindings_card = ctk.CTkFrame(self, corner_radius=12)
        self.bindings_card.pack(fill="x", padx=20, pady=10)

        self.bindings_title = ctk.CTkLabel(self.bindings_card, text="Controller Keybinds", font=ctk.CTkFont(size=13, weight="bold"), text_color="#94a3b8")
        self.bindings_title.pack(anchor="w", padx=20, pady=(10, 5))

        # Grid container for bindings dropdowns
        self.grid_frame = ctk.CTkFrame(self.bindings_card, fg_color="transparent")
        self.grid_frame.pack(fill="x", padx=10, pady=5)
        self.grid_frame.columnconfigure((0, 1), weight=1)

        self.option_menus = {}
        buttons = [
            ("Button A (South)", "key_a"),
            ("Button B (East)", "key_b"),
            ("Button X (West)", "key_x"),
            ("Button Y (North)", "key_y")
        ]

        for idx, (label, key) in enumerate(buttons):
            row = idx // 2
            col = idx % 2
            
            cell = ctk.CTkFrame(self.grid_frame, fg_color="transparent")
            cell.grid(row=row, column=col, padx=10, pady=5, sticky="we")
            
            lbl = ctk.CTkLabel(cell, text=label, font=ctk.CTkFont(size=11))
            lbl.pack(anchor="w", padx=5)
            
            menu = ctk.CTkOptionMenu(cell, values=list(ACTIONS.values()), command=self.on_binding_change)
            menu.pack(fill="x", pady=2)
            self.option_menus[key] = menu

        # Uninstall Button
        self.uninstall_btn = ctk.CTkButton(
            self,
            text="Uninstall Software",
            fg_color="#7f1d1d",
            hover_color="#b91c1c",
            text_color="#fca5a5",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.confirm_uninstall
        )
        self.uninstall_btn.pack(fill="x", padx=20, pady=(15, 20))

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
        try:
            req = urllib.request.Request(f"{HOST}/toggle")
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                self.update_switch_ui(data["enabled"])
        except Exception:
            pass

    def update_switch_ui(self, enabled):
        if enabled:
            self.status_title.configure(text="Emulation Active", text_color="#34d399")
            self.toggle_switch.select()
        else:
            self.status_title.configure(text="Emulation Paused (Sleep)", text_color="#ef4444")
            self.toggle_switch.deselect()

    def on_slider_change(self, val):
        sens = self.sens_slider.get()
        dz = self.dz_slider.get()
        curve = self.curve_slider.get()

        self.sens_lbl.configure(text=f"Sensitivity: {sens:.1f}")
        self.dz_lbl.configure(text=f"Deadzone: {int(dz*100)}%")

        curve_name = "(Linear)" if curve == 1.0 else ("(Quadratic)" if curve == 2.0 else ("(Cubic)" if curve == 3.0 else ""))
        self.curve_lbl.configure(text=f"Curve Power: {curve:.1f} {curve_name}")

        self.push_config_updates()

    def on_binding_change(self, choice):
        self.push_config_updates()

    def push_config_updates(self, *args):
        sens = self.sens_slider.get()
        dz = self.dz_slider.get()
        curve = self.curve_slider.get()

        key_a = ACTION_REVERSE.get(self.option_menus["key_a"].get(), 0)
        key_b = ACTION_REVERSE.get(self.option_menus["key_b"].get(), 0)
        key_x = ACTION_REVERSE.get(self.option_menus["key_x"].get(), 0)
        key_y = ACTION_REVERSE.get(self.option_menus["key_y"].get(), 0)

        inv_x = 1 if self.invert_x_switch.get() else 0
        inv_y = 1 if self.invert_y_switch.get() else 0

        url = f"{HOST}/set?deadzone={dz:.2f}&sensitivity={sens:.1f}&curve_power={curve:.1f}&key_a={key_a}&key_b={key_b}&key_x={key_x}&key_y={key_y}&invert_x={inv_x}&invert_y={inv_y}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=0.1) as resp:
                pass
        except Exception:
            pass

    def poll_daemon(self):
        try:
            req = urllib.request.Request(f"{HOST}/status")
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                
                self.update_switch_ui(data["enabled"])
                
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

                for key in ["key_a", "key_b", "key_x", "key_y"]:
                    if key in data:
                        action_name = ACTIONS.get(data[key], "Disabled")
                        self.option_menus[key].set(action_name)

                # Hide the warning banner since it is connected and working!
                if hasattr(self, 'warning_frame'):
                    self.warning_frame.pack_forget()
        except Exception:
            self.status_title.configure(text="Connecting to Daemon...", text_color="#e2e8f0")
            if not self.permissions_ok and hasattr(self, 'warning_frame'):
                if not self.warning_frame.winfo_manager():
                    self.warning_frame.pack(fill="x", padx=20, pady=(0, 10), before=self.status_card)
            
        self.after(2000, self.poll_daemon)

    def on_exit(self):
        print("[TriggerCursor] Stopping background C++ daemon...")
        if self.daemon_proc:
            try:
                self.daemon_proc.terminate()
                self.daemon_proc.wait()
            except Exception:
                pass
        if hasattr(self, "daemon_log"):
            try:
                self.daemon_log.close()
            except Exception:
                pass
        self.destroy()

def main():
    app = TriggerCursorApp()
    app.mainloop()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil

def get_user_data_dir():
    if sys.platform.startswith("win32"):
        base = os.getenv("APPDATA", os.path.expanduser("~"))
        path = os.path.join(base, "TriggerCursor")
    else:
        base = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        path = os.path.join(base, "triggercursor")
    os.makedirs(path, exist_ok=True)
    return path

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check for customtkinter dependency
    try:
        import customtkinter
    except ImportError:
        print("[TriggerCursor Launcher] customtkinter not found. Installing dependencies...")
        try:
            # Determine appropriate pip arguments
            pip_cmd = [sys.executable, "-m", "pip", "install", "customtkinter>=6.0.0"]
            if sys.platform.startswith("linux"):
                pip_cmd.append("--break-system-packages")
            
            subprocess.run(pip_cmd, check=True)
            print("[TriggerCursor Launcher] Dependencies installed successfully.")
        except Exception as e:
            print(f"[TriggerCursor Launcher] Failed to install dependencies: {e}")
            print("Please install customtkinter manually and try again.")
            sys.exit(1)

    # Replicate compile check to build daemon in foreground if missing
    user_data_dir = get_user_data_dir()
    build_dir = os.path.join(user_data_dir, "build")
    
    if sys.platform.startswith("win32"):
        binary_path = os.path.join(build_dir, "Release", "trigger_cursor_daemon.exe")
        if not os.path.exists(binary_path):
            binary_path = os.path.join(build_dir, "trigger_cursor_daemon.exe")
        if not os.path.exists(binary_path):
            binary_path = os.path.join(build_dir, "Debug", "trigger_cursor_daemon.exe")
    else:
        binary_path = os.path.join(build_dir, "trigger_cursor_daemon")

    if not os.path.exists(binary_path):
        print("[TriggerCursor Launcher] Daemon binary not found. Compiling backend...")
        try:
            os.makedirs(build_dir, exist_ok=True)
            if sys.platform.startswith("win32"):
                subprocess.run(["cmake", "-B", build_dir, "-S", root_dir], cwd=build_dir, check=True)
                subprocess.run(["cmake", "--build", build_dir, "--config", "Release"], cwd=build_dir, check=True)
            else:
                subprocess.run(["cmake", "-B", build_dir, "-S", root_dir, "-DCMAKE_BUILD_TYPE=Release"], cwd=build_dir, check=True)
                subprocess.run(["cmake", "--build", build_dir], cwd=build_dir, check=True)
            print("[TriggerCursor Launcher] Compilation successful!")
        except Exception as e:
            print(f"[TriggerCursor Launcher] Warning: Failed to compile daemon: {e}")
            print("Launcher will continue, but the app might fail to start the daemon.")

    # Insert root directory to Python path
    sys.path.insert(0, root_dir)

    # Parse foreground option
    foreground = False
    if "--foreground" in sys.argv or "-f" in sys.argv:
        foreground = True
        sys.argv = [arg for arg in sys.argv if arg not in ("--foreground", "-f")]

    if foreground:
        try:
            from triggercursor.gui import main as run_app
            run_app()
        except KeyboardInterrupt:
            print("\n[TriggerCursor Launcher] Interrupted by user. Exiting.")
            sys.exit(0)
        except Exception as e:
            print(f"[TriggerCursor Launcher] Failed to launch application: {e}")
            sys.exit(1)
    else:
        print("[TriggerCursor Launcher] Launching GUI in background and exiting terminal...")
        gui_script = os.path.join(root_dir, "triggercursor", "gui.py")
        cmd = [sys.executable, gui_script]
        
        try:
            if sys.platform.startswith("win32"):
                DETACHED_PROCESS = 0x00000008
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=DETACHED_PROCESS,
                    cwd=root_dir
                )
            else:
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    cwd=root_dir
                )
        except Exception as e:
            print(f"[TriggerCursor Launcher] Failed to spawn detached GUI: {e}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[TriggerCursor Launcher] Interrupted by user. Exiting.")
        sys.exit(0)

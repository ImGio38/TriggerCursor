#!/usr/bin/env python3
import os
import sys
import platform
import subprocess
import shutil
import time
import threading
import ctypes

# ANSI Escape Sequences for Terminal Styling
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"

def enable_ansi_support():
    if sys.platform.startswith("win32"):
        try:
            kernel32 = ctypes.windll.kernel32
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

# Spinner Helper for Visual Polish
class Spinner:
    def __init__(self, message="Working..."):
        self.message = message
        self.spinner_cycle = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.running = False
        self.thread = None

    def _spin(self):
        idx = 0
        while self.running:
            sys.stdout.write(f"\r{COLOR_CYAN}{self.spinner_cycle[idx]}{COLOR_RESET} {self.message}")
            sys.stdout.flush()
            idx = (idx + 1) % len(self.spinner_cycle)
            time.sleep(0.08)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self, success=True):
        self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 15) + "\r")
        if success:
            print(f"{COLOR_GREEN}✓{COLOR_RESET} {self.message} - Completed.")
        else:
            print(f"{COLOR_RED}✗{COLOR_RESET} {self.message} - Failed.")
        sys.stdout.flush()

def run_command_with_spinner(cmd, message, cwd=None):
    spinner = Spinner(message)
    spinner.start()
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
        if res.returncode == 0:
            spinner.stop(success=True)
            return True, res.stdout
        else:
            spinner.stop(success=False)
            print(f"{COLOR_RED}Command execution failed:{COLOR_RESET} {' '.join(cmd)}")
            print(f"Stdout:\n{res.stdout}")
            print(f"Stderr:\n{res.stderr}")
            return False, res.stderr
    except Exception as e:
        spinner.stop(success=False)
        print(f"{COLOR_RED}Failed to run command:{COLOR_RESET} {e}")
        return False, str(e)

def run_command_foreground(cmd, message, cwd=None):
    print(f"\n{COLOR_CYAN}>>> {message}...{COLOR_RESET}")
    try:
        subprocess.run(cmd, check=True, cwd=cwd)
        print(f"{COLOR_GREEN}✓ {message} - Completed successfully.{COLOR_RESET}\n")
        return True
    except Exception as e:
        print(f"{COLOR_RED}✗ {message} - Failed: {e}{COLOR_RESET}\n")
        return False

def get_user_data_dir():
    if sys.platform.startswith("win32"):
        base = os.getenv("APPDATA", os.path.expanduser("~"))
        path = os.path.join(base, "TriggerCursor")
    else:
        base = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        path = os.path.join(base, "triggercursor")
    os.makedirs(path, exist_ok=True)
    return path

def detect_linux_pkg_manager():
    if shutil.which("apt-get"):
        return "apt"
    elif shutil.which("dnf"):
        return "dnf"
    elif shutil.which("pacman"):
        return "pacman"
    return None

def main():
    enable_ansi_support()
    root_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"{COLOR_BOLD}{COLOR_BLUE}=========================================================={COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_BLUE}              TriggerCursor System Setup                  {COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_BLUE}=========================================================={COLOR_RESET}")
    print()

    # --- 1. DETERMINE DEPENDENCY STATUS ---
    dependencies = {}
    
    # Check Tkinter
    try:
        import tkinter
        dependencies["Tkinter (GUI Toolkit)"] = ("INSTALLED", None)
    except ImportError:
        dependencies["Tkinter (GUI Toolkit)"] = ("MISSING", "system-pkg")

    # Check CMake
    cmake_path = shutil.which("cmake")
    if not cmake_path and sys.platform.startswith("win32"):
        # Look in common Windows installation paths
        win_cmake_paths = [
            r"C:\Program Files\CMake\bin\cmake.exe",
            r"C:\Program Files (x86)\CMake\bin\cmake.exe"
        ]
        for path in win_cmake_paths:
            if os.path.exists(path):
                os.environ["PATH"] += os.pathsep + os.path.dirname(path)
                cmake_path = path
                break
    if cmake_path:
        dependencies["CMake (Build Tool)"] = ("INSTALLED", cmake_path)
    else:
        dependencies["CMake (Build Tool)"] = ("MISSING", "system-pkg")

    # Check C++ Compiler
    compiler_path = None
    if sys.platform.startswith("win32"):
        if shutil.which("cl"):
            compiler_path = "MSVC (cl.exe)"
        elif shutil.which("g++"):
            compiler_path = "MinGW (g++)"
        elif shutil.which("clang++"):
            compiler_path = "Clang (clang++)"
        else:
            # Check vswhere
            vswhere_paths = [
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft Visual Studio\Installer\vswhere.exe")
            ]
            for vp in vswhere_paths:
                if os.path.exists(vp):
                    try:
                        res = subprocess.run([
                            vp, "-latest", "-products", "*",
                            "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                            "-property", "installationPath"
                        ], capture_output=True, text=True)
                        if res.returncode == 0 and res.stdout.strip():
                            compiler_path = f"MSVC Tools (VS at {res.stdout.strip()})"
                            break
                    except Exception:
                        pass
    else:
        if shutil.which("g++"):
            compiler_path = "GCC (g++)"
        elif shutil.which("clang++"):
            compiler_path = "Clang (clang++)"

    if compiler_path:
        dependencies["C++ Compiler"] = ("INSTALLED", compiler_path)
    else:
        dependencies["C++ Compiler"] = ("MISSING", "system-pkg")

    # Check CustomTkinter
    try:
        import customtkinter
        dependencies["CustomTkinter (Python Package)"] = ("INSTALLED", None)
    except ImportError:
        dependencies["CustomTkinter (Python Package)"] = ("MISSING", "pip-pkg")

    # --- 2. DISPLAY STATUS GRID ---
    print(f"{COLOR_BOLD}System Verification Plan:{COLOR_RESET}")
    print("-" * 65)
    plan_to_install = []
    
    for name, (status, detail) in dependencies.items():
        if status == "INSTALLED":
            detail_str = f" ({detail})" if detail else ""
            print(f"  {COLOR_GREEN}[✓] {name:<30}{COLOR_RESET} : INSTALLED{detail_str}")
        else:
            print(f"  {COLOR_YELLOW}[-] {name:<30}{COLOR_RESET} : {COLOR_RED}MISSING{COLOR_RESET}")
            plan_to_install.append(name)
            
    print("-" * 65)
    print()

    # --- 3. APPLY PLAN IF NEEDED ---
    if plan_to_install:
        print(f"{COLOR_YELLOW}Missing components detected. Applying setup plan...{COLOR_RESET}")
        
        # Windows Installations
        if sys.platform.startswith("win32"):
            # Check winget
            winget_available = shutil.which("winget") is not None
            if not winget_available:
                print(f"{COLOR_RED}Warning: winget is not available. Please install CMake and Visual Studio Build Tools manually.{COLOR_RESET}")
                
            if "CMake (Build Tool)" in plan_to_install and winget_available:
                cmd = ["winget", "install", "--id", "Kitware.CMake", "-h", "--accept-source-agreements", "--accept-package-agreements"]
                success, _ = run_command_with_spinner(cmd, "Installing CMake via winget")
                if success:
                    # Try to add default install path to current session env
                    paths = [r"C:\Program Files\CMake\bin", r"C:\Program Files (x86)\CMake\bin"]
                    for p in paths:
                        if os.path.exists(p):
                            os.environ["PATH"] += os.pathsep + p
                            break

            if "C++ Compiler" in plan_to_install and winget_available:
                print(f"{COLOR_YELLOW}Visual Studio Build Tools workload 'Desktop development with C++' is required.{COLOR_RESET}")
                print("This is a ~2GB download and requires administrator privileges.")
                choice = input("Do you want to install VS Build Tools now? [Y/n]: ").strip().lower()
                if choice in ("", "y", "yes"):
                    cmd = ["winget", "install", "--id", "Microsoft.VisualStudio.2022.BuildTools", "--override", 
                           "--passive --locale en-US --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended", 
                           "--accept-source-agreements", "--accept-package-agreements"]
                    run_command_foreground(cmd, "Installing Visual Studio Build Tools")
                else:
                    print("Skipping Build Tools. C++ compilation might fail.")

        # Linux Installations
        else:
            pkg_mgr = detect_linux_pkg_manager()
            if not pkg_mgr:
                print(f"{COLOR_RED}Error: Supported package manager (apt/dnf/pacman) not found.{COLOR_RESET}")
                print("Please install missing dependencies manually.")
            else:
                # Refresh sudo credentials interactively
                print(f"{COLOR_YELLOW}Sudo credentials are required to install missing system libraries.{COLOR_RESET}")
                try:
                    subprocess.run(["sudo", "-v"], check=True)
                    sudo_verified = True
                except subprocess.CalledProcessError:
                    sudo_verified = False
                    print(f"{COLOR_RED}Sudo authentication failed. Skipping system package setup.{COLOR_RESET}")

                if sudo_verified:
                    pkgs = []
                    # Setup packages map
                    if pkg_mgr == "apt":
                        if "Tkinter (GUI Toolkit)" in plan_to_install:
                            pkgs.append("python3-tk")
                        if "CMake (Build Tool)" in plan_to_install:
                            pkgs.append("cmake")
                        if "C++ Compiler" in plan_to_install:
                            pkgs.extend(["build-essential", "python3-dev"])
                        
                        if pkgs:
                            run_command_with_spinner(["sudo", "apt-get", "update"], "Updating package repositories")
                            run_command_with_spinner(["sudo", "apt-get", "install", "-y"] + pkgs, f"Installing packages via apt: {', '.join(pkgs)}")
                            
                    elif pkg_mgr == "dnf":
                        if "Tkinter (GUI Toolkit)" in plan_to_install:
                            pkgs.append("python3-tkinter")
                        if "CMake (Build Tool)" in plan_to_install:
                            pkgs.append("cmake")
                        
                        if "C++ Compiler" in plan_to_install:
                            pkgs.append("python3-devel")
                            run_command_foreground(["sudo", "dnf", "groupinstall", "-y", "Development Tools"], "Installing Development Tools workload")
                        
                        if pkgs:
                            run_command_with_spinner(["sudo", "dnf", "install", "-y"] + pkgs, f"Installing packages via dnf: {', '.join(pkgs)}")
                            
                    elif pkg_mgr == "pacman":
                        if "Tkinter (GUI Toolkit)" in plan_to_install:
                            pkgs.append("tk")
                        if "CMake (Build Tool)" in plan_to_install:
                            pkgs.append("cmake")
                        if "C++ Compiler" in plan_to_install:
                            pkgs.append("base-devel")
                            
                        if pkgs:
                            run_command_with_spinner(["sudo", "pacman", "-S", "--needed", "--noconfirm"] + pkgs, f"Installing packages via pacman: {', '.join(pkgs)}")

        # Install pip packages if missing
        if "CustomTkinter (Python Package)" in plan_to_install:
            pip_cmd = [sys.executable, "-m", "pip", "install", "customtkinter>=6.0.0"]
            if sys.platform.startswith("linux"):
                pip_cmd.append("--break-system-packages")
            run_command_with_spinner(pip_cmd, "Installing CustomTkinter via pip")

        print(f"\n{COLOR_GREEN}✓ Setup phase completed.{COLOR_RESET}\n")

    # --- 4. COMPILE DAEMON BACKEND IF MISSING ---
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
        print(f"{COLOR_YELLOW}Daemon binary not found. Initiating backend compilation...{COLOR_RESET}")
        try:
            os.makedirs(build_dir, exist_ok=True)
            if sys.platform.startswith("win32"):
                # Run configure
                success, _ = run_command_with_spinner(["cmake", "-B", build_dir, "-S", root_dir], "Configuring CMake build environment", cwd=build_dir)
                # Run build
                if success:
                    run_command_with_spinner(["cmake", "--build", build_dir, "--config", "Release"], "Compiling native C++ backend (Release)", cwd=build_dir)
            else:
                # Run configure
                success, _ = run_command_with_spinner(["cmake", "-B", build_dir, "-S", root_dir, "-DCMAKE_BUILD_TYPE=Release"], "Configuring CMake build environment", cwd=build_dir)
                # Run build
                if success:
                    run_command_with_spinner(["cmake", "--build", build_dir], "Compiling native C++ backend (Release)", cwd=build_dir)
        except Exception as e:
            print(f"{COLOR_RED}Warning: Backend compilation failed: {e}{COLOR_RESET}")
            print("Launcher will proceed, but daemon operations might fail.")

    # --- 5. LAUNCH GUI APPLICATION ---
    # Append root_dir to path so python launcher can find triggercursor package
    sys.path.insert(0, root_dir)

    foreground = False
    if "--foreground" in sys.argv or "-f" in sys.argv:
        foreground = True
        sys.argv = [arg for arg in sys.argv if arg not in ("--foreground", "-f")]

    if foreground:
        try:
            print(f"{COLOR_GREEN}Launching TriggerCursor GUI in foreground...{COLOR_RESET}")
            from triggercursor.gui import main as run_app
            run_app()
        except KeyboardInterrupt:
            print(f"\n{COLOR_YELLOW}[TriggerCursor] Interrupted by user. Exiting.{COLOR_RESET}")
            sys.exit(0)
        except Exception as e:
            print(f"{COLOR_RED}[TriggerCursor] Launch failed: {e}{COLOR_RESET}")
            sys.exit(1)
    else:
        print(f"{COLOR_CYAN}Launching GUI in background and exiting terminal...{COLOR_RESET}")
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
            print(f"{COLOR_RED}[TriggerCursor] Failed to spawn detached GUI: {e}{COLOR_RESET}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{COLOR_YELLOW}[TriggerCursor Setup] Cancelled by user.{COLOR_RESET}")
        sys.exit(0)

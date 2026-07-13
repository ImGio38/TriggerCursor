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

def find_mingw_gxx():
    if shutil.which("g++"):
        return shutil.which("g++")
        
    search_bases = [
        get_user_data_dir(),
        os.path.expandvars(r"%LocalAppData%\Microsoft\WinGet\Packages"),
        os.path.expandvars(r"%ProgramFiles%"),
        os.path.expandvars(r"%ProgramFiles(x86)%"),
        os.path.expandvars(r"%UserProfile%\AppData\Local\Programs"),
        r"C:\winlibs"
    ]
    
    for base in search_bases:
        if not os.path.exists(base):
            continue
        try:
            for entry in os.scandir(base):
                if entry.is_dir():
                    name_lower = entry.name.lower()
                    if "winlibs" in name_lower or "mingw" in name_lower or "msys" in name_lower or "w64devkit" in name_lower:
                        for root, dirs, files in os.walk(entry.path):
                            if "g++.exe" in files:
                                return os.path.join(root, "g++.exe")
                            # Don't go too deep to avoid performance issues
                            rel_path = os.path.relpath(root, entry.path)
                            depth = len(rel_path.split(os.sep))
                            if depth > 3:
                                del dirs[:] # stop recursing this branch
        except Exception:
            pass
    return None

def download_and_extract_w64devkit():
    import urllib.request
    import zipfile
    
    user_data_dir = get_user_data_dir()
    zip_path = os.path.join(user_data_dir, "w64devkit.zip")
    
    url = "https://github.com/skeeto/w64devkit/releases/download/v2.8.0/w64devkit-2.8.0.zip"
    
    spinner = Spinner("Downloading w64devkit (~41MB)...")
    spinner.start()
    try:
        # Use a custom user-agent to avoid GitHub returning 403
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        spinner.stop(success=True)
    except Exception as e:
        spinner.stop(success=False)
        print(f"{COLOR_RED}Failed to download w64devkit: {e}{COLOR_RESET}")
        return False
        
    spinner = Spinner("Extracting compiler toolchain...")
    spinner.start()
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(user_data_dir)
        spinner.stop(success=True)
        # Clean up zip
        os.remove(zip_path)
        return True
    except Exception as e:
        spinner.stop(success=False)
        print(f"{COLOR_RED}Failed to extract w64devkit: {e}{COLOR_RESET}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False

def check_fast_path():
    # Fast path check: if daemon binary exists and packages are installed, we can boot immediately
    user_data_dir = get_user_data_dir()
    build_dir = os.path.join(user_data_dir, "build")
    
    if sys.platform.startswith("win32"):
        binary_paths = [
            os.path.join(build_dir, "Release", "trigger_cursor_daemon.exe"),
            os.path.join(build_dir, "trigger_cursor_daemon.exe"),
            os.path.join(build_dir, "Debug", "trigger_cursor_daemon.exe")
        ]
    else:
        binary_paths = [os.path.join(build_dir, "trigger_cursor_daemon")]
        
    binary_exists = any(os.path.exists(bp) for bp in binary_paths)
    if not binary_exists:
        return False
        
    try:
        import tkinter
        import customtkinter
        return True
    except ImportError:
        return False

def main():
    enable_ansi_support()
    root_dir = os.path.dirname(os.path.abspath(__file__))

    # Fast path check: launch immediately if everything is already configured and compiled
    if check_fast_path():
        # Append root_dir to path so python launcher can find triggercursor package
        sys.path.insert(0, root_dir)
        foreground = "--foreground" in sys.argv or "-f" in sys.argv
        if foreground:
            sys.argv = [arg for arg in sys.argv if arg not in ("--foreground", "-f")]
            try:
                from triggercursor.gui import main as run_app
                run_app()
                return
            except Exception:
                pass
        else:
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
                return
            except Exception:
                pass

    # Fallback to interactive setup with beautiful dashboard
    print(f"{COLOR_BOLD}{COLOR_BLUE}")
    print("   ┌┬┐┬─┐┬┌─┐┌─┐┌─┐┬─┐  ┌─┐┬ ┬┬─┐┌─┐┌─┐┬─┐")
    print("    │ ├┬┘││ ┬│ ┬├┤ ├┬┘  │  │ │├┬┘└─┐│ │├┬┘")
    print("    ┴ ┴└─┴└─┘└─┘└──┴└─  └─┘└─┘┴└─└─┘└─┘┴└─")
    print(f"{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}  System Setup & Dependency Verification{COLOR_RESET}")
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
        # Auto-discover MinGW first if g++ is not directly in PATH
        if not shutil.which("g++"):
            gxx_path = find_mingw_gxx()
            if gxx_path:
                gxx_dir = os.path.dirname(gxx_path)
                if gxx_dir not in os.environ["PATH"]:
                    os.environ["PATH"] += os.pathsep + gxx_dir
                    
        if shutil.which("cl"):
            compiler_path = shutil.which("cl")
        elif shutil.which("g++"):
            compiler_path = shutil.which("g++")
        elif shutil.which("clang++"):
            compiler_path = shutil.which("clang++")
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
                            compiler_path = os.path.join(res.stdout.strip(), "VC", "Tools", "MSVC")
                            break
                    except Exception:
                        pass
    else:
        if shutil.which("g++"):
            compiler_path = shutil.which("g++")
        elif shutil.which("clang++"):
            compiler_path = shutil.which("clang++")

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
    print(f"┌────────────────────────────────────────────────────────────────────────┐")
    print(f"│                       SYSTEM VERIFICATION PLAN                         │")
    print(f"├─────────────────────────────────────────┬──────────────────────────────┤")
    plan_to_install = []
    
    for name, (status, detail) in dependencies.items():
        if status == "INSTALLED":
            detail_str = f"({os.path.basename(detail)})" if detail else ""
            status_text = f"{COLOR_GREEN}✓ INSTALLED {detail_str}{COLOR_RESET}"
            clean_status = f"✓ INSTALLED {detail_str}"
            padding = 28 - len(clean_status)
            print(f"│  {name:<39} │ {status_text}{' ' * padding}│")
        else:
            status_text = f"{COLOR_RED}✗ MISSING{COLOR_RESET}"
            padding = 28 - len("✗ MISSING")
            print(f"│  {name:<39} │ {status_text}{' ' * padding}│")
            plan_to_install.append(name)
            
    print(f"└─────────────────────────────────────────┴──────────────────────────────┘")
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

            if "C++ Compiler" in plan_to_install:
                print(f"{COLOR_BOLD}{COLOR_YELLOW}C++ Compiler is required to compile the native daemon.{COLOR_RESET}")
                print("Please select a compiler option:")
                print(f"  {COLOR_GREEN}[1] Auto-Download w64devkit (Ultra-Lightweight){COLOR_RESET} - Portable GCC/G++ (~41MB download, no admin required, recommended)")
                if winget_available:
                    print(f"  {COLOR_GREEN}[2] MinGW (winlibs.mingw) via winget{COLOR_RESET} - Standard package manager GCC (~150MB)")
                    print(f"  {COLOR_GREEN}[3] VS Build Tools (Minimal) via winget{COLOR_RESET} - Official MSVC without extras (~1.5GB)")
                    print(f"  {COLOR_GREEN}[4] VS Build Tools (Full) via winget{COLOR_RESET} - Official MSVC with all extras (~2.5GB)")
                    print(f"  {COLOR_GREEN}[5] Skip / Install Manually{COLOR_RESET}")
                else:
                    print(f"  {COLOR_GREEN}[2] Skip / Install Manually{COLOR_RESET}")
                print()
                
                if winget_available:
                    choice = input("Select option [1-5] (default: 1): ").strip()
                else:
                    choice = input("Select option [1-2] (default: 1): ").strip()
                    if choice == "2":
                        choice = "5" # Map to Skip / Install Manually
                
                if choice == "" or choice == "1":
                    success = download_and_extract_w64devkit()
                    if success:
                        gxx_path = find_mingw_gxx()
                        if gxx_path:
                            gxx_dir = os.path.dirname(gxx_path)
                            if gxx_dir not in os.environ["PATH"]:
                                os.environ["PATH"] += os.pathsep + gxx_dir
                            print(f"{COLOR_GREEN}✓ w64devkit compiler successfully configured at {gxx_path}{COLOR_RESET}")
                        else:
                            print(f"{COLOR_YELLOW}! compiler could not be located immediately. A terminal restart may be required.{COLOR_RESET}")
                elif choice == "2":
                    cmd = ["winget", "install", "--id", "winlibs.mingw", "-h", "--accept-source-agreements", "--accept-package-agreements"]
                    success = run_command_foreground(cmd, "Installing MinGW via winget")
                    if success:
                        gxx_path = find_mingw_gxx()
                        if gxx_path:
                            gxx_dir = os.path.dirname(gxx_path)
                            if gxx_dir not in os.environ["PATH"]:
                                os.environ["PATH"] += os.pathsep + gxx_dir
                            print(f"{COLOR_GREEN}✓ MinGW compiler successfully configured at {gxx_path}{COLOR_RESET}")
                        else:
                            print(f"{COLOR_YELLOW}! MinGW installed, but compiler could not be located immediately. A terminal restart may be required.{COLOR_RESET}")
                elif choice == "3":
                    cmd = ["winget", "install", "--id", "Microsoft.VisualStudio.2022.BuildTools", "--override", 
                           "--passive --locale en-US --add Microsoft.VisualStudio.Workload.VCTools", 
                           "--accept-source-agreements", "--accept-package-agreements"]
                    run_command_foreground(cmd, "Installing Visual Studio Build Tools (Minimal)")
                elif choice == "4":
                    cmd = ["winget", "install", "--id", "Microsoft.VisualStudio.2022.BuildTools", "--override", 
                           "--passive --locale en-US --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended", 
                           "--accept-source-agreements", "--accept-package-agreements"]
                    run_command_foreground(cmd, "Installing Visual Studio Build Tools (Full)")
                else:
                    print("Skipping Compiler setup. C++ compilation might fail.")

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
                # Determine generator and compiler configuration
                generator_args = []
                if compiler_path and "g++" in compiler_path.lower():
                    generator_args = ["-G", "MinGW Makefiles", "-DCMAKE_BUILD_TYPE=Release"]
                else:
                    generator_args = ["-DCMAKE_BUILD_TYPE=Release"]
                
                # Run configure
                success, _ = run_command_with_spinner(["cmake"] + generator_args + ["-B", build_dir, "-S", root_dir], "Configuring CMake build environment", cwd=build_dir)
                # Run build
                if success:
                    run_command_with_spinner(["cmake", "--build", build_dir, "--config", "Release"], "Compiling native C++ backend (Release)", cwd=build_dir)
            else:
                # Run configure
                success, _ = run_command_with_spinner(["cmake", "-B", build_dir, "-S", root_dir, "-DCMAKE_BUILD_TYPE=Release"], "Configuring CMake build environment", cwd=build_dir)
                # Run build
                if success:
                    run_command_with_spinner(["cmake", "--build", build_dir], "Compiling native C++ backend (Release)", cwd=build_dir)
            
            # Verify build success and offer to clean up portable compiler
            built_binary = None
            for bp in [
                os.path.join(build_dir, "Release", "trigger_cursor_daemon.exe"),
                os.path.join(build_dir, "trigger_cursor_daemon.exe"),
                os.path.join(build_dir, "Debug", "trigger_cursor_daemon.exe"),
                os.path.join(build_dir, "trigger_cursor_daemon")
            ]:
                if os.path.exists(bp):
                    built_binary = bp
                    break
                    
            if built_binary:
                print(f"{COLOR_GREEN}✓ Native daemon compiled successfully!{COLOR_RESET}")
                # If w64devkit exists in APPDATA, offer to clean it up
                w64devkit_dir = os.path.join(user_data_dir, "w64devkit")
                if os.path.exists(w64devkit_dir):
                    print()
                    print(f"{COLOR_YELLOW}Compilation complete. We can clean up the temporary compiler (w64devkit) to save ~100MB of space.{COLOR_RESET}")
                    choice = input("Do you want to delete the portable compiler toolchain now? [Y/n]: ").strip().lower()
                    if choice in ("", "y", "yes"):
                        spinner = Spinner("Cleaning up temporary compiler files...")
                        spinner.start()
                        try:
                            # Remove directory tree
                            shutil.rmtree(w64devkit_dir)
                            spinner.stop(success=True)
                            print(f"{COLOR_GREEN}✓ Cleaned up temporary compiler files.{COLOR_RESET}")
                        except Exception as e:
                            spinner.stop(success=False)
                            print(f"Warning: Could not remove temporary compiler files: {e}")
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

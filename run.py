#!/usr/bin/env python3
import os
import sys
import subprocess

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

    # Insert root directory to Python path
    sys.path.insert(0, root_dir)

    # Import and run the app main entrypoint
    try:
        from triggercursor.gui import main as run_app
        run_app()
    except Exception as e:
        print(f"[TriggerCursor Launcher] Failed to launch application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

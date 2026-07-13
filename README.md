# TriggerCursor

A highly optimized, near-zero overhead controller-to-mouse driver. It features a native C++ emulation daemon and a modern desktop dashboard interface built with Python and CustomTkinter.

## Key Features

* **Native GUI:** Lightweight desktop interface built with CustomTkinter, without the overhead of a web browser.

* **Auto-Launch & Self-Closing:** Starts the background C++ daemon automatically on startup, and terminates it instantly on close.

* **Visual Controller Mapper:** Interactive Xbox/PlayStation visual layout featuring hover highlighting, click-to-select, and live hotplug rescanning.

* **Unified Macro Engine:** Maps buttons to mouse clicks, keyboard holds, or advanced macro sequences (e.g. `Ctrl+C` or `A,Delay:100,B`).

* **Hardware-First Autodetect:** Queries device bus IDs to target physical USB/Bluetooth devices directly, bypassing virtual wrapper layers.

* **Deadzones & Sensitivity:** Fully customizable radial deadzones, sensitivity multipliers, acceleration curves, and axis inversion controls.

* **Zero-Overhead C++ Daemon:** Utilizes native hardware interrupts (`evdev` on Linux, `XInput` on Windows) and SSE instruction math (`_mm_rsqrt_ss`) for optimal performance.

## System Requirements

Ensure your system has the required compilation tools to build the low-latency C++ backend:

### Linux Compatibility & Distros

TriggerCursor is display-server agnostic (works on both **Wayland** and **X11**) because it emulates hardware at the kernel level using `/dev/uinput`.

#### Guaranteed to Work:
* **Ubuntu** (18.04+)
* **Debian** (10+)
* **Fedora** (28+)
* **Arch Linux / Manjaro**
* **Linux Mint** (19+)
* **Pop!_OS**
* **openSUSE** (Leap & Tumbleweed)
* **RHEL / Rocky Linux / AlmaLinux** (8+)

#### Prerequisites & Installation by Distro:

Depending on your distribution, you must install the compilation tools and Python's graphical interface toolkit (since `tkinter` is packaged separately by default on many distributions):

* **Ubuntu / Debian / Mint / Pop!_OS:**
  ```bash
  sudo apt update
  sudo apt install cmake build-essential python3-dev python3-tk
  ```
* **Fedora / RHEL / Rocky / Alma:**
  ```bash
  sudo dnf groupinstall "Development Tools"
  sudo dnf install cmake python3-devel python3-tkinter
  ```
* **Arch Linux / Manjaro:**
  ```bash
  sudo pacman -S --needed base-devel cmake tk
  ```

#### What May Not Work / Known Gotchas:
* **Immutable OSs (e.g., SteamOS / Steam Deck):** By default, SteamOS has a read-only root filesystem. To install compilation dependencies (`cmake`, `gcc`), you must temporarily unlock the filesystem (`steamos-readonly disable`) and initialize the pacman keys.
* **Minimal / Server Kernels:** Custom-compiled or minimal server/container kernels may lack `uinput` support (`CONFIG_INPUT_UINPUT` disabled). Standard desktop kernels always have this module enabled.
* **Systems without PolicyKit / `udev`:** The interface uses `pkexec` (PolicyKit) to graphically request udev rule setup for `/dev/uinput`. Minimal systems without a PolicyKit agent will require manual setup (see [Linux Permissions Setup](#linux-permissions-setup) below).

### Windows
* Python 3 and pip
* Git
* CMake
* Visual Studio with the "Desktop development with C++" workload active

> [!NOTE]
> **Automatic Setup:** If Python, CMake, or Visual Studio C++ Build Tools are missing, the launcher will automatically attempt to install them for you.

## How to Run

TriggerCursor features a unified, cross-platform terminal bootstrapper that automatically checks system requirements, installs missing dependencies, compiles the low-overhead C++ backend daemon, and boots the application.

### Visual Installer UI
On launch, the bootstrapper presents a clear setup plan board:

```text
==========================================================
              TriggerCursor System Setup                  
==========================================================

System Verification Plan:
-----------------------------------------------------------------
  [✓] Tkinter (GUI Toolkit)          : INSTALLED
  [-] CMake (Build Tool)             : MISSING (Will install via winget)
  [-] C++ Compiler                   : MISSING (Will install via winget)
  [-] CustomTkinter (Python Package) : MISSING (Will install via pip)
-----------------------------------------------------------------
```

Missing components are resolved automatically with visual spinners and progress loaders (utilizing native package managers: `apt`, `dnf`, or `pacman` on Linux; `winget` and `pip` on Windows).

1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/TriggerCursor.git
   cd TriggerCursor
   ```

2. Run the launcher for your operating system:
   * **Linux:**
     ```bash
     ./run.sh
     ```
   * **Windows:**
     Double-click `run.bat` or run:
     ```cmd
     python run.py
     ```

On first launch, TriggerCursor will automatically compile the C++ daemon binary inside your standard user data folder (`~/.local/share/triggercursor` on Linux / `%APPDATA%/TriggerCursor` on Windows) and register the application shortcut under your OS application menu (Linux).

---

## Installation (Optional)

If you prefer installing it system-wide to run the `triggercursor` command directly from anywhere in your terminal:

```bash
# On Linux (to bypass system package restrictions):
pip install -e . --break-system-packages

# On Windows:
pip install -e .
```


## Linux Permissions Setup

The background daemon requires write permission to `/dev/uinput` to emulate hardware mouse inputs.

* **Automated Setup (Recommended):** The interface displays a "Permissions missing" banner on startup. Click the **Authorize** button to securely prompt for authorization and configure the system rules automatically.
* **Manual Setup:** Alternatively, you can configure these rules manually by running the following commands and then logging out and back in:
  ```bash
  echo 'KERNEL=="uinput", GROUP="input", MODE="0660", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/99-trigger-cursor.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```

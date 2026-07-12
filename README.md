# TriggerCursor

A highly optimized, near-zero overhead controller-to-mouse driver. It features a native C++ emulation daemon and a modern desktop dashboard interface built with Python and CustomTkinter.

## Key Features

* **Native Desktop Interface:** Runs as a standalone desktop window without requiring a web browser.
* **Auto-Launch & Self-Closing:** Launching the GUI automatically starts the background C++ daemon. Closing the GUI window terminates the daemon process immediately.
* **Application Menu Integration (Linux):** Registers itself under the Linux system application menu ("TriggerCursor") with a native gamepad launcher icon.
* **Interactive Gamepad Programmer (Logitech G HUB Style):**
  * Displays a visual Xbox/PlayStation outline layout built with vector graphics.
  * Supports hover highlighting and click-to-select for all 16 controller buttons.
  * Displays the active selected button highlighted in emerald green.
  * Includes a **⟳ Refresh** button to force-rescan USB/Bluetooth ports and detect hotplugged controllers.
* **Unified Button Mapper & Macro Engine:**
  * Maps all 16 buttons (A, B, X, Y, LB, RB, LT, RT, LS, RS, Back, Start, and D-pad directions).
  * Supports **Left Click**, **Right Click**, **Middle Click**, **Keyboard Key Holds**, and **Key Combos / Custom Macro chains** (e.g. `Ctrl+C` or `A,Delay:100,B`).
  * Features a real-time macro action previewer.
  * Automatic saving of macro entries on pressing **Enter** or clicking out of focus.
* **Hardware-First Autodetect:** Bypasses virtual compatibility controllers (like Steam Input wrappers) by querying device bus IDs and prioritizing physical USB/Bluetooth devices.
* **Deadzones & Inversion Controls:**
  * Radial Deadzone size controller (0% to 50%).
  * Sensitivity multiplier (0.5 to 20.0).
  * Acceleration Curve: Configurable curve power (1.0 for linear response, 2.0 for quadratic, and 3.0 for cubic).
  * Axis Inversion: Separate toggles to invert X and Y cursor axes.
* **Zero-Overhead Physics Backend:**
  * Linux: Uses evdev hardware event interrupts and consumes 0% CPU when the controller is idle.
  * Windows: Dynamically loads XInput at runtime and uses high-resolution waitable timers for sub-millisecond precision.
  * Math Optimization: Uses SSE Reciprocal Square Root instructions (`_mm_rsqrt_ss`) to normalize active vectors in 1 CPU cycle, avoiding expensive square root calculations on active paths.

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

## How to Run

You can run the application directly using the launcher scripts, which will automatically verify and install any missing dependencies for you.

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

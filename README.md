# TriggerCursor

A highly optimized, near-zero overhead controller-to-mouse driver. It features a native C++ emulation daemon and a modern desktop dashboard interface built with Python and CustomTkinter.

## Key Features

* **Native Desktop Interface:** Runs as a standalone desktop window without requiring a web browser.
* **Auto-Launch & Self-Closing:** Launching the GUI automatically starts the background C++ daemon. Closing the GUI window terminates the daemon process immediately.
* **Application Menu Integration (Linux):** Registers itself under the Linux system application menu ("TriggerCursor") with a native gamepad launcher icon.
* **Custom Key Bindings:** Maps individual controller buttons (A, B, X, Y) to actions (Left Click, Right Click, Middle Click, or Disabled).
* **Adjustable Sensitivity & Acceleration:**
  * Sensitivity: Configurable down to fractional increments (0.5 to 20.0).
  * Acceleration Curve: Configurable curve power (1.0 for linear response, 2.0 for quadratic, and 3.0 for cubic).
* **Zero-Overhead Physics Backend:**
  * Linux: Uses evdev hardware event interrupts and consumes 0% CPU when the controller is idle.
  * Windows: Dynamically loads XInput at runtime and uses high-resolution waitable timers for sub-millisecond precision.
  * Math Optimization: Uses SSE Reciprocal Square Root instructions (`_mm_rsqrt_ss`) to normalize active vectors in 1 CPU cycle, avoiding expensive square root calculations on active paths.

## System Requirements

Ensure your system has the required compilation tools to build the low-latency C++ backend:

### Linux
* Python 3 and pip
* Git
* CMake
* C++ Compiler (GCC or Clang)

On Debian/Ubuntu systems, install these packages via:
```bash
sudo apt install cmake build-essential
```

### Windows
* Python 3 and pip
* Git
* CMake
* Visual Studio with the "Desktop development with C++" workload active

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/TriggerCursor.git
   cd TriggerCursor
   ```

2. Install the package in editable mode:
   ```bash
   pip install -e .
   ```
   This registers the `triggercursor` executable command in your system path.

## Running the Application

Launch the interface from the command line:
```bash
triggercursor
```
On first launch, TriggerCursor will automatically compile the C++ daemon binary inside your standard user configuration directory (`~/.local/share/triggercursor` on Linux / `%APPDATA%/TriggerCursor` on Windows) and create the relevant application shortcuts.

## Linux Permissions Setup

The background daemon requires write permission to `/dev/uinput` to emulate hardware mouse inputs.

* **Automated Setup (Recommended):** The interface displays a "Permissions missing" banner on startup. Click the **Authorize** button to securely prompt for authorization and configure the system rules automatically.
* **Manual Setup:** Alternatively, you can configure these rules manually by running the following commands and then logging out and back in:
  ```bash
  echo 'KERNEL=="uinput", GROUP="input", MODE="0660", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/99-trigger-cursor.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```

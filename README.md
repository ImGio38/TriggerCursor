# TriggerCursor

A highly optimized, near-zero overhead controller-to-mouse driver built natively in **C++** with a sleek, modern desktop control interface built in **Python (CustomTkinter)**.

---

## Key Features & Customizations

1. **Standalone GUI (No Browser)**: The interface runs as a standalone desktop window on your screen. You do not need to open a web browser.
2. **Auto-Launch & Self-Closing**: Launching the GUI app automatically starts the C++ daemon in the background. Closing the GUI window terminates the background C++ process immediately. No terminal window needs to stay open.
3. **Application Menu Integration (Linux)**: Upon launching the app for the first time, it automatically registers itself as a native desktop application under your Linux system application menu (**"TriggerCursor"** with a gamepad icon). You can search and launch it directly from your OS launcher.
4. **Custom Key Bindings**: Map individual controller buttons (A, B, X, Y) to actions (Left Click, Right Click, Middle Click, or Disabled) using clean dropdown menus.
5. **Adjustable Sensitivity & Acceleration**:
   * **Sensitivity**: Configure down to fractionals (e.g. `0.5` to `20.0`) for precise control.
   * **Acceleration Curve**: Choose your acceleration power. Drag it to `1.0` for a flat linear response, `2.0` for a gentle quadratic response, or `3.0` for a fast cubic curve.
6. **Zero-Overhead Physics (C++ Backend)**:
   * **Linux**: Uses hardware event interrupts (`evdev`) and sleeps at **0% CPU** when the controller is at rest.
   * **Windows**: Dynamically loads XInput at runtime and uses high-resolution waitable timers for sub-millisecond precision.
   * **Math**: Avoids square roots on idle paths and uses SSE Reciprocal Square Root instructions (`_mm_rsqrt_ss`) to normalize active vectors in 1 CPU cycle.

---

## System Requirements

Before installing, make sure your system has the necessary compiler tools to build the low-latency C++ backend:

### 🐧 Linux Requirements
* **Python 3** (and `pip`)
* **Git**
* **CMake** (`sudo apt install cmake`)
* **C++ Compiler** (`sudo apt install build-essential`)

### 🪟 Windows Requirements
* **Python 3** (and `pip`)
* **Git**
* **CMake** (installed via [cmake.org](https://cmake.org/download/))
* **Visual Studio** (with the **"Desktop development with C++"** workload checked during installation)

---

## Installation & Running

### 1. Download & Install
Clone the repository and install the application in editable/development mode:
```bash
# Clone the repository
git clone https://github.com/<your-username>/TriggerCursor.git
cd TriggerCursor

# Install the package locally
pip install -e .
```
This registers the command `triggercursor` in your system path.

### 2. Run the Application
Once installed, launch the GUI from your terminal or command prompt:
```bash
triggercursor
```
On first launch, **TriggerCursor** will automatically compile the C++ daemon binary inside your standard user data folder (`~/.local/share/triggercursor` on Linux / `%APPDATA%/TriggerCursor` on Windows) and create your application shortcuts.

---

## 🐧 Linux Permissions Setup (Automated)

On Linux, the background daemon needs access to `/dev/uinput` to emulate hardware mouse clicks and movements:

* **Automated Setup (Recommended):** On first run, TriggerCursor will display a **"⚠️ Permissions missing"** banner. Simply click the **"Authorize"** button next to it. It will securely prompt for your system password to automatically set up the udev rules.
* **Manual Setup:** If you prefer setting it up manually, run the following commands in your terminal and log out/in:
  ```bash
  echo 'KERNEL=="uinput", GROUP="input", MODE="0660", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/99-trigger-cursor.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```

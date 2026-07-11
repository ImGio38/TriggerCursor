# TriggerCursor

A highly optimized, near-zero overhead controller-to-mouse driver built natively in **C++** with a sleek, modern desktop control interface built in **Python (CustomTkinter)**.

---

## Key Features & Customizations

1. **Standalone GUI (No Browser)**: The interface runs as a standalone desktop window on your screen. You do not need to open a web browser.
2. **Auto-Launch & Self-Closing**: Launching the GUI app automatically starts the C++ daemon in the background. Closing the GUI window terminates the background C++ process immediately. No terminal window needs to stay open.
3. **Application Menu Integration**: Upon launching the app for the first time, it automatically registers itself as a native desktop application under your Linux system application menu (**"TriggerCursor"** with a gamepad icon). You can search and launch it directly from your OS launcher.
4. **Custom Key Bindings**: Map individual controller buttons (A, B, X, Y) to actions (Left Click, Right Click, Middle Click, or Disabled) using clean dropdown menus.
5. **Adjustable Sensitivity & Acceleration**:
   * **Sensitivity**: Configure down to fractionals (e.g. `0.5` to `20.0`) for precise control.
   * **Acceleration Curve**: Choose your acceleration power. Drag it to `1.0` for a flat linear response, `2.0` for a gentle quadratic response, or `3.0` for a fast cubic curve.
6. **Zero-Overhead Physics (C++ Backend)**:
   * **Linux**: Uses hardware event interrupts (`evdev`) and sleeps at **0% CPU** when the controller is at rest.
   * **Windows**: Dynamically loads XInput at runtime and uses high-resolution waitable timers for sub-millisecond precision.
   * **Math**: Avoids square roots on idle paths and uses SSE Reciprocal Square Root instructions (`_mm_rsqrt_ss`) to normalize active vectors in 1 CPU cycle.

---

## Installation & Running

### 1. Install as a Python Package
You can install **TriggerCursor** in editable/development mode or directly:
```bash
# Clone the repository
git clone https://github.com/<your-username>/TriggerCursor.git
cd TriggerCursor

# Install the package locally
pip install -e .
```
This registers the command `triggercursor` in your path.

### 2. Run the Application
Once installed, run it from your terminal:
```bash
triggercursor
```
On first launch, **TriggerCursor** will automatically compile the C++ daemon binary inside your standard user data folder (e.g., `~/.local/share/triggercursor/build` on Linux) and register the desktop application shortcut under your OS application menu.

### 3. Linux Permissions Setup
If the application displays a warning message stating "Permissions missing", you can configure your system to run the daemon without root privileges:
* Click the **"Authorize"** button directly inside the GUI, which will elevate via polkit, OR
* Run the following commands manually to add a udev rule and join the `input` group:
  ```bash
  echo 'KERNEL=="uinput", GROUP="input", MODE="0660", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/99-trigger-cursor.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```
  *(Log out of your desktop environment and log back in for changes to take effect).*

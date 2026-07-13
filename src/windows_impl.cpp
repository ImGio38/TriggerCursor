#ifdef _WIN32

#include "controller_daemon.h"
#include "math_utils.h"

#include <iostream>
#include <windows.h>
#include <xinput.h>
#include <vector>

// Typedef for XInputGetState function pointer (dynamic loading)
typedef DWORD (WINAPI* XInputGetState_t)(DWORD, XINPUT_STATE*);

static XInputGetState_t pXInputGetState = nullptr;
static HMODULE hXInputLib = nullptr;

// Dynamically load XInput DLL at runtime to remove static library requirements
static bool LoadXInput() {
    // Try newer XInput 1.4 (Windows 8/10/11)
    hXInputLib = LoadLibraryW(L"xinput1_4.dll");
    if (!hXInputLib) {
        // Try standard XInput 1.3 (DirectX runtime installs)
        hXInputLib = LoadLibraryW(L"xinput1_3.dll");
    }
    if (!hXInputLib) {
        // Try older fallback
        hXInputLib = LoadLibraryW(L"xinput9_1_0.dll");
    }

    if (hXInputLib) {
        pXInputGetState = reinterpret_cast<XInputGetState_t>(GetProcAddress(hXInputLib, "XInputGetState"));
    }

    return pXInputGetState != nullptr;
}

static void UnloadXInput() {
    if (hXInputLib) {
        FreeLibrary(hXInputLib);
        hXInputLib = nullptr;
        pXInputGetState = nullptr;
    }
}

// Send mouse movement to the OS
static void SendRelativeMove(int dx, int dy) {
    if (dx == 0 && dy == 0) return;

    INPUT input;
    ZeroMemory(&input, sizeof(INPUT));
    input.type = INPUT_MOUSE;
    input.mi.dx = dx;
    input.mi.dy = dy;
    input.mi.dwFlags = MOUSEEVENTF_MOVE;

    SendInput(1, &input, sizeof(INPUT));
}

// Send mouse button press/release
static void SendButtonClick(DWORD dwFlags) {
    INPUT input;
    ZeroMemory(&input, sizeof(INPUT));
    input.type = INPUT_MOUSE;
    input.mi.dwFlags = dwFlags;

    SendInput(1, &input, sizeof(INPUT));
}

// Send keyboard key press/release
static void SendKeyClick(WORD keycode, bool is_pressed) {
    INPUT input;
    ZeroMemory(&input, sizeof(INPUT));
    input.type = INPUT_KEYBOARD;
    input.ki.wVk = keycode;
    input.ki.dwFlags = is_pressed ? 0 : KEYEVENTF_KEYUP;

    SendInput(1, &input, sizeof(INPUT));
}

// Execute macro action sequences
static void ExecuteActions(const std::vector<MacroAction>& actions) {
    for (const auto& act : actions) {
        if (act.type == ACTION_MOUSE_DOWN || act.type == ACTION_MOUSE_UP) {
            DWORD flag = 0;
            if (act.value == 1) flag = (act.type == ACTION_MOUSE_DOWN) ? MOUSEEVENTF_LEFTDOWN : MOUSEEVENTF_LEFTUP;
            else if (act.value == 2) flag = (act.type == ACTION_MOUSE_DOWN) ? MOUSEEVENTF_RIGHTDOWN : MOUSEEVENTF_RIGHTUP;
            else if (act.value == 3) flag = (act.type == ACTION_MOUSE_DOWN) ? MOUSEEVENTF_MIDDLEDOWN : MOUSEEVENTF_MIDDLEUP;
            
            if (flag != 0) {
                SendButtonClick(flag);
            }
        }
        else if (act.type == ACTION_KEY_DOWN || act.type == ACTION_KEY_UP) {
            SendKeyClick(static_cast<WORD>(act.value), (act.type == ACTION_KEY_DOWN));
        }
        else if (act.type == ACTION_DELAY) {
            Sleep(act.value);
        }
    }
}

// Ensure high-resolution waitable timer constants are present
#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002
#endif

#ifndef XINPUT_GAMEPAD_TRIGGER_THRESHOLD
#define XINPUT_GAMEPAD_TRIGGER_THRESHOLD 30
#endif

int RunWindowsDaemon(SharedConfig& config) {
    if (!LoadXInput()) {
        std::cerr << "[Windows Daemon] Failed to load XInput DLL. Is a controller driver installed?" << std::endl;
        return -1;
    }

    std::cout << "[Windows Daemon] Dynamically loaded XInput." << std::endl;

    // 1. Setup scheduler resolution
    HANDLE hTimer = CreateWaitableTimerExW(
        NULL, NULL, 
        CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, 
        TIMER_ALL_ACCESS
    );

    bool using_global_period = false;
    if (hTimer == NULL) {
        // Fallback: Set system-wide timer resolution to 1ms
        std::cout << "[Windows Daemon] High-res timer not supported. Falling back to timeBeginPeriod(1)." << std::endl;
        timeBeginPeriod(1);
        using_global_period = true;
    } else {
        // Set waitable timer to trigger every poll_rate_ms
        LARGE_INTEGER liDueTime;
        liDueTime.QuadPart = -static_cast<LONGLONG>(config.poll_rate_ms.load()) * 10000LL; // 100ns units
        SetWaitableTimer(hTimer, &liDueTime, config.poll_rate_ms.load(), NULL, NULL, FALSE);
        std::cout << "[Windows Daemon] Created high-resolution waitable timer (" << config.poll_rate_ms.load() << "ms)." << std::endl;
    }

    std::cout << "[Windows Daemon] Running loop..." << std::endl;

    // Track connection state
    bool was_connected = false;

    // Track button states to send edge-triggered click events
    bool last_states[16] = {false};

    // Accumulators for fractional pixel movements
    float accum_x = 0.0f;
    float accum_y = 0.0f;

    while (config.running.load()) {
        // Handle forced controller refresh/reconnect request
        if (config.force_refresh.load()) {
            was_connected = false;
            std::fill(std::begin(last_states), std::end(last_states), false);
            config.set_controller("None", "None");
            config.force_refresh.store(false);
        }

        // Sleep cycle
        if (!config.enabled.load()) {
            // Emulation disabled, drop down to low frequency check (0% CPU)
            Sleep(100);
            continue;
        }

        if (hTimer != NULL) {
            WaitForSingleObject(hTimer, INFINITE);
        } else {
            Sleep(config.poll_rate_ms.load());
        }

        // Query gamepad state
        XINPUT_STATE state;
        ZeroMemory(&state, sizeof(XINPUT_STATE));

        DWORD result = ERROR_DEVICE_NOT_CONNECTED;
        DWORD active_user_idx = 0;
        for (DWORD i = 0; i < 4; ++i) {
            result = pXInputGetState(i, &state);
            if (result == ERROR_SUCCESS) {
                active_user_idx = i;
                break;
            }
        }

        if (result != ERROR_SUCCESS) {
            // Controller disconnected or offline
            if (was_connected) {
                std::cout << "[Windows Daemon] Controller disconnected." << std::endl;
                config.set_controller("None", "None");
                was_connected = false;
                std::fill(std::begin(last_states), std::end(last_states), false);
            }
            Sleep(500);
            continue;
        }

        if (!was_connected) {
            std::cout << "[Windows Daemon] Controller connected (User Index: " << active_user_idx << ")." << std::endl;
            config.set_controller("Xbox Controller", "Xbox");
            was_connected = true;
        }

        // Read all 16 button states
        bool current_states[16];
        current_states[0] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_A) != 0;
        current_states[1] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_B) != 0;
        current_states[2] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_X) != 0;
        current_states[3] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_Y) != 0;
        current_states[4] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_LEFT_SHOULDER) != 0;
        current_states[5] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_RIGHT_SHOULDER) != 0;
        current_states[6] = state.Gamepad.bLeftTrigger > XINPUT_GAMEPAD_TRIGGER_THRESHOLD;
        current_states[7] = state.Gamepad.bRightTrigger > XINPUT_GAMEPAD_TRIGGER_THRESHOLD;
        current_states[8] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_LEFT_THUMB) != 0;
        current_states[9] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_RIGHT_THUMB) != 0;
        current_states[10] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_BACK) != 0;
        current_states[11] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_START) != 0;
        current_states[12] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_DPAD_UP) != 0;
        current_states[13] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_DPAD_DOWN) != 0;
        current_states[14] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_DPAD_LEFT) != 0;
        current_states[15] = (state.Gamepad.wButtons & XINPUT_GAMEPAD_DPAD_RIGHT) != 0;

        // Process edge-triggered button actions
        for (int i = 0; i < 16; ++i) {
            if (current_states[i] != last_states[i]) {
                if (config.enabled.load()) {
                    std::vector<MacroAction> actions;
                    std::vector<MacroAction> release_dummy;
                    if (current_states[i]) {
                        config.get_button_mapping(i, actions, release_dummy);
                    } else {
                        config.get_button_mapping(i, release_dummy, actions);
                    }
                    ExecuteActions(actions);
                }
                last_states[i] = current_states[i];
            }
        }

        // Normalize axes: XInput values range from -32768 to 32767
        float norm_x = static_cast<float>(state.Gamepad.sThumbLX) / 32768.0f;
        float norm_y = static_cast<float>(state.Gamepad.sThumbLY) / 32768.0f;

        // Ensure clamps
        if (norm_x > 1.0f) norm_x = 1.0f;
        else if (norm_x < -1.0f) norm_x = -1.0f;
        if (norm_y > 1.0f) norm_y = 1.0f;
        else if (norm_y < -1.0f) norm_y = -1.0f;

        // Process physics (only if enabled)
        if (config.enabled.load()) {
            float out_dx = 0.0f;
            float out_dy = 0.0f;
            MathUtils::ProcessJoystick(norm_x, norm_y, config.deadzone.load(), config.sensitivity.load(), config.curve_power.load(), out_dx, out_dy);

            // Windows Coordinate Inversion: Screen Y runs downwards, joystick Y runs upwards.
            out_dy = -out_dy;

            if (config.invert_x.load()) out_dx = -out_dx;
            if (config.invert_y.load()) out_dy = -out_dy;

            accum_x += out_dx;
            accum_y += out_dy;

            int move_x = static_cast<int>(accum_x);
            int move_y = static_cast<int>(accum_y);

            accum_x -= move_x;
            accum_y -= move_y;

            if (move_x != 0 || move_y != 0) {
                SendRelativeMove(move_x, move_y);
            }
        } else {
            accum_x = 0.0f;
            accum_y = 0.0f;
        }
    }

    // Cleanup
    if (using_global_period) {
        timeEndPeriod(1);
    }
    if (hTimer != NULL) {
        CloseHandle(hTimer);
    }
    UnloadXInput();
    return 0;
}

#endif // _WIN32

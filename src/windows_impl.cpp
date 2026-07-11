#ifdef _WIN32

#include "controller_daemon.h"
#include "math_utils.h"

#include <iostream>
#include <windows.h>
#include <xinput.h>

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

// Ensure high-resolution waitable timer constants are present
#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002
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
    std::cout << "[Windows Daemon] Mapping:" << std::endl;
    std::cout << "  Left Joystick -> Mouse Movement" << std::endl;
    std::cout << "  Button A -> Left Click" << std::endl;
    std::cout << "  Button B -> Right Click" << std::endl;
    std::cout << "  Button X -> Middle Click" << std::endl;

    // Track button states to send edge-triggered click events
    bool last_a = false;
    bool last_b = false;
    bool last_x = false;
    bool last_y = false;

    // Accumulators for fractional pixel movements
    float accum_x = 0.0f;
    float accum_y = 0.0f;

    while (config.running.load()) {
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

        DWORD result = pXInputGetState(0, &state);
        if (result != ERROR_SUCCESS) {
            // Controller disconnected or offline, sleep a bit longer to prevent hot-looping
            if (config.verbose.load()) {
                std::cout << "[Windows Daemon] Controller disconnected. Re-trying..." << std::endl;
            }
            Sleep(500);
            continue;
        }

        // Process Buttons (Edge-triggered)
        bool btn_a = (state.Gamepad.wButtons & XINPUT_GAMEPAD_A) != 0;
        bool btn_b = (state.Gamepad.wButtons & XINPUT_GAMEPAD_B) != 0;
        bool btn_x = (state.Gamepad.wButtons & XINPUT_GAMEPAD_X) != 0;
        bool btn_y = (state.Gamepad.wButtons & XINPUT_GAMEPAD_Y) != 0;

        auto send_win_btn = [&](bool pressed, bool& last_pressed, int action) {
            if (pressed != last_pressed) {
                if (config.enabled.load() && action > 0) {
                    DWORD down_flag = 0, up_flag = 0;
                    if (action == 1) { down_flag = MOUSEEVENTF_LEFTDOWN; up_flag = MOUSEEVENTF_LEFTUP; }
                    else if (action == 2) { down_flag = MOUSEEVENTF_RIGHTDOWN; up_flag = MOUSEEVENTF_RIGHTUP; }
                    else if (action == 3) { down_flag = MOUSEEVENTF_MIDDLEDOWN; up_flag = MOUSEEVENTF_MIDDLEUP; }
                    
                    if (down_flag != 0) {
                        SendButtonClick(pressed ? down_flag : up_flag);
                    }
                }
                last_pressed = pressed;
            }
        };

        send_win_btn(btn_a, last_a, config.key_a.load());
        send_win_btn(btn_b, last_b, config.key_b.load());
        send_win_btn(btn_x, last_x, config.key_x.load());
        send_win_btn(btn_y, last_y, config.key_y.load());

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

#ifdef _WIN32

#include "controller_daemon.h"
#include "math_utils.h"

#include <iostream>
#include <windows.h>
#include <mmsystem.h>
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

        // 1. Query XInput first
        XINPUT_STATE xstate;
        ZeroMemory(&xstate, sizeof(XINPUT_STATE));

        DWORD xinput_result = ERROR_DEVICE_NOT_CONNECTED;
        DWORD active_user_idx = 0;
        for (DWORD i = 0; i < 4; ++i) {
            xinput_result = pXInputGetState(i, &xstate);
            if (xinput_result == ERROR_SUCCESS) {
                active_user_idx = i;
                break;
            }
        }

        bool current_states[16] = {false};
        float norm_x = 0.0f;
        float norm_y = 0.0f;
        bool device_connected = false;
        std::string current_name = "None";
        std::string current_type = "None";

        if (xinput_result == ERROR_SUCCESS) {
            device_connected = true;
            current_name = "Xbox Controller (XInput)";
            current_type = "Xbox";

            current_states[0] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_A) != 0;
            current_states[1] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_B) != 0;
            current_states[2] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_X) != 0;
            current_states[3] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_Y) != 0;
            current_states[4] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_LEFT_SHOULDER) != 0;
            current_states[5] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_RIGHT_SHOULDER) != 0;
            current_states[6] = xstate.Gamepad.bLeftTrigger > XINPUT_GAMEPAD_TRIGGER_THRESHOLD;
            current_states[7] = xstate.Gamepad.bRightTrigger > XINPUT_GAMEPAD_TRIGGER_THRESHOLD;
            current_states[8] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_LEFT_THUMB) != 0;
            current_states[9] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_RIGHT_THUMB) != 0;
            current_states[10] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_BACK) != 0;
            current_states[11] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_START) != 0;
            current_states[12] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_DPAD_UP) != 0;
            current_states[13] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_DPAD_DOWN) != 0;
            current_states[14] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_DPAD_LEFT) != 0;
            current_states[15] = (xstate.Gamepad.wButtons & XINPUT_GAMEPAD_DPAD_RIGHT) != 0;

            norm_x = static_cast<float>(xstate.Gamepad.sThumbLX) / 32768.0f;
            norm_y = static_cast<float>(xstate.Gamepad.sThumbLY) / 32768.0f;
            
            if (norm_x > 1.0f) norm_x = 1.0f;
            else if (norm_x < -1.0f) norm_x = -1.0f;
            if (norm_y > 1.0f) norm_y = 1.0f;
            else if (norm_y < -1.0f) norm_y = -1.0f;
        } 
        else {
            // 2. Query WinMM Joysticks
            UINT num_devs = joyGetNumDevs();
            JOYINFOEX joy_info;
            std::memset(&joy_info, 0, sizeof(joy_info));
            joy_info.dwSize = sizeof(JOYINFOEX);
            joy_info.dwFlags = JOY_RETURNALL;

            for (UINT i = 0; i < 16 && i < num_devs; ++i) {
                JOYCAPSW caps;
                if (joyGetDevCapsW(i, &caps, sizeof(caps)) == JOYERR_NOERROR) {
                    if (joyGetPosEx(i, &joy_info) == JOYERR_NOERROR) {
                        device_connected = true;
                        
                        // Convert WCHAR product name to UTF-8
                        char name_mb[256] = {0};
                        WideCharToMultiByte(CP_UTF8, 0, caps.szPname, -1, name_mb, sizeof(name_mb) - 1, NULL, NULL);
                        current_name = name_mb;
                        
                        // Detect layout type
                        current_type = "Xbox";
                        std::string lower_name = current_name;
                        for (char &c : lower_name) c = std::tolower(c);
                        
                        bool is_playstation = false;
                        if (lower_name.find("playstation") != std::string::npos || 
                            lower_name.find("sony") != std::string::npos || 
                            lower_name.find("dualshock") != std::string::npos || 
                            lower_name.find("dualsense") != std::string::npos || 
                            lower_name.find("ps4") != std::string::npos || 
                            lower_name.find("ps5") != std::string::npos ||
                            lower_name.find("wireless controller") != std::string::npos) {
                            current_type = "PlayStation";
                            is_playstation = true;
                        } else if (lower_name.find("nintendo") != std::string::npos || 
                                   lower_name.find("switch") != std::string::npos) {
                            current_type = "Nintendo";
                        }

                        // Map buttons
                        if (is_playstation) {
                            current_states[0] = (joy_info.dwButtons & JOY_BUTTON2) != 0; // Cross (South)
                            current_states[1] = (joy_info.dwButtons & JOY_BUTTON3) != 0; // Circle (East)
                            current_states[2] = (joy_info.dwButtons & JOY_BUTTON1) != 0; // Square (West)
                            current_states[3] = (joy_info.dwButtons & JOY_BUTTON4) != 0; // Triangle (North)
                            current_states[4] = (joy_info.dwButtons & JOY_BUTTON5) != 0; // L1 (LB)
                            current_states[5] = (joy_info.dwButtons & JOY_BUTTON6) != 0; // R1 (RB)
                            current_states[6] = (joy_info.dwButtons & JOY_BUTTON7) != 0; // L2 (LT)
                            current_states[7] = (joy_info.dwButtons & JOY_BUTTON8) != 0; // R2 (RT)
                            current_states[8] = (joy_info.dwButtons & JOY_BUTTON11) != 0; // L3 (LS)
                            current_states[9] = (joy_info.dwButtons & JOY_BUTTON12) != 0; // R3 (RS)
                            current_states[10] = (joy_info.dwButtons & JOY_BUTTON9) != 0; // Share (Back)
                            current_states[11] = (joy_info.dwButtons & JOY_BUTTON10) != 0; // Options (Start)
                        } else {
                            // Generic / Xbox-like fallback
                            current_states[0] = (joy_info.dwButtons & JOY_BUTTON1) != 0; 
                            current_states[1] = (joy_info.dwButtons & JOY_BUTTON2) != 0; 
                            current_states[2] = (joy_info.dwButtons & JOY_BUTTON3) != 0; 
                            current_states[3] = (joy_info.dwButtons & JOY_BUTTON4) != 0; 
                            current_states[4] = (joy_info.dwButtons & JOY_BUTTON5) != 0; 
                            current_states[5] = (joy_info.dwButtons & JOY_BUTTON6) != 0; 
                            current_states[6] = (joy_info.dwButtons & JOY_BUTTON7) != 0; 
                            current_states[7] = (joy_info.dwButtons & JOY_BUTTON8) != 0; 
                            current_states[8] = (joy_info.dwButtons & JOY_BUTTON9) != 0; 
                            current_states[9] = (joy_info.dwButtons & JOY_BUTTON10) != 0; 
                            current_states[10] = (joy_info.dwButtons & JOY_BUTTON11) != 0; 
                            current_states[11] = (joy_info.dwButtons & JOY_BUTTON12) != 0; 
                        }

                        // Map POV Hat to D-pad
                        if (joy_info.dwPOV != JOY_POVCENTERED) {
                            current_states[12] = (joy_info.dwPOV >= 31500 || joy_info.dwPOV <= 4500);  // Up
                            current_states[13] = (joy_info.dwPOV >= 13500 && joy_info.dwPOV <= 22500); // Down
                            current_states[14] = (joy_info.dwPOV >= 22500 && joy_info.dwPOV <= 31500); // Left
                            current_states[15] = (joy_info.dwPOV >= 4500 && joy_info.dwPOV <= 13500);   // Right
                        }

                        // Map left stick axes (WinMM dwXpos/dwYpos range from 0 to 65535, center is 32768)
                        norm_x = (static_cast<float>(joy_info.dwXpos) - 32768.0f) / 32768.0f;
                        // Invert Y because up is 0 and down is 65535 in WinMM
                        norm_y = -(static_cast<float>(joy_info.dwYpos) - 32768.0f) / 32768.0f;

                        if (norm_x > 1.0f) norm_x = 1.0f;
                        else if (norm_x < -1.0f) norm_x = -1.0f;
                        if (norm_y > 1.0f) norm_y = 1.0f;
                        else if (norm_y < -1.0f) norm_y = -1.0f;

                        break;
                    }
                }
            }
        }

        if (!device_connected) {
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
            std::cout << "[Windows Daemon] Controller connected: " << current_name << " (" << current_type << ")." << std::endl;
            config.set_controller(current_name, current_type);
            was_connected = true;
        }

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

#ifndef CONTROLLER_DAEMON_H
#define CONTROLLER_DAEMON_H

#include <atomic>
#include <string>
#include <vector>
#include <mutex>
#include <cstring>

enum ActionType {
    ACTION_NONE = 0,
    ACTION_MOUSE_DOWN = 1,
    ACTION_MOUSE_UP = 2,
    ACTION_KEY_DOWN = 3,
    ACTION_KEY_UP = 4,
    ACTION_DELAY = 5
};

struct MacroAction {
    ActionType type;
    int value;
};

// Thread-safe configuration settings shared between HTTP Server and Input loops
struct SharedConfig {
    std::atomic<float> deadzone{0.20f};      // 20% deadzone
    std::atomic<float> sensitivity{5.0f};    // Speed multiplier
    std::atomic<int> poll_rate_ms{4};        // Polling interval
    std::atomic<bool> enabled{true};         // Emulation ON/OFF state
    std::atomic<bool> verbose{false};        // Debug logs state changes
    std::atomic<bool> running{true};         // Keep daemon alive
    
    std::atomic<float> curve_power{2.0f};    // Acceleration curve power
    std::atomic<int> key_a{1};               // Keep for compatibility, though we use the index system
    std::atomic<int> key_b{2};
    std::atomic<int> key_x{3};
    std::atomic<int> key_y{0};
    std::atomic<bool> invert_x{false};       // Invert X axis
    std::atomic<bool> invert_y{false};       // Invert Y axis
    std::atomic<bool> force_refresh{false};  // Re-detect/refresh controller

    // 16 button mappings (press and release sequences)
    std::mutex mappings_mtx;
    std::vector<MacroAction> press_mappings[16];
    std::vector<MacroAction> release_mappings[16];

    // Active controller info
    std::mutex controller_mtx;
    char controller_name[256];
    char controller_type[64];

    SharedConfig() {
        std::strncpy(controller_name, "None", sizeof(controller_name));
        std::strncpy(controller_type, "None", sizeof(controller_type));

        // Default mappings:
        // Button A (0) -> Left Click
        press_mappings[0] = {{ACTION_MOUSE_DOWN, 1}};
        release_mappings[0] = {{ACTION_MOUSE_UP, 1}};
        
        // Button B (1) -> Right Click
        press_mappings[1] = {{ACTION_MOUSE_DOWN, 2}};
        release_mappings[1] = {{ACTION_MOUSE_UP, 2}};
    }

    void set_controller(const std::string& name, const std::string& type) {
        std::lock_guard<std::mutex> lock(controller_mtx);
        std::strncpy(controller_name, name.c_str(), sizeof(controller_name) - 1);
        controller_name[sizeof(controller_name) - 1] = '\0';
        std::strncpy(controller_type, type.c_str(), sizeof(controller_type) - 1);
        controller_type[sizeof(controller_type) - 1] = '\0';
    }

    void get_controller(std::string& name, std::string& type) {
        std::lock_guard<std::mutex> lock(controller_mtx);
        name = controller_name;
        type = controller_type;
    }

    void set_button_mapping(int btn_idx, const std::vector<MacroAction>& press, const std::vector<MacroAction>& release) {
        if (btn_idx < 0 || btn_idx >= 16) return;
        std::lock_guard<std::mutex> lock(mappings_mtx);
        press_mappings[btn_idx] = press;
        release_mappings[btn_idx] = release;
    }

    void get_button_mapping(int btn_idx, std::vector<MacroAction>& press, std::vector<MacroAction>& release) {
        if (btn_idx < 0 || btn_idx >= 16) return;
        std::lock_guard<std::mutex> lock(mappings_mtx);
        press = press_mappings[btn_idx];
        release = release_mappings[btn_idx];
    }

    std::string serialize_mappings(int btn_idx) {
        std::vector<MacroAction> press, release;
        get_button_mapping(btn_idx, press, release);
        
        std::string res = "\"press\":\"";
        for (size_t i = 0; i < press.size(); ++i) {
            res += std::to_string(press[i].type) + ":" + std::to_string(press[i].value);
            if (i + 1 < press.size()) res += ",";
        }
        res += "\",\"release\":\"";
        for (size_t i = 0; i < release.size(); ++i) {
            res += std::to_string(release[i].type) + ":" + std::to_string(release[i].value);
            if (i + 1 < release.size()) res += ",";
        }
        res += "\"";
        return res;
    }
};

// OS-specific entry points
#ifdef __linux__
int RunLinuxDaemon(SharedConfig& config);
#elif defined(_WIN32)
int RunWindowsDaemon(SharedConfig& config);
#endif

#endif // CONTROLLER_DAEMON_H

#ifndef CONTROLLER_DAEMON_H
#define CONTROLLER_DAEMON_H

// Configuration defaults
#include <atomic>

// Thread-safe configuration settings shared between HTTP Server and Input loops
struct SharedConfig {
    std::atomic<float> deadzone{0.20f};      // 20% deadzone
    std::atomic<float> sensitivity{5.0f};    // Lower default speed multiplier (was 15.0f)
    std::atomic<int> poll_rate_ms{4};        // Capped loop rate (4ms = 250Hz)
    std::atomic<bool> enabled{true};         // Emulation ON/OFF state
    std::atomic<bool> verbose{false};        // Debug logs state changes
    std::atomic<bool> running{true};         // Keep daemon alive
    
    std::atomic<float> curve_power{2.0f};    // Acceleration exponent (1.0 = linear, 2.0 = quadratic, 3.0 = cubic)
    std::atomic<int> key_a{1};               // 1 = Left Click, 2 = Right Click, 3 = Middle Click, 0 = Unmapped
    std::atomic<int> key_b{2};
    std::atomic<int> key_x{3};
    std::atomic<int> key_y{0};
    std::atomic<bool> invert_x{false};       // Invert X axis deflection
    std::atomic<bool> invert_y{false};       // Invert Y axis deflection
};

// OS-specific entry points
#ifdef __linux__
int RunLinuxDaemon(SharedConfig& config);
#elif defined(_WIN32)
int RunWindowsDaemon(SharedConfig& config);
#endif

#endif // CONTROLLER_DAEMON_H

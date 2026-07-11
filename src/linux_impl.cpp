#ifdef __linux__

#include "controller_daemon.h"
#include "math_utils.h"

#include <iostream>
#include <string>
#include <vector>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <poll.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/input.h>
#include <linux/uinput.h>
#include <sys/prctl.h>
#include <signal.h>
#include <cctype>
#include <thread>
#include <chrono>

// Helper to check capability bit
static bool CheckBit(int bit, const unsigned long* array) {
    return (array[bit / (8 * sizeof(unsigned long))] & (1UL << (bit % (8 * sizeof(unsigned long)))));
}

// Auto-detect a gamepad device path
static std::string FindGamepadDevice(bool verbose) {
    std::string best_path = "";
    int best_priority = -1; // -1: none, 0: virtual, 1: physical

    for (int i = 0; i < 64; ++i) {
        std::string path = "/dev/input/event" + std::to_string(i);
        int fd = open(path.c_str(), O_RDONLY | O_NONBLOCK);
        if (fd < 0) continue;

        unsigned long key_bits[KEY_MAX / (8 * sizeof(unsigned long))] = {0};
        if (ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(key_bits)), key_bits) >= 0) {
            // Gamepads will support BTN_GAMEPAD
            if (CheckBit(BTN_GAMEPAD, key_bits)) {
                char name[256] = "Unknown Gamepad";
                ioctl(fd, EVIOCGNAME(sizeof(name)), name);
                std::string name_str(name);
                
                // Skip our own virtual mouse/keyboard device to avoid feedback loop
                if (name_str.find("Virtual") != std::string::npos || 
                    name_str.find("Controller-to-Mouse") != std::string::npos) {
                    close(fd);
                    continue;
                }
                
                struct input_id id;
                int priority = 0; // Default to virtual
                if (ioctl(fd, EVIOCGID, &id) >= 0) {
                    if (id.bustype == 0x03 || id.bustype == 0x05) { // BUS_USB (0x03) or BUS_BLUETOOTH (0x05)
                        priority = 1; // Physical hardware device
                    }
                }
                
                if (priority > best_priority) {
                    best_priority = priority;
                    best_path = path;
                    if (verbose) {
                        std::cout << "[Linux Daemon] Found candidate gamepad: " << name 
                                  << " at " << path << " (priority: " << priority << ")" << std::endl;
                    }
                    // If we found a physical gamepad, we can stop search early
                    if (priority == 1) {
                        close(fd);
                        break;
                    }
                }
            }
        }
        close(fd);
    }
    return best_path;
}

// Helper to normalize gamepad axes using absolute coordinate info
static float NormalizeAxis(int32_t raw_val, const struct input_absinfo& info) {
    if (info.maximum == info.minimum) return 0.0f;
    float center = (info.maximum + info.minimum) / 2.0f;
    float range = (info.maximum - info.minimum) / 2.0f;
    float norm = (static_cast<float>(raw_val) - center) / range;
    if (norm > 1.0f) return 1.0f;
    if (norm < -1.0f) return -1.0f;
    return norm;
}

// Inject relative move events
static void SendRelativeMove(int uinput_fd, int dx, int dy) {
    struct input_event evs[3];
    std::memset(evs, 0, sizeof(evs));
    int count = 0;

    if (dx != 0) {
        evs[count].type = EV_REL;
        evs[count].code = REL_X;
        evs[count].value = dx;
        count++;
    }
    if (dy != 0) {
        evs[count].type = EV_REL;
        evs[count].code = REL_Y;
        evs[count].value = dy;
        count++;
    }
    if (count > 0) {
        evs[count].type = EV_SYN;
        evs[count].code = SYN_REPORT;
        evs[count].value = 0;
        count++;
        if (write(uinput_fd, evs, count * sizeof(struct input_event)) < 0) {
            std::cerr << "[Linux Daemon] Error writing relative move to uinput" << std::endl;
        }
    }
}

// Inject mouse button click events
static void SendButtonClick(int uinput_fd, int mouse_btn, int is_pressed) {
    struct input_event evs[2];
    std::memset(evs, 0, sizeof(evs));

    evs[0].type = EV_KEY;
    evs[0].code = mouse_btn;
    evs[0].value = is_pressed;

    evs[1].type = EV_SYN;
    evs[1].code = SYN_REPORT;
    evs[1].value = 0;

    if (write(uinput_fd, evs, sizeof(evs)) < 0) {
        std::cerr << "[Linux Daemon] Error writing button click to uinput" << std::endl;
    }
}

// Inject keyboard key press/release
static void SendKeyClick(int uinput_fd, int keycode, int is_pressed) {
    struct input_event evs[2];
    std::memset(evs, 0, sizeof(evs));

    evs[0].type = EV_KEY;
    evs[0].code = keycode;
    evs[0].value = is_pressed;

    evs[1].type = EV_SYN;
    evs[1].code = SYN_REPORT;
    evs[1].value = 0;

    if (write(uinput_fd, evs, sizeof(evs)) < 0) {
        std::cerr << "[Linux Daemon] Error writing key to uinput" << std::endl;
    }
}

// Execute macro action sequences
static void ExecuteActions(int uinput_fd, const std::vector<MacroAction>& actions) {
    for (const auto& act : actions) {
        if (act.type == ACTION_MOUSE_DOWN || act.type == ACTION_MOUSE_UP) {
            int mouse_btn = -1;
            if (act.value == 1) mouse_btn = BTN_LEFT;
            else if (act.value == 2) mouse_btn = BTN_RIGHT;
            else if (act.value == 3) mouse_btn = BTN_MIDDLE;
            
            if (mouse_btn != -1) {
                SendButtonClick(uinput_fd, mouse_btn, (act.type == ACTION_MOUSE_DOWN) ? 1 : 0);
            }
        }
        else if (act.type == ACTION_KEY_DOWN || act.type == ACTION_KEY_UP) {
            SendKeyClick(uinput_fd, act.value, (act.type == ACTION_KEY_DOWN) ? 1 : 0);
        }
        else if (act.type == ACTION_DELAY) {
            std::this_thread::sleep_for(std::chrono::milliseconds(act.value));
        }
    }
}

// Map Linux input key code to 16 button index
static int GetButtonIndexLinux(uint16_t code) {
    switch (code) {
        case BTN_SOUTH: return 0;   // A / Cross
        case BTN_EAST: return 1;    // B / Circle
        case BTN_WEST: return 2;    // X / Square
        case BTN_NORTH: return 3;   // Y / Triangle
        case BTN_TL: return 4;      // LB / L1
        case BTN_TR: return 5;      // RB / R1
        case BTN_TL2: return 6;     // LT / L2
        case BTN_TR2: return 7;     // RT / R2
        case BTN_THUMBL: return 8;  // LS / L3
        case BTN_THUMBR: return 9;  // RS / R3
        case BTN_SELECT: return 10; // Back / Share
        case BTN_START: return 11;  // Start / Options
        default: return -1;
    }
}

int RunLinuxDaemon(SharedConfig& config) {
    // Terminate the daemon immediately if the parent process (Python GUI) dies
    prctl(PR_SET_PDEATHSIG, SIGTERM);

    std::cout << "[Linux Daemon] Successfully initialized. Waiting for gamepad..." << std::endl;

    int gamepad_fd = -1;
    std::string dev_path;
    
    // Limits
    struct input_absinfo abs_x_info;
    struct input_absinfo abs_y_info;
    std::memset(&abs_x_info, 0, sizeof(abs_x_info));
    std::memset(&abs_y_info, 0, sizeof(abs_y_info));

    // Setup Virtual Mouse & Keyboard (uinput)
    int uinput_fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (uinput_fd < 0) {
        std::cerr << "[Linux Daemon] Failed to open /dev/uinput (Permission denied? Run with sudo)." << std::endl;
        return -1;
    }

    // Enable relative movement
    ioctl(uinput_fd, UI_SET_EVBIT, EV_REL);
    ioctl(uinput_fd, UI_SET_RELBIT, REL_X);
    ioctl(uinput_fd, UI_SET_RELBIT, REL_Y);

    // Enable key events (including mouse buttons and keyboard keys)
    ioctl(uinput_fd, UI_SET_EVBIT, EV_KEY);
    ioctl(uinput_fd, UI_SET_KEYBIT, BTN_LEFT);
    ioctl(uinput_fd, UI_SET_KEYBIT, BTN_RIGHT);
    ioctl(uinput_fd, UI_SET_KEYBIT, BTN_MIDDLE);

    // Register all standard keyboard keys for keyboard/macro emulation
    // (We stop at 247 to avoid registering gamepad/joystick buttons which starts at 272/288.
    // This prevents libinput from misclassifying the virtual mouse/keyboard as a gamepad).
    for (int key = 1; key <= 247; ++key) {
        ioctl(uinput_fd, UI_SET_KEYBIT, key);
    }

    struct uinput_setup usetup;
    std::memset(&usetup, 0, sizeof(usetup));
    usetup.id.bustype = BUS_USB;
    usetup.id.vendor  = 0x1234; // Dummy IDs
    usetup.id.product = 0x5678;
    std::strncpy(usetup.name, "Controller-to-Mouse Virtual input device", UINPUT_MAX_NAME_SIZE);

    if (ioctl(uinput_fd, UI_DEV_SETUP, &usetup) < 0 || ioctl(uinput_fd, UI_DEV_CREATE) < 0) {
        std::cerr << "[Linux Daemon] Failed to create virtual uinput device." << std::endl;
        close(uinput_fd);
        return -1;
    }

    // Accumulators for fractional movement
    float accum_x = 0.0f;
    float accum_y = 0.0f;

    // Track D-pad state changes
    int last_hat_x = 0;
    int last_hat_y = 0;

    while (config.running.load()) {
        // Handle forced controller refresh/reconnect request
        if (config.force_refresh.load()) {
            if (gamepad_fd >= 0) {
                close(gamepad_fd);
                gamepad_fd = -1;
            }
            config.set_controller("None", "None");
            config.force_refresh.store(false);
        }

        // Double-check if parent process has become orphaned
        if (getppid() == 1) {
            std::cout << "[Linux Daemon] Parent process exited. Terminating cleanly..." << std::endl;
            break;
        }

        // Try to connect to gamepad if not connected
        if (gamepad_fd < 0) {
            dev_path = FindGamepadDevice(config.verbose.load());
            if (!dev_path.empty()) {
                gamepad_fd = open(dev_path.c_str(), O_RDONLY | O_NONBLOCK);
                if (gamepad_fd >= 0) {
                    char name[256] = "Unknown Gamepad";
                    ioctl(gamepad_fd, EVIOCGNAME(sizeof(name)), name);
                    std::string name_str(name);
                    
                    std::string type_str = "Xbox"; // Default to Xbox style (most common layout)
                    std::string lower_name = name_str;
                    for (char &c : lower_name) c = std::tolower(c);
                    
                    if (lower_name.find("playstation") != std::string::npos || 
                        lower_name.find("sony") != std::string::npos || 
                        lower_name.find("dualshock") != std::string::npos || 
                        lower_name.find("dualsense") != std::string::npos || 
                        lower_name.find("ps4") != std::string::npos || 
                        lower_name.find("ps5") != std::string::npos) {
                        type_str = "PlayStation";
                    } else if (lower_name.find("nintendo") != std::string::npos || 
                               lower_name.find("switch") != std::string::npos) {
                        type_str = "Nintendo";
                    }
                    
                    config.set_controller(name_str, type_str);
                    
                    std::cout << "[Linux Daemon] Opened gamepad: " << name_str << " (" << type_str << ") at " << dev_path << std::endl;

                    if (ioctl(gamepad_fd, EVIOCGABS(ABS_X), &abs_x_info) < 0 ||
                        ioctl(gamepad_fd, EVIOCGABS(ABS_Y), &abs_y_info) < 0) {
                        std::cerr << "[Linux Daemon] Warning: Failed to query axis ranges. Defaulting to 16-bit limits." << std::endl;
                        abs_x_info.minimum = -32768; abs_x_info.maximum = 32767;
                        abs_y_info.minimum = -32768; abs_y_info.maximum = 32767;
                    }
                }
            }

            if (gamepad_fd < 0) {
                // Sleep for 1 second before trying to find gamepad again
                struct timeval tv;
                tv.tv_sec = 1;
                tv.tv_usec = 0;
                select(0, nullptr, nullptr, nullptr, &tv);
                continue;
            }
        }

        // Setup poll
        struct pollfd fds[1];
        fds[0].fd = gamepad_fd;
        fds[0].events = POLLIN;

        int32_t raw_x = abs_x_info.value;
        int32_t raw_y = abs_y_info.value;
        int timeout_ms = -1; // Start in blocking mode

        // Inner poll loop for reading gamepad input
        while (config.running.load() && gamepad_fd >= 0) {
            if (getppid() == 1) {
                break;
            }

            // Poll with a 1 second timeout when joystick is at rest
            int current_timeout = (timeout_ms == -1) ? 1000 : timeout_ms;

            int poll_result = poll(fds, 1, current_timeout);
            if (poll_result < 0) {
                if (errno == EINTR) continue;
                std::cerr << "[Linux Daemon] poll() error: " << std::strerror(errno) << std::endl;
                break;
            }

            // Check for disconnect or error
            if (poll_result > 0 && (fds[0].revents & (POLLHUP | POLLERR | POLLNVAL))) {
                std::cout << "[Linux Daemon] Gamepad disconnected." << std::endl;
                close(gamepad_fd);
                gamepad_fd = -1;
                config.set_controller("None", "None");
                break;
            }

            if (poll_result > 0 && (fds[0].revents & POLLIN)) {
                struct input_event evs[64];
                ssize_t bytes_read = read(gamepad_fd, evs, sizeof(evs));
                if (bytes_read > 0) {
                    int event_count = bytes_read / sizeof(struct input_event);
                    for (int i = 0; i < event_count; ++i) {
                        if (evs[i].type == EV_ABS) {
                            if (evs[i].code == ABS_X) {
                                raw_x = evs[i].value;
                            } else if (evs[i].code == ABS_Y) {
                                raw_y = evs[i].value;
                            } else if (evs[i].code == ABS_HAT0X) {
                                int current_hat_x = evs[i].value;
                                if (current_hat_x != last_hat_x) {
                                    if (config.enabled.load()) {
                                        std::vector<MacroAction> actions;
                                        std::vector<MacroAction> dummy;
                                        // Release last direction
                                        if (last_hat_x == -1) { config.get_button_mapping(14, dummy, actions); ExecuteActions(uinput_fd, actions); }
                                        if (last_hat_x == 1)  { config.get_button_mapping(15, dummy, actions); ExecuteActions(uinput_fd, actions); }
                                        // Press new direction
                                        if (current_hat_x == -1) { config.get_button_mapping(14, actions, dummy); ExecuteActions(uinput_fd, actions); }
                                        if (current_hat_x == 1)  { config.get_button_mapping(15, actions, dummy); ExecuteActions(uinput_fd, actions); }
                                    }
                                    last_hat_x = current_hat_x;
                                }
                            } else if (evs[i].code == ABS_HAT0Y) {
                                int current_hat_y = evs[i].value;
                                if (current_hat_y != last_hat_y) {
                                    if (config.enabled.load()) {
                                        std::vector<MacroAction> actions;
                                        std::vector<MacroAction> dummy;
                                        // Release last direction
                                        if (last_hat_y == -1) { config.get_button_mapping(12, dummy, actions); ExecuteActions(uinput_fd, actions); }
                                        if (last_hat_y == 1)  { config.get_button_mapping(13, dummy, actions); ExecuteActions(uinput_fd, actions); }
                                        // Press new direction
                                        if (current_hat_y == -1) { config.get_button_mapping(12, actions, dummy); ExecuteActions(uinput_fd, actions); }
                                        if (current_hat_y == 1)  { config.get_button_mapping(13, actions, dummy); ExecuteActions(uinput_fd, actions); }
                                    }
                                    last_hat_y = current_hat_y;
                                }
                            }
                        } else if (evs[i].type == EV_KEY) {
                            int btn_idx = GetButtonIndexLinux(evs[i].code);
                            std::cout << "[Linux Daemon] Button Event: code=" << evs[i].code 
                                      << " (hex: 0x" << std::hex << evs[i].code << std::dec << "), value=" << evs[i].value 
                                      << ", btn_idx=" << btn_idx << std::endl;
                            if (btn_idx != -1 && config.enabled.load()) {
                                std::vector<MacroAction> actions;
                                std::vector<MacroAction> release_dummy;
                                if (evs[i].value == 1) { // Press
                                    config.get_button_mapping(btn_idx, actions, release_dummy);
                                } else if (evs[i].value == 0) { // Release
                                    config.get_button_mapping(btn_idx, release_dummy, actions);
                                }
                                if (evs[i].value == 1 || evs[i].value == 0) {
                                    if (config.verbose.load()) {
                                        std::cout << "[Linux Daemon] Executing " << actions.size() << " actions for btn_idx=" << btn_idx << std::endl;
                                    }
                                    ExecuteActions(uinput_fd, actions);
                                }
                            }
                        }
                    }
                } else if (bytes_read < 0 && errno != EAGAIN) {
                    std::cout << "[Linux Daemon] Gamepad read error. Re-connecting..." << std::endl;
                    close(gamepad_fd);
                    gamepad_fd = -1;
                    config.set_controller("None", "None");
                    break;
                }
            }

            float norm_x = NormalizeAxis(raw_x, abs_x_info);
            float norm_y = NormalizeAxis(raw_y, abs_y_info);

            if (config.enabled.load()) {
                float out_dx = 0.0f;
                float out_dy = 0.0f;
                MathUtils::ProcessJoystick(norm_x, norm_y, config.deadzone.load(), config.sensitivity.load(), config.curve_power.load(), out_dx, out_dy);

                if (config.invert_x.load()) out_dx = -out_dx;
                if (config.invert_y.load()) out_dy = -out_dy;

                accum_x += out_dx;
                accum_y += out_dy;

                int move_x = static_cast<int>(accum_x);
                int move_y = static_cast<int>(accum_y);

                accum_x -= move_x;
                accum_y -= move_y;

                if (move_x != 0 || move_y != 0) {
                    SendRelativeMove(uinput_fd, move_x, move_y);
                }
            } else {
                accum_x = 0.0f;
                accum_y = 0.0f;
            }

            float mag2 = norm_x * norm_x + norm_y * norm_y;
            float deadzone2 = config.deadzone.load() * config.deadzone.load();

            if (config.enabled.load() && mag2 >= deadzone2) {
                timeout_ms = config.poll_rate_ms.load();
            } else {
                timeout_ms = -1;
            }
        }
    }

    if (gamepad_fd >= 0) {
        close(gamepad_fd);
    }
    ioctl(uinput_fd, UI_DEV_DESTROY);
    close(uinput_fd);
    return 0;
}

#endif // __linux__

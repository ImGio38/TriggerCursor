#include "controller_daemon.h"
#include "http_server.h"
#include <iostream>
#include <string>
#include <cstdlib>
#include <thread>

void PrintUsage(const char* exec_name) {
    std::cout << "Usage: " << exec_name << " [options]" << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  --deadzone <val>     Joystick deadzone (0.0 to 1.0, default: 0.20)" << std::endl;
    std::cout << "  --sensitivity <val>  Cursor speed scaling factor (default: 15.0)" << std::endl;
    std::cout << "  --poll-rate <ms>     Polling rate in milliseconds (default: 4ms / 250Hz)" << std::endl;
    std::cout << "  --verbose            Print active state and buttons logging" << std::endl;
    std::cout << "  --help               Display this help message" << std::endl;
}

int main(int argc, char* argv[]) {
    SharedConfig config;

    // Command-line arguments parsing
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") {
            PrintUsage(argv[0]);
            return 0;
        } else if (arg == "--deadzone" && i + 1 < argc) {
            config.deadzone.store(std::strtof(argv[++i], nullptr));
        } else if (arg == "--sensitivity" && i + 1 < argc) {
            config.sensitivity.store(std::strtof(argv[++i], nullptr));
        } else if (arg == "--poll-rate" && i + 1 < argc) {
            config.poll_rate_ms.store(static_cast<int>(std::strtol(argv[++i], nullptr, 10)));
        } else if (arg == "--verbose") {
            config.verbose.store(true);
        } else {
            std::cerr << "Unknown option: " << arg << std::endl;
            PrintUsage(argv[0]);
            return 1;
        }
    }

    // Input validation
    if (config.deadzone.load() < 0.0f || config.deadzone.load() >= 1.0f) {
        std::cerr << "Error: Deadzone must be between 0.0 and 1.0" << std::endl;
        return 1;
    }
    if (config.sensitivity.load() <= 0.0f) {
        std::cerr << "Error: Sensitivity must be positive" << std::endl;
        return 1;
    }
    if (config.poll_rate_ms.load() < 1) {
        std::cerr << "Error: Polling rate must be at least 1ms" << std::endl;
        return 1;
    }

    std::cout << "==========================================================" << std::endl;
    std::cout << "   Near-Zero Overhead Controller-to-Mouse Daemon          " << std::endl;
    std::cout << "==========================================================" << std::endl;
    std::cout << "Configured Parameters:" << std::endl;
    std::cout << "  Deadzone:         " << config.deadzone.load() << std::endl;
    std::cout << "  Sensitivity:      " << config.sensitivity.load() << std::endl;
    std::cout << "  Polling interval: " << config.poll_rate_ms.load() << " ms" << std::endl;
    std::cout << "  Logging mode:     " << (config.verbose.load() ? "VERBOSE" : "STANDARD") << std::endl;
    std::cout << "  Local Dashboard:  http://localhost:8080" << std::endl;
    std::cout << "==========================================================" << std::endl;

    // Start local Web Server in background thread for Dashboard Control
    std::thread server_thread(RunHTTPServer, &config);

    int result = -1;
#ifdef __linux__
    result = RunLinuxDaemon(config);
#elif defined(_WIN32)
    result = RunWindowsDaemon(config);
#else
    std::cerr << "Unsupported operating system." << std::endl;
#endif

    // Shut down background thread cleanly
    config.running.store(false);
    if (server_thread.joinable()) {
        server_thread.join();
    }

    return result;
}

#ifndef HTTP_SERVER_H
#define HTTP_SERVER_H

#include "controller_daemon.h"

#include <string>
#include <iostream>
#include <cstdlib>
#include <cstring>
#include <sstream>
#include <vector>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET socket_t;
#define close_socket(s) closesocket(s)
#define invalid_socket(s) ((s) == INVALID_SOCKET)
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <sys/select.h>
typedef int socket_t;
#define close_socket(s) close(s)
#define invalid_socket(s) ((s) < 0)
#endif

inline std::vector<MacroAction> ParseMappingString(const std::string& str) {
    std::vector<MacroAction> actions;
    if (str.empty() || str == "none") return actions;
    
    std::stringstream ss(str);
    std::string item;
    while (std::getline(ss, item, ',')) {
        size_t colon = item.find(':');
        if (colon != std::string::npos) {
            int type_val = std::strtol(item.substr(0, colon).c_str(), nullptr, 10);
            int value_val = std::strtol(item.substr(colon + 1).c_str(), nullptr, 10);
            actions.push_back({static_cast<ActionType>(type_val), value_val});
        }
    }
    return actions;
}

inline void RunHTTPServer(SharedConfig* config) {
#ifdef _WIN32
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        std::cerr << "[HTTP Server] WSAStartup failed" << std::endl;
        return;
    }
#endif

    socket_t server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (invalid_socket(server_fd)) {
        std::cerr << "[HTTP Server] Socket creation failed" << std::endl;
        return;
    }

    int opt = 1;
#ifdef _WIN32
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));
#else
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
#endif

    struct sockaddr_in address;
    std::memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = inet_addr("127.0.0.1"); // Secure: Bind to localhost only
    address.sin_port = htons(8080);

    if (bind(server_fd, (struct sockaddr*)&address, sizeof(address)) < 0) {
        std::cerr << "[HTTP Server] Bind failed to port 8080 (Port already in use?)" << std::endl;
        close_socket(server_fd);
        return;
    }

    if (listen(server_fd, 5) < 0) {
        std::cerr << "[HTTP Server] Listen failed" << std::endl;
        close_socket(server_fd);
        return;
    }

    if (config->verbose) {
        std::cout << "[HTTP Server] Listening on http://localhost:8080" << std::endl;
    }

    while (config->running.load()) {
        struct timeval tv;
        tv.tv_sec = 1; // 1s timeout to check running flag periodically
        tv.tv_usec = 0;

        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(server_fd, &readfds);

        int activity = select(static_cast<int>(server_fd + 1), &readfds, nullptr, nullptr, &tv);
        if (activity < 0) break;
        if (activity == 0) continue; // Timeout, loop again

        struct sockaddr_in client_addr;
        socklen_t addr_len = sizeof(client_addr);
        socket_t client_fd = accept(server_fd, (struct sockaddr*)&client_addr, &addr_len);
        if (invalid_socket(client_fd)) continue;

        char buffer[4096] = {0};
        int bytes_read = recv(client_fd, buffer, sizeof(buffer) - 1, 0);
        if (bytes_read > 0) {
            std::string req(buffer);

            if (req.find("GET /status") != std::string::npos) {
                std::string c_name, c_type;
                config->get_controller(c_name, c_type);
                
                std::string mappings_json = "[";
                for (int i = 0; i < 16; ++i) {
                    mappings_json += "{" + config->serialize_mappings(i) + "}";
                    if (i + 1 < 16) mappings_json += ",";
                }
                mappings_json += "]";

                std::string body = "{\"deadzone\":" + std::to_string(config->deadzone.load()) +
                                   ",\"sensitivity\":" + std::to_string(config->sensitivity.load()) +
                                   ",\"enabled\":" + (config->enabled.load() ? "true" : "false") +
                                   ",\"verbose\":" + (config->verbose.load() ? "true" : "false") +
                                   ",\"curve_power\":" + std::to_string(config->curve_power.load()) +
                                   ",\"key_a\":" + std::to_string(config->key_a.load()) +
                                   ",\"key_b\":" + std::to_string(config->key_b.load()) +
                                   ",\"key_x\":" + std::to_string(config->key_x.load()) +
                                   ",\"key_y\":" + std::to_string(config->key_y.load()) +
                                   ",\"invert_x\":" + (config->invert_x.load() ? "true" : "false") +
                                   ",\"invert_y\":" + (config->invert_y.load() ? "true" : "false") +
                                   ",\"controller_name\":\"" + c_name + "\"" +
                                   ",\"controller_type\":\"" + c_type + "\"" +
                                   ",\"mappings\":" + mappings_json + "}";
                
                std::string resp = "HTTP/1.1 200 OK\r\n"
                                   "Content-Type: application/json\r\n"
                                   "Access-Control-Allow-Origin: *\r\n"
                                   "Content-Length: " + std::to_string(body.length()) + "\r\n"
                                   "Connection: close\r\n\r\n" + body;
                send(client_fd, resp.c_str(), static_cast<int>(resp.length()), 0);
            }
            else if (req.find("GET /toggle") != std::string::npos) {
                bool new_state = !config->enabled.load();
                config->enabled.store(new_state);
                
                std::string body = "{\"enabled\":" + std::string(new_state ? "true" : "false") + "}";
                std::string resp = "HTTP/1.1 200 OK\r\n"
                                   "Content-Type: application/json\r\n"
                                   "Access-Control-Allow-Origin: *\r\n"
                                   "Content-Length: " + std::to_string(body.length()) + "\r\n"
                                   "Connection: close\r\n\r\n" + body;
                send(client_fd, resp.c_str(), static_cast<int>(resp.length()), 0);
            }
            else if (req.find("GET /refresh") != std::string::npos) {
                config->force_refresh.store(true);
                
                std::string body = "{\"status\":\"ok\"}";
                std::string resp = "HTTP/1.1 200 OK\r\n"
                                   "Content-Type: application/json\r\n"
                                   "Access-Control-Allow-Origin: *\r\n"
                                   "Content-Length: " + std::to_string(body.length()) + "\r\n"
                                   "Connection: close\r\n\r\n" + body;
                send(client_fd, resp.c_str(), static_cast<int>(resp.length()), 0);
            }
            else if (req.find("GET /set_mapping?") != std::string::npos) {
                int btn_idx = -1;
                size_t pos_btn = req.find("btn=");
                if (pos_btn != std::string::npos) {
                    btn_idx = std::strtol(req.substr(pos_btn + 4).c_str(), nullptr, 10);
                }
                
                std::vector<MacroAction> press_actions;
                size_t pos_press = req.find("press=");
                if (pos_press != std::string::npos) {
                    std::string val_str = req.substr(pos_press + 6);
                    size_t pos_amp = val_str.find('&');
                    size_t pos_space = val_str.find(' ');
                    size_t end_pos = (pos_amp < pos_space) ? pos_amp : pos_space;
                    if (end_pos != std::string::npos) {
                        val_str = val_str.substr(0, end_pos);
                    }
                    press_actions = ParseMappingString(val_str);
                }
                
                std::vector<MacroAction> release_actions;
                size_t pos_release = req.find("release=");
                if (pos_release != std::string::npos) {
                    std::string val_str = req.substr(pos_release + 8);
                    size_t pos_amp = val_str.find('&');
                    size_t pos_space = val_str.find(' ');
                    size_t end_pos = (pos_amp < pos_space) ? pos_amp : pos_space;
                    if (end_pos != std::string::npos) {
                        val_str = val_str.substr(0, end_pos);
                    }
                    release_actions = ParseMappingString(val_str);
                }
                
                if (btn_idx >= 0 && btn_idx < 16) {
                    config->set_button_mapping(btn_idx, press_actions, release_actions);
                }
                
                std::string body = "{\"status\":\"ok\"}";
                std::string resp = "HTTP/1.1 200 OK\r\n"
                                   "Content-Type: application/json\r\n"
                                   "Access-Control-Allow-Origin: *\r\n"
                                   "Content-Length: " + std::to_string(body.length()) + "\r\n"
                                   "Connection: close\r\n\r\n" + body;
                send(client_fd, resp.c_str(), static_cast<int>(resp.length()), 0);
            }
            else if (req.find("GET /set?") != std::string::npos) {
                size_t pos_dz = req.find("deadzone=");
                if (pos_dz != std::string::npos) {
                    float dz = std::strtof(req.substr(pos_dz + 9).c_str(), nullptr);
                    config->deadzone.store(dz);
                }
                size_t pos_sens = req.find("sensitivity=");
                if (pos_sens != std::string::npos) {
                    float sens = std::strtof(req.substr(pos_sens + 12).c_str(), nullptr);
                    config->sensitivity.store(sens);
                }
                size_t pos_verb = req.find("verbose=");
                if (pos_verb != std::string::npos) {
                    bool verb = req.substr(pos_verb + 8, 1) == "1" || req.substr(pos_verb + 8, 4) == "true";
                    config->verbose.store(verb);
                }
                size_t pos_curve = req.find("curve_power=");
                if (pos_curve != std::string::npos) {
                    float cp = std::strtof(req.substr(pos_curve + 12).c_str(), nullptr);
                    config->curve_power.store(cp);
                }
                size_t pos_ka = req.find("key_a=");
                if (pos_ka != std::string::npos) {
                    int ka = std::strtol(req.substr(pos_ka + 6).c_str(), nullptr, 10);
                    config->key_a.store(ka);
                }
                size_t pos_kb = req.find("key_b=");
                if (pos_kb != std::string::npos) {
                    int kb = std::strtol(req.substr(pos_kb + 6).c_str(), nullptr, 10);
                    config->key_b.store(kb);
                }
                size_t pos_kx = req.find("key_x=");
                if (pos_kx != std::string::npos) {
                    int kx = std::strtol(req.substr(pos_kx + 6).c_str(), nullptr, 10);
                    config->key_x.store(kx);
                }
                size_t pos_ky = req.find("key_y=");
                if (pos_ky != std::string::npos) {
                    int ky = std::strtol(req.substr(pos_ky + 6).c_str(), nullptr, 10);
                    config->key_y.store(ky);
                }
                size_t pos_invx = req.find("invert_x=");
                if (pos_invx != std::string::npos) {
                    bool invx = req.substr(pos_invx + 9, 1) == "1" || req.substr(pos_invx + 9, 4) == "true";
                    config->invert_x.store(invx);
                }
                size_t pos_invy = req.find("invert_y=");
                if (pos_invy != std::string::npos) {
                    bool invy = req.substr(pos_invy + 9, 1) == "1" || req.substr(pos_invy + 9, 4) == "true";
                    config->invert_y.store(invy);
                }
                
                std::string body = "{\"status\":\"ok\"}";
                std::string resp = "HTTP/1.1 200 OK\r\n"
                                   "Content-Type: application/json\r\n"
                                   "Access-Control-Allow-Origin: *\r\n"
                                   "Content-Length: " + std::to_string(body.length()) + "\r\n"
                                   "Connection: close\r\n\r\n" + body;
                send(client_fd, resp.c_str(), static_cast<int>(resp.length()), 0);
            }
            else if (req.find("GET / ") != std::string::npos) {
                std::string body = "{\"status\":\"running\"}";
                std::string resp = "HTTP/1.1 200 OK\r\n"
                                   "Content-Type: application/json\r\n"
                                   "Content-Length: " + std::to_string(body.length()) + "\r\n"
                                   "Connection: close\r\n\r\n" + body;
                send(client_fd, resp.c_str(), static_cast<int>(resp.length()), 0);
            }
            else {
                std::string body = "Not Found";
                std::string resp = "HTTP/1.1 404 Not Found\r\n"
                                   "Content-Length: " + std::to_string(body.length()) + "\r\n"
                                   "Connection: close\r\n\r\n" + body;
                send(client_fd, resp.c_str(), static_cast<int>(resp.length()), 0);
            }
        }
        close_socket(client_fd);
    }

    close_socket(server_fd);
#ifdef _WIN32
    WSACleanup();
#endif
}

#endif // HTTP_SERVER_H

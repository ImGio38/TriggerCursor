cmake_minimum_required(VERSION 3.12)
project(TriggerCursorDaemon CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Optimization flags for near-zero overhead execution
if(MSVC)
    add_compile_options(/O2 /Oi /Ot /EHsc)
else()
    add_compile_options(-O3 -march=native -ffast-math)
endif()

add_executable(trigger_cursor_daemon
    src/main.cpp
    src/controller_daemon.h
    src/math_utils.h
)

if(UNIX AND NOT APPLE)
    # Linux compilation path
    target_sources(trigger_cursor_daemon PRIVATE src/linux_impl.cpp)
    target_link_libraries(trigger_cursor_daemon PRIVATE pthread)
elseif(WIN32)
    # Windows compilation path
    target_sources(trigger_cursor_daemon PRIVATE src/windows_impl.cpp)
    # Link winmm.lib for timeBeginPeriod/timeEndPeriod fallback support
    target_link_libraries(trigger_cursor_daemon PRIVATE winmm)
endif()

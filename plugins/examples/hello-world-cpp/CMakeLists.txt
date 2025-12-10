# CMakeLists.txt for Hello World G-Assist Plugin (C++)
cmake_minimum_required(VERSION 3.15)
project(hello-world-cpp VERSION 1.0.0 LANGUAGES CXX)

# Require C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Output name
set(PLUGIN_NAME "g-assist-plugin-hello-world-cpp")

# SDK path (relative to this CMakeLists.txt)
set(SDK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../sdk/cpp")

# Find or fetch nlohmann/json
include(FetchContent)
FetchContent_Declare(
    json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
)
FetchContent_MakeAvailable(json)

# Create executable
add_executable(${PLUGIN_NAME} plugin.cpp)

# Include directories
target_include_directories(${PLUGIN_NAME} PRIVATE
    ${SDK_DIR}
)

# Link nlohmann_json
target_link_libraries(${PLUGIN_NAME} PRIVATE nlohmann_json::nlohmann_json)

# Windows-specific settings
if(WIN32)
    # Static linking for easier deployment
    set_target_properties(${PLUGIN_NAME} PROPERTIES
        MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
    )
endif()

# Copy manifest.json to output directory
add_custom_command(TARGET ${PLUGIN_NAME} POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${CMAKE_CURRENT_SOURCE_DIR}/manifest.json"
        "$<TARGET_FILE_DIR:${PLUGIN_NAME}>/manifest.json"
    COMMENT "Copying manifest.json to output directory"
)

# Install target
install(TARGETS ${PLUGIN_NAME} RUNTIME DESTINATION .)
install(FILES manifest.json DESTINATION .)


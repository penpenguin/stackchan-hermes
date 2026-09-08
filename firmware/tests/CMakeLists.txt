cmake_minimum_required(VERSION 3.16)

project(stackchan_firmware_tests LANGUAGES CXX)

enable_testing()

# Compile the exact patched Wi-Fi board sources with deterministic network/timer fakes.
set(WIFI_BOARD_TEST_DIR "${CMAKE_CURRENT_BINARY_DIR}/wifi-board")
file(MAKE_DIRECTORY "${WIFI_BOARD_TEST_DIR}" "${WIFI_BOARD_TEST_DIR}/freertos" "${WIFI_BOARD_TEST_DIR}/assets")
foreach(source wifi_board.cc wifi_board.h)
    configure_file("../xiaozhi-esp32/main/boards/common/${source}" "${WIFI_BOARD_TEST_DIR}/${source}" COPYONLY)
endforeach()
foreach(header board.h display.h audio_codec.h system_info.h settings.h assets/lang_config.h
        freertos/FreeRTOS.h freertos/task.h freertos/event_groups.h esp_timer.h esp_network.h
        esp_log.h font_awesome.h wifi_manager.h wifi_station.h ssid_manager.h)
    file(WRITE "${WIFI_BOARD_TEST_DIR}/${header}" "#include \"wifi_board_fakes.h\"\n")
endforeach()
add_executable(wifi_setup_lifecycle_test wifi_setup_lifecycle_test.cpp "${WIFI_BOARD_TEST_DIR}/wifi_board.cc")
target_include_directories(wifi_setup_lifecycle_test PRIVATE "${WIFI_BOARD_TEST_DIR}" fakes/wifi_board)
target_compile_features(wifi_setup_lifecycle_test PRIVATE cxx_std_17)
add_test(NAME wifi_setup_lifecycle_test COMMAND wifi_setup_lifecycle_test)

add_executable(espnow_wifi_test espnow_wifi_test.cpp)
target_include_directories(espnow_wifi_test PRIVATE fakes/espnow_wifi ../main)
target_compile_features(espnow_wifi_test PRIVATE cxx_std_17)
add_test(NAME espnow_wifi_test COMMAND espnow_wifi_test)

add_executable(local_control_activity_test
    local_control_activity_test.cpp
    ../main/stackchan/json/json_helper.cpp
)
target_include_directories(local_control_activity_test PRIVATE
    fakes/local_control ../main ../components/ArduinoJson/src
)
target_compile_features(local_control_activity_test PRIVATE cxx_std_17)
add_test(NAME local_control_activity_test COMMAND local_control_activity_test)

add_executable(local_device_policy_test local_device_policy_test.cpp)
target_include_directories(local_device_policy_test PRIVATE ../main)
target_compile_features(local_device_policy_test PRIVATE cxx_std_17)
add_test(NAME local_device_policy_test COMMAND local_device_policy_test)



add_executable(motion_math_test
    motion_math_test.cpp
    ../main/stackchan/motion/motion_math.cpp
)

target_include_directories(motion_math_test PRIVATE
    ../main
)

target_compile_features(motion_math_test PRIVATE cxx_std_17)

add_test(NAME motion_math_test COMMAND $<TARGET_FILE:motion_math_test>)

add_executable(motion_safety_test
    motion_safety_test.cpp
)

target_include_directories(motion_safety_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(motion_safety_test PRIVATE cxx_std_17)

add_test(NAME motion_safety_test COMMAND $<TARGET_FILE:motion_safety_test>)

add_executable(motion_command_safety_test
    motion_command_safety_test.cpp
)

target_include_directories(motion_command_safety_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(motion_command_safety_test PRIVATE cxx_std_17)

add_test(NAME motion_command_safety_test COMMAND $<TARGET_FILE:motion_command_safety_test>)

add_executable(servo_output_safety_test
    servo_output_safety_test.cpp
)

target_include_directories(servo_output_safety_test PRIVATE
    ../main
)

target_compile_features(servo_output_safety_test PRIVATE cxx_std_17)

add_test(NAME servo_output_safety_test COMMAND $<TARGET_FILE:servo_output_safety_test>)

add_executable(head_touch_debouncer_test
    head_touch_debouncer_test.cpp
)

target_include_directories(head_touch_debouncer_test PRIVATE
    ../main/hal
)

target_compile_features(head_touch_debouncer_test PRIVATE cxx_std_17)

add_test(NAME head_touch_debouncer_test COMMAND $<TARGET_FILE:head_touch_debouncer_test>)

add_executable(websocket_frame_limits_test
    websocket_frame_limits_test.cpp
)

target_include_directories(websocket_frame_limits_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(websocket_frame_limits_test PRIVATE cxx_std_17)

add_test(
    NAME websocket_frame_limits_test
    COMMAND $<TARGET_FILE:websocket_frame_limits_test>
)

add_executable(websocket_handshake_test
    websocket_handshake_test.cpp
    ../components/stackchan_bridge_client/websocket_handshake.cpp
)

target_include_directories(websocket_handshake_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(websocket_handshake_test PRIVATE cxx_std_17)

add_test(
    NAME websocket_handshake_test
    COMMAND $<TARGET_FILE:websocket_handshake_test>
)

find_package(Threads REQUIRED)

add_executable(camera_upload_redirect_test
    camera_upload_redirect_test.cpp
    ../main/hal/stackchan_bridge_camera_upload.h
    ../managed_components/78__esp-ml307/src/http_client.cc
    ../components/stackchan_bridge_client/camera_capture.cpp
)
target_include_directories(camera_upload_redirect_test PRIVATE
    fakes/websocket_wire
    ../managed_components/78__esp-ml307/include
    ../components/stackchan_bridge_client/include
    ../components/ArduinoJson/src
    ../main/hal
)
target_compile_features(camera_upload_redirect_test PRIVATE cxx_std_17)
target_link_libraries(camera_upload_redirect_test PRIVATE Threads::Threads)
add_test(NAME camera_upload_redirect_test COMMAND camera_upload_redirect_test)

add_executable(websocket_random_test
    websocket_random_test.cpp
    ../components/stackchan_bridge_client/web_socket.cpp
    ../components/stackchan_bridge_client/websocket_pong.cpp
)
target_include_directories(websocket_random_test PRIVATE
    fakes/websocket_wire
    ../managed_components/78__esp-ml307/include
    ../components/stackchan_bridge_client/include
)
target_compile_features(websocket_random_test PRIVATE cxx_std_17)
target_link_libraries(websocket_random_test PRIVATE Threads::Threads)
add_test(NAME websocket_random_test COMMAND $<TARGET_FILE:websocket_random_test>)

add_executable(official_websocket_transport_test
    official_websocket_transport_test.cpp
    ../main/hal/stackchan_bridge_websocket.cpp
    ../components/stackchan_bridge_client/websocket_pong.cpp
)

target_include_directories(official_websocket_transport_test PRIVATE
    fakes
    ../main/hal
    ../components/stackchan_bridge_client/include
)

target_compile_features(official_websocket_transport_test PRIVATE cxx_std_17)
target_link_libraries(official_websocket_transport_test PRIVATE Threads::Threads)

add_test(
    NAME official_websocket_transport_test
    COMMAND $<TARGET_FILE:official_websocket_transport_test>
)

add_executable(bridge_client_protocol_test
    bridge_client_protocol_test.cpp
    ../components/stackchan_bridge_client/protocol.cpp
)

target_include_directories(bridge_client_protocol_test PRIVATE
    ../components/stackchan_bridge_client/include
    ../components/ArduinoJson/src
)

target_compile_features(bridge_client_protocol_test PRIVATE cxx_std_17)

add_test(NAME bridge_client_protocol_test COMMAND $<TARGET_FILE:bridge_client_protocol_test>)

add_executable(bridge_client_protocol_guard_test
    bridge_client_protocol_guard_test.cpp
    ../components/stackchan_bridge_client/protocol_guard.cpp
)

target_include_directories(bridge_client_protocol_guard_test PRIVATE
    ../components/stackchan_bridge_client/include
    ../components/ArduinoJson/src
)

target_compile_features(bridge_client_protocol_guard_test PRIVATE cxx_std_17)

add_test(
    NAME bridge_client_protocol_guard_test
    COMMAND $<TARGET_FILE:bridge_client_protocol_guard_test>
)

add_executable(bridge_client_state_test
    bridge_client_state_test.cpp
    ../components/stackchan_bridge_client/state_machine.cpp
)

target_include_directories(bridge_client_state_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(bridge_client_state_test PRIVATE cxx_std_17)

add_test(NAME bridge_client_state_test COMMAND $<TARGET_FILE:bridge_client_state_test>)

add_executable(bridge_client_reconnect_test
    bridge_client_reconnect_test.cpp
    ../components/stackchan_bridge_client/reconnect.cpp
)

target_include_directories(bridge_client_reconnect_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(bridge_client_reconnect_test PRIVATE cxx_std_17)

add_test(NAME bridge_client_reconnect_test COMMAND $<TARGET_FILE:bridge_client_reconnect_test>)

add_executable(bridge_client_settings_test
    bridge_client_settings_test.cpp
    ../components/stackchan_bridge_client/settings.cpp
)

target_include_directories(bridge_client_settings_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(bridge_client_settings_test PRIVATE cxx_std_17)

add_test(NAME bridge_client_settings_test COMMAND $<TARGET_FILE:bridge_client_settings_test>)

add_executable(bridge_client_discovery_test
    bridge_client_discovery_test.cpp
    ../components/stackchan_bridge_client/discovery.cpp
    ../components/stackchan_bridge_client/settings.cpp
)

target_include_directories(bridge_client_discovery_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(bridge_client_discovery_test PRIVATE cxx_std_17)

add_test(NAME bridge_client_discovery_test COMMAND $<TARGET_FILE:bridge_client_discovery_test>)

add_executable(bridge_client_provisioning_test
    bridge_client_provisioning_test.cpp
    ../components/stackchan_bridge_client/provisioning.cpp
    ../components/stackchan_bridge_client/settings.cpp
)

target_include_directories(bridge_client_provisioning_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(bridge_client_provisioning_test PRIVATE cxx_std_17)

add_test(NAME bridge_client_provisioning_test COMMAND $<TARGET_FILE:bridge_client_provisioning_test>)

add_executable(bridge_client_command_test
    bridge_client_command_test.cpp
    ../components/stackchan_bridge_client/command.cpp
)

target_include_directories(bridge_client_command_test PRIVATE
    ../components/stackchan_bridge_client/include
    ../components/ArduinoJson/src
)

target_compile_features(bridge_client_command_test PRIVATE cxx_std_17)

add_test(NAME bridge_client_command_test COMMAND $<TARGET_FILE:bridge_client_command_test>)

add_executable(bridge_client_command_executor_test
    bridge_client_command_executor_test.cpp
    ../components/stackchan_bridge_client/command_executor.cpp
)

target_include_directories(bridge_client_command_executor_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(bridge_client_command_executor_test PRIVATE cxx_std_17)

add_test(
    NAME bridge_client_command_executor_test
    COMMAND $<TARGET_FILE:bridge_client_command_executor_test>
)

add_executable(bridge_client_audio_output_test
    bridge_client_audio_output_test.cpp
    ../components/stackchan_bridge_client/audio_output.cpp
)

target_include_directories(bridge_client_audio_output_test PRIVATE
    ../components/stackchan_bridge_client/include
    ../components/ArduinoJson/src
)

target_compile_features(bridge_client_audio_output_test PRIVATE cxx_std_17)

add_test(
    NAME bridge_client_audio_output_test
    COMMAND $<TARGET_FILE:bridge_client_audio_output_test>
)

add_executable(audio_playback_completion_test
    audio_playback_completion_test.cpp
)

target_include_directories(audio_playback_completion_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(audio_playback_completion_test PRIVATE cxx_std_17)

add_test(
    NAME audio_playback_completion_test
    COMMAND $<TARGET_FILE:audio_playback_completion_test>
)

add_executable(bridge_client_audio_input_test
    bridge_client_audio_input_test.cpp
    ../components/stackchan_bridge_client/audio_input.cpp
)

target_include_directories(bridge_client_audio_input_test PRIVATE
    ../components/stackchan_bridge_client/include
    ../components/ArduinoJson/src
)

target_compile_features(bridge_client_audio_input_test PRIVATE cxx_std_17)

add_test(
    NAME bridge_client_audio_input_test
    COMMAND $<TARGET_FILE:bridge_client_audio_input_test>
)

add_executable(bridge_client_audio_safety_test
    bridge_client_audio_safety_test.cpp
    ../components/stackchan_bridge_client/audio_safety.cpp
)

target_include_directories(bridge_client_audio_safety_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(bridge_client_audio_safety_test PRIVATE cxx_std_17)

add_test(
    NAME bridge_client_audio_safety_test
    COMMAND $<TARGET_FILE:bridge_client_audio_safety_test>
)

add_executable(bridge_client_event_test
    bridge_client_event_test.cpp
    ../components/stackchan_bridge_client/event.cpp
)

target_include_directories(bridge_client_event_test PRIVATE
    ../components/stackchan_bridge_client/include
    ../components/ArduinoJson/src
)

target_compile_features(bridge_client_event_test PRIVATE cxx_std_17)

add_test(NAME bridge_client_event_test COMMAND $<TARGET_FILE:bridge_client_event_test>)

add_executable(bridge_client_message_id_test
    bridge_client_message_id_test.cpp
    ../components/stackchan_bridge_client/message_id.cpp
)

target_include_directories(bridge_client_message_id_test PRIVATE
    ../components/stackchan_bridge_client/include
)

target_compile_features(bridge_client_message_id_test PRIVATE cxx_std_17)

add_test(
    NAME bridge_client_message_id_test
    COMMAND $<TARGET_FILE:bridge_client_message_id_test>
)

add_executable(bridge_client_camera_capture_test
    bridge_client_camera_capture_test.cpp
    ../components/stackchan_bridge_client/camera_capture.cpp
)

target_include_directories(bridge_client_camera_capture_test PRIVATE
    ../components/stackchan_bridge_client/include
    ../components/ArduinoJson/src
)

target_compile_features(bridge_client_camera_capture_test PRIVATE cxx_std_17)

add_test(
    NAME bridge_client_camera_capture_test
    COMMAND $<TARGET_FILE:bridge_client_camera_capture_test>
)

add_executable(bridge_client_session_test
    bridge_client_session_test.cpp
    ../components/stackchan_bridge_client/audio_input.cpp
    ../components/stackchan_bridge_client/audio_output.cpp
    ../components/stackchan_bridge_client/camera_capture.cpp
    ../components/stackchan_bridge_client/command.cpp
    ../components/stackchan_bridge_client/event.cpp
    ../components/stackchan_bridge_client/session.cpp
    ../components/stackchan_bridge_client/protocol.cpp
    ../components/stackchan_bridge_client/protocol_guard.cpp
    ../components/stackchan_bridge_client/reconnect.cpp
    ../components/stackchan_bridge_client/settings.cpp
    ../components/stackchan_bridge_client/state_machine.cpp
)

target_include_directories(bridge_client_session_test PRIVATE
    ../components/stackchan_bridge_client/include
    ../components/ArduinoJson/src
)

target_compile_features(bridge_client_session_test PRIVATE cxx_std_17)

add_test(NAME bridge_client_session_test COMMAND $<TARGET_FILE:bridge_client_session_test>)

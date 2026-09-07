idf_component_register(
    SRCS
        "audio_input.cpp"
        "audio_output.cpp"
        "audio_safety.cpp"
        "camera_capture.cpp"
        "command.cpp"
        "command_executor.cpp"
        "discovery.cpp"
        "event.cpp"
        "message_id.cpp"
        "provisioning.cpp"
        "protocol.cpp"
        "protocol_guard.cpp"
        "reconnect.cpp"
        "session.cpp"
        "settings.cpp"
        "state_machine.cpp"
    INCLUDE_DIRS "include"
    REQUIRES ArduinoJson
)

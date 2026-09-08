from __future__ import annotations

import json
import re
import subprocess
from hashlib import sha256
from pathlib import Path

from stackchan_bridge.protocol.models import MAX_AUDIO_PACKET_BYTES, MAX_JSON_BYTES

ROOT = Path(__file__).resolve().parents[2]
FIRMWARE_ROOT = ROOT / "firmware"


def test_espnow_reuses_managed_wifi_instead_of_creating_a_second_event_loop() -> None:
    espnow = (FIRMWARE_ROOT / "main/hal/hal_espnow.cpp").read_text()
    board = (FIRMWARE_ROOT / "main/hal/board/stackchan.cc").read_text()
    assert "esp_event_loop_create_default" not in espnow
    assert "esp_netif_create_default_wifi_sta" not in espnow
    assert "board_prepare_espnow(channel)" in espnow
    assert "prepareEspNowWifi(channel, connect_timer_)" in board


def test_espnow_app_uses_the_addressed_control_handler_with_local_activity() -> None:
    app = (FIRMWARE_ROOT / "main/apps/app_espnow_ctrl/app_espnow_ctrl.cpp").read_text()
    assert "applyEspNowControlPacket(_received_data, _receiver_id," in app


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_pinned_official_firmware_baseline_is_present_with_reviewed_defaults() -> None:
    cmake = (FIRMWARE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    license_text = (FIRMWARE_ROOT / "LICENSE").read_text(encoding="utf-8")
    defaults = (FIRMWARE_ROOT / "sdkconfig.defaults").read_text(encoding="utf-8")
    partitions = (FIRMWARE_ROOT / "partitions.csv").read_text(encoding="utf-8")
    repositories = json.loads((FIRMWARE_ROOT / "repos.json").read_text(encoding="utf-8"))

    assert 'set(PROJECT_VER "1.5.1")' in cmake
    assert license_text.startswith("MIT License\n")
    assert "Copyright (c) 2026 M5Stack Technology CO LTD" in license_text
    assert 'CONFIG_IDF_TARGET="esp32s3"' in defaults
    assert "CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y" in defaults
    assert "CONFIG_BOARD_TYPE_M5STACK_STACK_CHAN=y" in defaults
    assert "ota_0" in partitions
    assert "ota_1" in partitions
    assert "assets" in partitions
    assert len(repositories) == 6


def test_vendor_snapshot_records_immutable_upstream_and_dependency_provenance() -> None:
    lock = json.loads((FIRMWARE_ROOT / "upstream-lock.json").read_text(encoding="utf-8"))

    assert lock["schema_version"] == 1
    assert lock["source"] == {
        "repository": "https://github.com/m5stack/StackChan.git",
        "commit": "1b5765599fba8aaad1811d9a79358ccc7051f5f3",
        "firmware_tree": "a981688092155fb4a84c530575e70c7f83ab42e6",
        "firmware_version": "1.5.1",
        "import_method": "vendor_snapshot",
        "license": "MIT",
    }
    assert lock["toolchain"] == {
        "esp_idf_version": "v5.5.4",
        "esp_idf_commit": "735507283d5b2f9fb363a1901172dbd9e847945d",
    }
    assert lock["critical_file_sha256"] == {
        "LICENSE": _file_sha256(FIRMWARE_ROOT / "LICENSE"),
        "dependencies.lock": _file_sha256(FIRMWARE_ROOT / "dependencies.lock"),
        "partitions.csv": _file_sha256(FIRMWARE_ROOT / "partitions.csv"),
        "patches/xiaozhi-esp32.patch": _file_sha256(
            FIRMWARE_ROOT / "patches" / "xiaozhi-esp32.patch"
        ),
        "repos.json": _file_sha256(FIRMWARE_ROOT / "repos.json"),
        "sdkconfig.defaults": _file_sha256(FIRMWARE_ROOT / "sdkconfig.defaults"),
    }
    assert {
        dependency["path"]: (dependency["ref"], dependency["commit"], dependency["license"])
        for dependency in lock["fetched_repositories"]
    } == {
        "components/ArduinoJson": (
            "v7.4.2",
            "733bc4ee82630c88c0a619a883cd3a206efae977",
            "MIT",
        ),
        "components/esp-now": (
            "c33383de97f3ed2fc52117f5ef04f71990432e5d",
            "c33383de97f3ed2fc52117f5ef04f71990432e5d",
            "Apache-2.0",
        ),
        "components/mooncake": (
            "v2.3.3",
            "572a7e488641f1c3f22e85d65c27f095ecf27d12",
            "MIT",
        ),
        "components/mooncake_log": (
            "v1.5.0",
            "554d55cd8c6e551b911b99cad274a46929f05bae",
            "MIT",
        ),
        "components/smooth_ui_toolkit": (
            "v2.12.0",
            "2a18ff5d3fd6b402339d0f4f3c2834f574e3cb05",
            "MIT",
        ),
        "xiaozhi-esp32": (
            "v2.2.4",
            "e77dedb1309153bb63fed285772962c920c97dd4",
            "MIT",
        ),
    }
    xiaozhi = next(
        dependency
        for dependency in lock["fetched_repositories"]
        if dependency["path"] == "xiaozhi-esp32"
    )
    assert xiaozhi["patch"] == "patches/xiaozhi-esp32.patch"
    assert xiaozhi["patched_diff_sha256"] == (
        "b4bf351e08dd5e63eab3e936cb955fc87ac6faefadb2e926bcdbc2015357116b"
    )


def test_firmware_ignore_rules_keep_fetched_dependencies_out_and_custom_component_in() -> None:
    def is_ignored(path: str) -> bool:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode in {0, 1}
        return result.returncode == 0

    assert is_ignored("firmware/components/mooncake/probe.cpp")
    assert is_ignored("firmware/xiaozhi-esp32/probe.cpp")
    assert is_ignored("firmware/managed_components/probe.cpp")
    assert is_ignored("firmware/build-host-tests/probe.txt")
    assert not is_ignored("firmware/components/stackchan_bridge_client/CMakeLists.txt")


def test_bridge_client_core_is_registered_as_an_esp_idf_component() -> None:
    cmake = (FIRMWARE_ROOT / "components" / "stackchan_bridge_client" / "CMakeLists.txt").read_text(
        encoding="utf-8"
    )

    assert "idf_component_register" in cmake
    for source in (
        "protocol.cpp",
        "reconnect.cpp",
        "session.cpp",
        "settings.cpp",
        "state_machine.cpp",
    ):
        assert f'"{source}"' in cmake
    assert 'INCLUDE_DIRS "include"' in cmake
    assert "REQUIRES ArduinoJson" in cmake


def test_main_uses_a_thin_official_websocket_adapter_for_bridge_transport() -> None:
    adapter = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_websocket.cpp").read_text(
        encoding="utf-8"
    )
    main_cmake = (FIRMWARE_ROOT / "main" / "CMakeLists.txt").read_text(encoding="utf-8")

    assert "stackchan_bridge_client" in main_cmake
    assert "network_.CreateWebSocket(1)" in adapter
    assert "socket_.reset()" in adapter
    for official_call in (
        "SetHeader",
        "SetReceiveBufferSize",
        "OnConnected",
        "OnDisconnected",
        "OnData",
        "OnError",
        "Connect",
        "Send",
        "Ping",
        "Close",
    ):
        assert f"->{official_call}(" in adapter


def test_websocket_override_validates_the_server_handshake_against_its_client_key() -> None:
    implementation = (
        FIRMWARE_ROOT / "components" / "stackchan_bridge_client" / "web_socket.cpp"
    ).read_text(encoding="utf-8")
    handshake = (
        FIRMWARE_ROOT / "components" / "stackchan_bridge_client" / "websocket_handshake.cpp"
    ).read_text(encoding="utf-8")
    main_cmake = (FIRMWARE_ROOT / "main" / "CMakeLists.txt").read_text(encoding="utf-8")

    assert "validateWebSocketHandshakeResponse(" in implementation
    assert "clientKey->second" in implementation
    assert 'find("HTTP/1.1 101")' not in implementation
    assert "258EAFA5-E914-47DA-95CA-C5AB0DC85B11" in handshake
    assert 'equalsIgnoreCase(name, "Upgrade")' in handshake
    assert 'equalsIgnoreCase(name, "Connection")' in handshake
    assert 'equalsIgnoreCase(name, "Sec-WebSocket-Accept")' in handshake
    assert "websocket_handshake.cpp" in main_cmake


def test_main_registers_a_default_enabled_nvs_backed_bridge_service() -> None:
    kconfig = (FIRMWARE_ROOT / "main" / "Kconfig.projbuild").read_text(encoding="utf-8")
    main = (FIRMWARE_ROOT / "main" / "main.cpp").read_text(encoding="utf-8")
    service = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_service.cpp").read_text(
        encoding="utf-8"
    )

    assert "config STACKCHAN_HERMES_BRIDGE_CLIENT" in kconfig
    assert "config STACKCHAN_HERMES_DEFAULT_BRIDGE_URL" in kconfig
    assert "config STACKCHAN_HERMES_MAX_RECORDING_MS" in kconfig
    assert "range 1000 15000" in kconfig
    assert "config STACKCHAN_HERMES_PLAYBACK_PREROLL_MS" in kconfig
    preroll_config = kconfig.split("config STACKCHAN_HERMES_PLAYBACK_PREROLL_MS", 1)[1].split(
        "endmenu", 1
    )[0]
    assert "range 0 1920" in preroll_config
    bridge_client_config = kconfig.split("config STACKCHAN_HERMES_BRIDGE_CLIENT", 1)[1].split(
        "config STACKCHAN_HERMES_DEFAULT_BRIDGE_URL", 1
    )[0]
    assert "default y" in bridge_client_config
    assert 'default ""' in kconfig
    assert "CONFIG_STACKCHAN_HERMES_BRIDGE_CLIENT" in main
    assert "startStackchanHermesBridgeClient()" in main
    assert 'Settings deviceSettings("device", false)' in service
    assert 'Settings bridgeSettings("bridge", false)' in service
    for key in ("id", "name", "url", "token"):
        assert f'GetString("{key}"' in service
    assert "resolveBridgeEndpoint" in service
    assert "config.hello.capabilities.head       = false" in service
    assert "config.audioInputMaxDurationMs" in service
    assert "config.audioOutputPrerollMs" in service
    assert "const std::uint32_t nowMs = GetHAL().millis()" in service
    assert "client_.update(nowMs)" in service
    assert "extensionManager()->createAbility" in service


def test_main_reports_the_physical_k151_model_instead_of_the_network_transport() -> None:
    identity = (
        FIRMWARE_ROOT
        / "components"
        / "stackchan_bridge_client"
        / "include"
        / "stackchan_bridge_client"
        / "hardware_identity.h"
    ).read_text(encoding="utf-8")
    service = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_service.cpp").read_text(
        encoding="utf-8"
    )
    command_target = (
        FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_command_target.cpp"
    ).read_text(encoding="utf-8")

    assert 'kStackChanHardwareModel[] = "M5STACK-K151"' in identity
    assert "config.hello.hardwareModel     = bridge_client::kStackChanHardwareModel" in service
    assert "info.hardwareModel = bridge_client::kStackChanHardwareModel" in command_target
    assert "board.GetBoardType()" not in service
    assert "board_.GetBoardType()" not in command_target


def test_physical_playback_completion_owns_speaking_until_audio_output_is_idle() -> None:
    audio_service_header = (
        FIRMWARE_ROOT / "xiaozhi-esp32" / "main" / "audio" / "audio_service.h"
    ).read_text(encoding="utf-8")
    audio_service = (
        FIRMWARE_ROOT / "xiaozhi-esp32" / "main" / "audio" / "audio_service.cc"
    ).read_text(encoding="utf-8")
    bridge_service = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_service.cpp").read_text(
        encoding="utf-8"
    )

    assert "stackchan_bridge_client/audio_playback_completion.h" in audio_service_header
    assert "AudioPlaybackCompletion playbackCompletion_" in audio_service_header
    output_task = audio_service.split("void AudioService::AudioOutputTask()", 1)[1].split(
        "void AudioService::OpusCodecTask()", 1
    )[0]
    assert output_task.index("playbackCompletion_.beginOutput()") < output_task.index(
        "codec_->OutputData"
    )
    assert output_task.index("codec_->OutputData") < output_task.index(
        "playbackCompletion_.finishOutput()"
    )
    idle_check = audio_service.split("bool AudioService::IsIdle()", 1)[1].split(
        "void AudioService::WaitForPlaybackQueueEmpty()", 1
    )[0]
    assert "playbackCompletion_.isIdle" in idle_check

    worker = bridge_service.split("void onRunning() override", 1)[1].split("private:", 1)[0]
    delivery = worker.split("client_.deliverAudioOutputPacket(", 1)[1].split(");", 1)[0]
    assert "audioService_.IsIdle()" in delivery
    assert "client_.audioOutputDeliveryComplete()" in worker
    assert "audioService_.IsIdle()" in worker
    assert "client_.acknowledgeAudioOutputPlayback()" in worker


def test_each_new_audio_output_stream_resets_the_decoder_before_playback() -> None:
    bridge_service = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_service.cpp").read_text(
        encoding="utf-8"
    )

    state_handler = bridge_service.split("config.stateChanged =", 1)[1].split(
        "config.envelopeFactory", 1
    )[0]
    assert "&audioService" in state_handler
    assert "state == bridge_client::DeviceState::Speaking" in state_handler
    assert "audioService.ResetDecoder();" in state_handler
    assert state_handler.index("audioService.ResetDecoder();") < state_handler.index(
        "commandTarget.applyBridgeState(state);"
    )


def test_decoder_cancellation_discards_in_flight_work_before_it_reaches_playback() -> None:
    audio_service = (
        FIRMWARE_ROOT / "xiaozhi-esp32" / "main" / "audio" / "audio_service.cc"
    ).read_text(encoding="utf-8")

    codec_task = audio_service.split("void AudioService::OpusCodecTask()", 1)[1].split(
        "void AudioService::SetDecodeSampleRate", 1
    )[0]
    assert "playbackCompletion_.beginDecode()" in codec_task
    assert "playbackCompletion_.finishDecode(decodeGeneration)" in codec_task
    assert codec_task.index(
        "playbackCompletion_.finishDecode(decodeGeneration)"
    ) < codec_task.index("audio_playback_queue_.push_back")

    reset_decoder = audio_service.split("void AudioService::ResetDecoder()", 1)[1].split(
        "void AudioService::SetPlaybackGainPercent", 1
    )[0]
    assert "playbackCompletion_.invalidateDecode();" in reset_decoder


def test_firmware_gate_builds_a_fresh_hermes_enabled_configuration() -> None:
    defaults_path = FIRMWARE_ROOT / "sdkconfig.hermes.defaults"
    gate = (ROOT / "scripts" / "verify-firmware.sh").read_text(encoding="utf-8")

    assert defaults_path.is_file()
    defaults = defaults_path.read_text(encoding="utf-8")
    for setting in (
        "CONFIG_STACKCHAN_HERMES_BRIDGE_CLIENT=y",
        "CONFIG_STACKCHAN_HERMES_USB_PROVISIONING=y",
        "CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y",
        "CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y",
        "CONFIG_STACKCHAN_HERMES_TTS_GAIN_PERCENT=65",
        "CONFIG_STACKCHAN_HERMES_MAX_RECORDING_MS=15000",
        "CONFIG_STACKCHAN_HERMES_PLAYBACK_PREROLL_MS=500",
    ):
        assert setting in defaults

    assert "mktemp -d" in gate
    assert "sdkconfig.hermes.defaults" in gate
    assert '-D SDKCONFIG="$firmware_verify_dir/sdkconfig"' in gate
    assert '-B "$firmware_verify_dir/build"' in gate
    assert 'firmware_image="$firmware_verify_dir/build/stack-chan.bin"' in gate
    assert 'wc -c < "$firmware_image"' in gate
    assert 'sha256sum "$firmware_image"' in gate
    assert "CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y" in gate
    assert "CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y" in gate


def test_hermes_head_motion_lock_guards_every_servo_output() -> None:
    kconfig = (FIRMWARE_ROOT / "main" / "Kconfig.projbuild").read_text(encoding="utf-8")
    driver = (FIRMWARE_ROOT / "main" / "hal" / "hal_servo.cpp").read_text(encoding="utf-8")

    motion_lock = kconfig.split("config STACKCHAN_HERMES_HEAD_MOTION_LOCK", 1)[1].split(
        "config STACKCHAN_HERMES_TTS_GAIN_PERCENT", 1
    )[0]
    assert "depends on STACKCHAN_HERMES_BRIDGE_CLIENT" in motion_lock
    assert "default y" in motion_lock
    assert "#if CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK" in driver
    assert driver.count("_scs_bus.WritePos(") == driver.count("_output_safety.writePosition(")
    assert driver.count("_scs_bus.WritePWM(") == driver.count("_output_safety.writeVelocity(")
    assert driver.count("_scs_bus.EnableTorque(") == driver.count("_output_safety.writeTorque(")


def test_k151_motion_profile_reaches_only_the_bounded_official_hal_path() -> None:
    target = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_command_target.cpp").read_text(
        encoding="utf-8"
    )
    service = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_service.cpp").read_text(
        encoding="utf-8"
    )
    driver = (FIRMWARE_ROOT / "main" / "hal" / "hal_servo.cpp").read_text(encoding="utf-8")

    set_angles = target.split("bool OfficialDeviceCommandTarget::setHeadAngles", 1)[1].split(
        "bool OfficialDeviceCommandTarget::homeHead", 1
    )[0]
    home = target.split("bool OfficialDeviceCommandTarget::homeHead", 1)[1].split(
        "bool OfficialDeviceCommandTarget::getHeadAngles", 1
    )[0]

    assert "CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK" in set_angles
    assert "K151MotionSafety::contains(yaw, pitch, speed)" in set_angles
    assert "motion.moveFromAuthenticatedBridgeWithSpeed" in set_angles
    assert "std::lround(yaw * 10.0)" in set_angles
    assert "std::lround(pitch * 10.0)" in set_angles
    assert "speed * 10" in set_angles
    assert "K151MotionSafety::kHomeYawDegrees" in home
    assert "K151MotionSafety::kHomePitchDegrees" in home
    assert "CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK" in service
    assert "config.hello.capabilities.head       = true;" in service
    assert "config.hello.capabilities.head       = false;" in service
    assert "Vector2i(-450, 450)" in driver
    assert "Vector2i(50, 850)" in driver
    assert "yaw_servo_config.enablePwmMode          = false" in driver
    servo = (FIRMWARE_ROOT / "main" / "stackchan" / "motion" / "servo.cpp").read_text(
        encoding="utf-8"
    )
    assert "K151MotionSafety::clampDriverSpeed(speed)" in servo


def test_unlocked_candidate_accepts_only_authenticated_bridge_motion() -> None:
    kconfig = (FIRMWARE_ROOT / "main" / "Kconfig.projbuild").read_text(encoding="utf-8")
    servo_header = (FIRMWARE_ROOT / "main" / "stackchan" / "motion" / "servo.h").read_text(
        encoding="utf-8"
    )
    servo = (FIRMWARE_ROOT / "main" / "stackchan" / "motion" / "servo.cpp").read_text(
        encoding="utf-8"
    )
    motion = (FIRMWARE_ROOT / "main" / "stackchan" / "motion" / "motion.cpp").read_text(
        encoding="utf-8"
    )
    driver = (FIRMWARE_ROOT / "main" / "hal" / "hal_servo.cpp").read_text(encoding="utf-8")
    target = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_command_target.cpp").read_text(
        encoding="utf-8"
    )

    local_lock = kconfig.split("config STACKCHAN_HERMES_LOCAL_MOTION_LOCK", 1)[1].split(
        "config STACKCHAN_HERMES_TTS_GAIN_PERCENT", 1
    )[0]
    assert "depends on STACKCHAN_HERMES_BRIDGE_CLIENT" in local_lock
    assert "depends on !STACKCHAN_HERMES_HEAD_MOTION_LOCK" in local_lock
    assert "default y" in local_lock
    assert "moveFromAuthenticatedBridgeWithSpeed" in servo_header
    assert "MotionCommandSource::Local" in servo
    assert "MotionCommandSource::AuthenticatedBridge" in servo
    assert "moveFromAuthenticatedBridgeWithSpeed" in motion
    assert "CONFIG_STACKCHAN_HERMES_LOCAL_MOTION_LOCK" in driver
    assert "motion->setLocalMotionLocked(true)" in driver
    assert "allowsMotionCommand(MotionCommandSource::Local)" in driver
    assert "allowsTorqueCommand(enabled, MotionCommandSource::Local)" in driver

    set_angles = target.split("bool OfficialDeviceCommandTarget::setHeadAngles", 1)[1].split(
        "bool OfficialDeviceCommandTarget::homeHead", 1
    )[0]
    assert "motion.moveFromAuthenticatedBridgeWithSpeed" in set_angles
    assert "motion.moveWithSpeed(" not in set_angles


def test_main_applies_persisted_volume_and_brightness_and_reports_live_volume() -> None:
    service = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_service.cpp").read_text(
        encoding="utf-8"
    )
    board = (FIRMWARE_ROOT / "main" / "hal" / "board" / "stackchan.cc").read_text(encoding="utf-8")

    runtime_settings = service.split("void applyHermesRuntimeSettings", 1)[1].split(
        "std::string randomUuidV4", 1
    )[0]
    assert 'Settings audioSettings("audio", false)' in runtime_settings
    assert 'audioSettings.GetInt("volume", -1)' in runtime_settings
    assert 'Settings displaySettings("display", false)' in runtime_settings
    assert 'displaySettings.GetInt("brightness", -1)' in runtime_settings
    assert "setSpeakerVolume" in runtime_settings
    assert "setBackLightBrightness" in runtime_settings

    live_volume = board.split("uint8_t hal_bridge::board_get_speaker_volume()", 1)[1]
    assert "audio_codec->output_volume()" in live_volume
    assert "if (volume <= 0)" not in live_volume


def test_display_show_text_uses_a_global_toast_instead_of_an_avatar_only_bubble() -> None:
    display = (FIRMWARE_ROOT / "main" / "hal" / "board" / "stackchan_display.cc").read_text(
        encoding="utf-8"
    )
    command_target = (
        FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_command_target.cpp"
    ).read_text(encoding="utf-8")

    notification = display.split("void StackChanAvatarDisplay::ShowNotification", 1)[1]
    show_text = command_target.split("bool OfficialDeviceCommandTarget::showText", 1)[1].split(
        "bool OfficialDeviceCommandTarget::setExpression", 1
    )[0]

    assert "#include <apps/common/toast/toast.h>" in display
    assert "view::pop_a_toast(notification, view::ToastType::Info, duration_ms)" in notification
    assert "display->ShowNotification(text.c_str(), durationMs);" in show_text
    assert "display->SetChatMessage" not in show_text


def test_expression_initializes_the_avatar_before_reporting_success() -> None:
    command_target = (
        FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_command_target.cpp"
    ).read_text(encoding="utf-8")

    set_expression = command_target.split("bool OfficialDeviceCommandTarget::setExpression", 1)[
        1
    ].split("bool OfficialDeviceCommandTarget::setBlink", 1)[0]

    assert "dynamic_cast<StackChanAvatarDisplay*>" in set_expression
    assert "if (!display->IsSetupUICalled())" in set_expression
    assert "display->SetupUI();" in set_expression
    assert "if (!GetStackChan().hasAvatar())" in set_expression
    assert set_expression.index("display->SetupUI();") < set_expression.index("display->SetEmotion")
    assert "presentationDirty_.store(false);" in set_expression
    assert set_expression.index("presentationDirty_.store(false);") < set_expression.index(
        "display->SetEmotion"
    )


def test_global_toast_manager_is_initialized_before_the_bridge_worker() -> None:
    main = (FIRMWARE_ROOT / "main" / "main.cpp").read_text(encoding="utf-8")
    toast = (FIRMWARE_ROOT / "main" / "apps" / "common" / "toast" / "toast.cpp").read_text(
        encoding="utf-8"
    )

    initialize = "view::initialize_toast_manager()"
    bridge_start = "stackchan::hermes::startStackchanHermesBridgeClient()"

    assert "#include <apps/common/toast/toast.h>" in main
    assert "bool view::initialize_toast_manager()" in toast
    assert initialize in main
    assert main.index(initialize) < main.index(bridge_start)
    assert main.index(initialize) < main.index("GetMooncake().update()")


def test_invalid_bridge_config_keeps_an_error_worker_for_local_presentation() -> None:
    service = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_service.cpp").read_text(
        encoding="utf-8"
    )
    startup = service.split("bool startStackchanHermesBridgeClient()", 1)[1]
    initialization_failure = startup.split("if (!operational)", 1)[1].split("}", 1)[0]

    assert "return false;" not in initialization_failure
    assert startup.index("initializationResult") < startup.index("createAbility")
    assert "return operational;" in startup


def test_head_touch_requires_a_longer_press_than_release_or_idle() -> None:
    adapter = (FIRMWARE_ROOT / "main" / "hal" / "hal_head_touch.cpp").read_text(encoding="utf-8")

    assert "_stable_press_samples = 6" in adapter
    assert "_stable_release_samples = 3" in adapter
    assert "HeadTouchDebouncer debouncer{" in adapter
    assert "_stable_press_samples, _stable_release_samples" in adapter


def test_head_touch_press_queues_an_authenticated_touch_event() -> None:
    service = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_service.cpp").read_text(
        encoding="utf-8"
    )

    callback = service.split("GetHAL().onHeadPetGesture.connect(", 1)[1].split(
        "headTouchConnected_ = true;", 1
    )[0]
    running = service.split("void onRunning() override", 1)[1].split("private:", 1)[0]

    assert "gesture == HeadPetGesture::Press" in callback
    assert "touchTapRequested_.store(true);" in callback
    assert "touchTapRequested_.exchange(false)" in running
    assert "client_.sendTouchTap(kHeadTouchEventX, kHeadTouchEventY)" in running
    assert "std::atomic<bool> touchTapRequested_{false};" in service


def test_firmware_discovers_an_authenticated_protocol_v1_bridge_over_mdns() -> None:
    manifest = (FIRMWARE_ROOT / "main" / "idf_component.yml").read_text(encoding="utf-8")
    main_cmake = (FIRMWARE_ROOT / "main" / "CMakeLists.txt").read_text(encoding="utf-8")
    adapter = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_mdns.cpp").read_text(
        encoding="utf-8"
    )
    service = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_service.cpp").read_text(
        encoding="utf-8"
    )

    assert "espressif/mdns: ==1.11.3" in manifest
    assert "mdns" in main_cmake
    assert "mdns_init()" in adapter
    assert 'mdns_query_ptr("_stackchan-hermes", "_tcp", 2000, 4, &results)' in adapter
    assert "mdns_query_results_free" in adapter
    assert "std::unique_ptr<mdns_result_t" in adapter
    assert "&mdns_query_results_free" in adapter
    assert "buildMdnsBridgeWebSocketUrl" in adapter
    assert "bridgeUrlResolver" in service
    assert "discoverStackchanHermesBridgeUrl" in service
    assert "config.bridgeUrlChanged" in service
    assert "cameraCapture.setBridgeUrl(bridgeUrl)" in service


def test_main_exposes_secret_safe_usb_serial_bridge_provisioning() -> None:
    kconfig = (FIRMWARE_ROOT / "main" / "Kconfig.projbuild").read_text(encoding="utf-8")
    main = (FIRMWARE_ROOT / "main" / "main.cpp").read_text(encoding="utf-8")
    provisioning = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_provisioning.cpp").read_text(
        encoding="utf-8"
    )

    assert "config STACKCHAN_HERMES_USB_PROVISIONING" in kconfig
    assert "esp_console_cmd_register" in provisioning
    assert "esp_console_start_repl" in provisioning
    assert 'command.command = "stackchan-hermes"' in provisioning
    for namespace in ("device", "bridge", "audio", "display", "motion", "touch"):
        assert f'Settings settings("{namespace}", true)' in provisioning
    for key in ("id", "name", "url", "fallback_url", "token"):
        assert f'SetString("{key}", result.value)' in provisioning
    for key in ("volume", "brightness", "idle_level"):
        assert f'SetInt("{key}", result.numericValue)' in provisioning
    assert 'SetBool("discovery", result.boolValue)' in provisioning
    assert 'SetBool("enabled", result.boolValue)' in provisioning
    assert "replConfig.history_save_path = nullptr" in provisioning
    assert "replConfig.max_history_len = 1" in provisioning
    assert "linenoiseHistoryFree();" in provisioning
    assert "printf(result.value" not in provisioning
    assert "ESP_LOG" not in provisioning
    assert main.index("startStackchanHermesProvisioningConsole()") < main.index(
        "GetMooncake().installApp"
    )
    assert main.index("startStackchanHermesProvisioningConsole()") < main.index(
        "startStackchanHermesBridgeClient()"
    )


def test_attended_wifi_cycle_is_one_shot_bounded_and_release_disabled() -> None:
    kconfig = (FIRMWARE_ROOT / "main" / "Kconfig.projbuild").read_text(encoding="utf-8")
    defaults = (FIRMWARE_ROOT / "sdkconfig.hermes.defaults").read_text(encoding="utf-8")
    readme = (FIRMWARE_ROOT / "README.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())
    parser = (
        FIRMWARE_ROOT / "components" / "stackchan_bridge_client" / "provisioning.cpp"
    ).read_text(encoding="utf-8")
    provisioning = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_provisioning.cpp").read_text(
        encoding="utf-8"
    )

    option = kconfig.split("config STACKCHAN_HERMES_ATTENDED_WIFI_CYCLE", 1)[1].split(
        "config STACKCHAN_HERMES_TTS_GAIN_PERCENT", 1
    )[0]
    assert "depends on STACKCHAN_HERMES_USB_PROVISIONING" in option
    assert "depends on ESP_CONSOLE_USB_SERIAL_JTAG || ESP_CONSOLE_USB_CDC" in option
    assert "default n" in option
    assert "CONFIG_STACKCHAN_HERMES_ATTENDED_WIFI_CYCLE=n" in defaults
    assert 'command == "cycle-wifi"' in parser
    assert "parseBoundedInteger(value, 5, 30" in parser

    cycle = provisioning.split("case bridge_client::ProvisioningAction::CycleWifi", 1)[1].split(
        "case bridge_client::ProvisioningAction::None", 1
    )[0]
    assert "#if CONFIG_STACKCHAN_HERMES_ATTENDED_WIFI_CYCLE" in cycle
    assert "authorizeAttendedWifiCycle" in cycle
    assert "WifiCycleAuthorization::AlreadyUsed" in cycle
    assert "WifiCycleAuthorization::NotConnected" in cycle
    assert cycle.index("wifi.StopStation()") < cycle.index("vTaskDelay")
    assert cycle.index("vTaskDelay") < cycle.index("wifi.StartStation()")
    assert "Settings settings" not in cycle
    assert "stackchan-hermes cycle-wifi 15" in normalized_readme
    assert "once per boot" in normalized_readme
    assert "does not modify stored Wi-Fi credentials" in normalized_readme
    assert "restore a normal release image" in normalized_readme


def test_main_keeps_bridge_settings_within_the_esp_idf_nvs_key_limit() -> None:
    sources = [
        (FIRMWARE_ROOT / "main" / "hal" / filename).read_text(encoding="utf-8")
        for filename in ("stackchan_bridge_provisioning.cpp", "stackchan_bridge_service.cpp")
    ]
    keys = [
        key
        for source in sources
        for key in re.findall(r'\b(?:Get|Set)(?:Bool|Int|String)\("([^"]+)"', source)
    ]

    assert keys
    assert all(len(key.encode("utf-8")) <= 15 for key in keys)


def test_firmware_contract_matches_bridge_protocol_and_bounds_every_stream() -> None:
    path = ROOT / "firmware" / "stackchan-bridge-client.contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))

    assert contract["version"] == 1
    assert contract["transport"] == {
        "websocket_path": "/v1/device/ws",
        "capture_upload_path": "/v1/device/captures/{capture_id}",
        "max_json_bytes": MAX_JSON_BYTES,
        "max_json_depth": 8,
        "max_audio_packet_bytes": MAX_AUDIO_PACKET_BYTES,
        "duplicate_message_ids": 256,
        "input_streams_per_device": 1,
        "output_streams_per_device": 1,
    }
    assert contract["audio"]["sample_rate"] == 16_000
    assert contract["audio"]["channels"] == 1
    assert contract["audio"]["allowed_frame_ms"] == [20, 40, 60]
    assert contract["audio"]["queue_packets"] > 0
    assert contract["audio"]["queue_packets"] <= 128
    assert contract["audio"]["input_overflow_policy"] == "drop_oldest_and_report"
    assert contract["audio"]["output_overflow_policy"] == "reject_new_and_report"
    assert contract["camera"]["max_jpeg_bytes"] == 2_097_152
    assert contract["camera"]["concurrent_capture_policy"] == "device_busy"
    assert contract["camera"]["max_upload_attempts"] == 3
    session = (FIRMWARE_ROOT / "components" / "stackchan_bridge_client" / "session.cpp").read_text(
        encoding="utf-8"
    )
    assert "constexpr std::size_t kSeenMessageIdLimit = 256" in session


def test_camera_frame_bytes_are_never_written_to_logs() -> None:
    camera_source = (FIRMWARE_ROOT / "main" / "hal" / "board" / "stackchan_camera.cc").read_text(
        encoding="utf-8"
    )

    assert "ESP_LOG_BUFFER_HEXDUMP" not in camera_source


def test_camera_network_work_starts_only_after_the_command_result_can_be_sent() -> None:
    camera_header = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_camera.h").read_text(
        encoding="utf-8"
    )
    camera_source = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_camera.cpp").read_text(
        encoding="utf-8"
    )
    service = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_service.cpp").read_text(
        encoding="utf-8"
    )
    start_body = camera_source.split("OfficialCameraCapture::start(", 1)[1].split(
        "bool OfficialCameraCapture::completion", 1
    )[0]

    assert "void update();" in camera_header
    assert "worker_ = std::thread" not in start_body
    assert "gate_.takePending(request)" in camera_source
    assert service.index("client_.update(nowMs);") < service.index("cameraCapture_.update();")


def test_camera_worker_has_a_scoped_stack_budget_for_capture_and_upload() -> None:
    camera_source = (FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_camera.cpp").read_text(
        encoding="utf-8"
    )
    main_cmake = (FIRMWARE_ROOT / "main" / "CMakeLists.txt").read_text(encoding="utf-8")

    assert "#include <esp_pthread.h>" in camera_source
    assert "constexpr std::size_t kCameraWorkerStackSize = 12 * 1024;" in camera_source
    assert "esp_pthread_get_cfg(&previous_)" in camera_source
    assert "esp_pthread_get_default_config()" in camera_source
    assert "configuration.stack_size = kCameraWorkerStackSize;" in camera_source
    assert "configuration.inherit_cfg = false;" in camera_source
    assert "esp_pthread_set_cfg(&configuration)" in camera_source
    assert "restore();" in camera_source
    assert "ScopedPthreadConfig cameraThreadConfig" in camera_source
    assert "if (!cameraThreadConfig.applied())" in camera_source
    assert re.search(r"PRIV_REQUIRES(?:(?!\)).)*\bpthread\b", main_cmake, re.DOTALL)


def test_camera_worker_schedules_shutter_audio_on_the_local_main_task() -> None:
    camera_source = (FIRMWARE_ROOT / "main" / "hal" / "board" / "stackchan_camera.cc").read_text(
        encoding="utf-8"
    )
    hal_bridge_header = (FIRMWARE_ROOT / "main" / "hal" / "board" / "hal_bridge.h").read_text(
        encoding="utf-8"
    )
    hal_bridge_source = (FIRMWARE_ROOT / "main" / "hal" / "board" / "hal_bridge.cc").read_text(
        encoding="utf-8"
    )
    capture_body = camera_source.split("bool StackChanCamera::Capture()", 1)[1].split(
        "bool StackChanCamera::StreamCaptures", 1
    )[0]

    assert "bool app_schedule(std::function<void()> callback);" in hal_bridge_header
    assert "hal_bridge::app_schedule([]()" in capture_body
    assert "hal_bridge::app_play_sound(OGG_CAMERA_SHUTTER);" in capture_body
    assert capture_body.index("hal_bridge::app_schedule([]()") < capture_body.index(
        "hal_bridge::app_play_sound(OGG_CAMERA_SHUTTER);"
    )
    assert "local_tasks.schedule(std::move(callback));" in hal_bridge_source
    assert "Application::" not in hal_bridge_source
    assert "service.Initialize(codec);" in hal_bridge_source
    main = (FIRMWARE_ROOT / "main/main.cpp").read_text()
    assert "hal_bridge::update_local_tasks();" in main
    assert "hal_bridge::app_play_sound(OGG_CAMERA_SHUTTER);\n\n    for" not in capture_body


def test_offline_startup_keeps_local_ui_and_defers_bridge_discovery_until_wifi_is_ready() -> None:
    main = (FIRMWARE_ROOT / "main/main.cpp").read_text()
    network = (FIRMWARE_ROOT / "main/hal/hal_network.cpp").read_text()
    worker = (FIRMWARE_ROOT / "main/hal/stackchan_bridge_service.cpp").read_text()
    running = worker.split("void onRunning() override", 1)[1].split("private:", 1)[0]
    start = worker.split("bool startStackchanHermesBridgeClient()", 1)[1]
    assert "while (!network_connected)" not in network
    assert "GetMooncake().update();" in main
    assert "startXiaozhi" not in main
    assert "skip_mooncake" not in main
    assert "worker->wifiConnected()" not in start
    assert "WifiManager::GetInstance().IsConnected()" in running
    assert "DeviceState::ConnectingWifi" in running
    assert "client_.wifiConnected()" in running


def test_leaving_speaking_always_stops_the_local_mouth_animation() -> None:
    display = (FIRMWARE_ROOT / "main" / "hal" / "board" / "stackchan_display.cc").read_text(
        encoding="utf-8"
    )
    command_target = (
        FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_command_target.cpp"
    ).read_text(encoding="utf-8")

    assert "strcmp(status, Lang::Strings::SPEAKING) != 0 && speaking_modifier_id_ >= 0" in display
    assert "stackchan.removeModifier(speaking_modifier_id_)" in display
    assert "avatar.mouth().setWeight(0)" in display
    avatar_presentation = command_target.split(
        "if (display != nullptr && display->IsSetupUICalled()", 1
    )[1].split("if (!textVisible_", 1)[0]
    reconnect_presentation = avatar_presentation.split(
        "case bridge_client::DeviceState::ConnectingBridge:", 1
    )[1].split("break;", 1)[0]
    assert 'display->SetEmotion("neutral")' in reconnect_presentation


def test_bridge_reconnect_presentation_uses_launcher_visible_notifications() -> None:
    command_target = (
        FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_command_target.cpp"
    ).read_text(encoding="utf-8")

    notification_path = command_target.split(
        "if (display != nullptr && notificationDirty_.exchange(false))", 1
    )[1].split("if (display != nullptr && display->IsSetupUICalled()", 1)[0]
    connecting = notification_path.split("case bridge_client::DeviceState::ConnectingBridge:", 1)[
        1
    ].split("break;", 1)[0]
    connected = notification_path.split("case bridge_client::DeviceState::Idle:", 1)[1].split(
        "break;", 1
    )[0]

    assert 'display->ShowNotification("Connecting Bridge", 3000)' in connecting
    assert 'display->ShowNotification("Bridge connected", 1600)' in connected


def test_bridge_reconnect_notifications_do_not_wait_for_avatar_ui() -> None:
    command_target = (
        FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_command_target.cpp"
    ).read_text(encoding="utf-8")
    command_target_header = (
        FIRMWARE_ROOT / "main" / "hal" / "stackchan_bridge_command_target.h"
    ).read_text(encoding="utf-8")

    apply_state = command_target.split("void OfficialDeviceCommandTarget::applyBridgeState", 1)[
        1
    ].split("void OfficialDeviceCommandTarget::update", 1)[0]

    assert "std::atomic<bool> notificationDirty_{true}" in command_target_header
    assert "notificationDirty_.store(true)" in apply_state
    notification_path = command_target.split(
        "if (display != nullptr && notificationDirty_.exchange(false))", 1
    )[1].split("if (display != nullptr && display->IsSetupUICalled()", 1)[0]
    assert "IsSetupUICalled" not in notification_path
    assert 'display->ShowNotification("Connecting Bridge", 3000)' in notification_path
    assert 'display->ShowNotification("Bridge connected", 1600)' in notification_path


def test_firmware_contract_records_verified_k151_motion_limits_and_locked_default() -> None:
    contract = json.loads(
        (ROOT / "firmware" / "stackchan-bridge-client.contract.json").read_text(encoding="utf-8")
    )

    safety = contract["motion_safety"]
    assert safety["board_limits_required"] is True
    assert safety["unconfigured_behavior"] == "reject_all_motion"
    assert safety["out_of_range_behavior"] == "error_not_clamp"
    assert safety["autonomous_motion_may_clamp"] is True
    assert safety["yaw"] == {"minimum_degrees": -45, "maximum_degrees": 45}
    assert safety["pitch"] == {"minimum_degrees": 5, "maximum_degrees": 85}
    assert safety["speed"] == {"minimum": 1, "maximum": 30, "default": 15}
    assert safety["home"] == {"yaw_degrees": 0, "pitch_degrees": 45}
    assert safety["release_motion_lock_default"] is True
    assert safety["unlock_requires_explicit_build_and_physical_approval"] is True
    assert safety["attended_candidate_local_motion_lock_default"] is True
    assert safety["attended_candidate_allowed_source"] == "authenticated_bridge_only"
    assert safety["flash_approval_does_not_authorize_motion"] is True
    assert safety["limit_source"] == {
        "pinned_upstream_commit": "1b5765599fba8aaad1811d9a79358ccc7051f5f3",
        "official_servo_documentation": "https://docs.m5stack.com/ja/arduino/stackchan/servo",
        "selection": "conservative_subset",
    }


def test_firmware_contract_freezes_reconnect_state_and_settings_precedence() -> None:
    contract_text = (ROOT / "firmware" / "stackchan-bridge-client.contract.json").read_text(
        encoding="utf-8"
    )
    contract = json.loads(contract_text)

    assert contract["reconnect"] == {
        "delays_seconds": [1, 2, 4, 8, 16, 30],
        "maximum_seconds": 30,
        "stable_reset_seconds": 30,
        "destroy_stale_tasks_before_connect": True,
    }
    assert contract["states"] == [
        "BOOTING",
        "CONNECTING_WIFI",
        "CONNECTING_BRIDGE",
        "IDLE",
        "LISTENING",
        "SPEAKING",
        "ERROR",
        "UPDATING",
    ]
    assert contract["bridge_url_precedence"] == [
        "nvs.bridge.url",
        "mdns._stackchan-hermes._tcp.local",
        "nvs.bridge.fallback_url",
        "kconfig.default_bridge_url",
        "explicit_error",
    ]
    assert set(contract["nvs_keys"]) == {
        "device.id",
        "device.name",
        "bridge.url",
        "bridge.fallback_url",
        "bridge.token",
        "bridge.discovery",
        "audio.volume",
        "display.brightness",
        "motion.idle_level",
        "touch.enabled",
    }
    assert contract["provisioning"] == {
        "selected_path": "usb_serial_utility",
        "status": "implemented_hardware_verified",
        "runtime_change_without_rebuild": True,
        "tracked_credentials": False,
    }
    lowered = contract_text.lower()
    assert "api_key" not in lowered
    assert "password" not in lowered

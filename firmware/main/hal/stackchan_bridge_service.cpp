#include "stackchan_bridge_service.h"

#include <array>
#include <atomic>
#include <memory>
#include <mutex>
#include <utility>

#include <audio/audio_service.h>
#include "board/hal_bridge.h"
#include <board.h>
#include <esp_app_desc.h>
#include <esp_log.h>
#include <esp_random.h>
#include <mooncake.h>
#include <settings.h>
#include <wifi_manager.h>
#include <stackchan_bridge_client/command_executor.h>
#include <stackchan_bridge_client/audio_safety.h>
#include <stackchan_bridge_client/hardware_identity.h>
#include <stackchan_bridge_client/message_id.h>
#include <stackchan_bridge_client/settings.h>

#include "hal.h"
#include "stackchan_bridge_camera.h"
#include "stackchan_bridge_command_target.h"
#include "stackchan_bridge_mdns.h"
#include "stackchan_bridge_websocket.h"

namespace stackchan::hermes {
namespace {

constexpr char kTag[] = "HermesBridge";
constexpr int kHeadTouchEventX = 160;
constexpr int kHeadTouchEventY = 0;

void applyHermesRuntimeSettings(Board& board)
{
    Settings audioSettings("audio", false);
    const int volume = audioSettings.GetInt("volume", -1);
    if (board.GetAudioCodec() != nullptr && volume >= 0 && volume <= 100) {
        GetHAL().setSpeakerVolume(static_cast<std::uint8_t>(volume), false);
    }

    Settings displaySettings("display", false);
    const int brightness = displaySettings.GetInt("brightness", -1);
    if (board.GetDisplay() != nullptr && brightness >= 0 && brightness <= 100) {
        GetHAL().setBackLightBrightness(static_cast<std::uint8_t>(brightness), false);
    }
}

std::string randomUuidV4()
{
    std::array<std::uint8_t, 16> bytes{};
    esp_fill_random(bytes.data(), bytes.size());
    return bridge_client::formatUuidV4(bytes);
}

bridge_client::BridgeClientConfig loadBridgeClientConfig(Board& board)
{
    Settings deviceSettings("device", false);
    Settings bridgeSettings("bridge", false);
    Settings touchSettings("touch", false);

    bridge_client::BridgeEndpointSources endpoints;
    endpoints.nvsUrl     = bridgeSettings.GetString("url", "");
    endpoints.nvsFallbackUrl = bridgeSettings.GetString("fallback_url", "");
    endpoints.kconfigUrl = CONFIG_STACKCHAN_HERMES_DEFAULT_BRIDGE_URL;
    endpoints.discoveryEnabled = bridgeSettings.GetBool("discovery", true);

    bridge_client::BridgeClientConfig config;
    if (endpoints.nvsUrl.empty() && endpoints.discoveryEnabled) {
        config.bridgeUrlResolver = [endpoints = std::move(endpoints)]() mutable {
            endpoints.mdnsUrl = discoverStackchanHermesBridgeUrl();
            const auto endpoint = bridge_client::resolveBridgeEndpoint(endpoints);
            return endpoint.ok ? endpoint.url : std::string{};
        };
    } else {
        const auto endpoint = bridge_client::resolveBridgeEndpoint(endpoints);
        if (endpoint.ok) {
            config.bridgeUrl = endpoint.url;
        }
    }
    config.deviceToken             = bridgeSettings.GetString("token", "");
    config.helloEnvelope.messageId = board.GetUuid();
    config.helloEnvelope.sentAtMs  = GetHAL().millis();
    config.hello.deviceId          = deviceSettings.GetString("id", board.GetUuid());
    config.hello.deviceName        = deviceSettings.GetString("name", "StackChan");
    config.hello.firmwareVersion   = esp_app_get_description()->version;
    config.hello.hardwareModel     = bridge_client::kStackChanHardwareModel;
    config.hello.capabilities.microphone = board.GetAudioCodec() != nullptr;
    config.hello.capabilities.speaker    = board.GetAudioCodec() != nullptr;
    config.hello.capabilities.camera     = false;
    config.hello.capabilities.touch      = touchSettings.GetBool("enabled", true);
#if CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK
    config.hello.capabilities.head       = false;
#else
    config.hello.capabilities.head       = true;
#endif
    config.hello.capabilities.display    = board.GetDisplay() != nullptr;
    config.hello.capabilities.avatar     = board.GetDisplay() != nullptr;
    config.hello.capabilities.ledCount   = 12;
    config.hello.audio.codec              = "opus";
    config.hello.audio.sampleRate         = 16000;
    config.hello.audio.channels           = 1;
    config.hello.audio.frameMs            = 60;
#ifdef CONFIG_STACKCHAN_HERMES_MAX_RECORDING_MS
    config.audioInputMaxDurationMs = CONFIG_STACKCHAN_HERMES_MAX_RECORDING_MS;
#endif
#ifdef CONFIG_STACKCHAN_HERMES_PLAYBACK_PREROLL_MS
    config.audioOutputPrerollMs = CONFIG_STACKCHAN_HERMES_PLAYBACK_PREROLL_MS;
#endif
    return config;
}

bridge_client::BridgeClientConfig bindRuntimeHandlers(
    bridge_client::BridgeClientConfig config,
    OfficialDeviceCommandTarget& commandTarget,
    OfficialCameraCapture& cameraCapture,
    AudioService& audioService
)
{
    config.hello.capabilities.camera = cameraCapture.available();
    config.commandHandler = [&commandTarget](const bridge_client::Command& command) {
        return bridge_client::executeCommand(command, commandTarget);
    };
    config.playbackFlushHandler = [&audioService]() {
        audioService.ResetDecoder();
    };
    config.bridgeUrlChanged = [&cameraCapture](const std::string& bridgeUrl) {
        cameraCapture.setBridgeUrl(bridgeUrl);
    };
    config.stateChanged = [&commandTarget, &audioService](bridge_client::DeviceState state) {
        if (state == bridge_client::DeviceState::Speaking) {
            audioService.ResetDecoder();
        }
        commandTarget.applyBridgeState(state);
    };
    config.envelopeFactory = []() {
        bridge_client::EnvelopeMetadata envelope;
        envelope.messageId = randomUuidV4();
        envelope.sentAtMs = GetHAL().millis();
        return envelope;
    };
    commandTarget.cancelCaptureCallback = [&cameraCapture](const std::string& id) { return cameraCapture.cancel(id); };
    config.cameraCompletedAcknowledged = [&cameraCapture](const std::string& id) { cameraCapture.acknowledgeCompletion(id); };
    commandTarget.setStartCaptureCallback(
        [&cameraCapture](const std::string& captureId, int quality, int timeoutMs) {
            return cameraCapture.start(captureId, quality, timeoutMs);
        }
    );
    return config;
}

class BridgeClientWorker final : public mooncake::BasicAbility {
public:
    BridgeClientWorker(NetworkInterface& network, bridge_client::BridgeClientConfig config)
        : touchEnabled_(config.hello.capabilities.touch),
          cameraCapture_(
              Board::GetInstance(),
              network,
              config.bridgeUrl,
              config.deviceToken,
              config.hello.deviceId
          ),
          commandTarget_(Board::GetInstance(), config.hello.capabilities.ledCount),
          transport_(network),
          client_(
              transport_,
              bindRuntimeHandlers(
                  std::move(config), commandTarget_, cameraCapture_, audioService_
              )
          )
    {
    }

    ~BridgeClientWorker() override
    {
        if (headTouchConnected_) {
            GetHAL().onHeadPetGesture.disconnect(headTouchConnection_);
        }
        if (audioStarted_) {
            if (recording_) {
                audioService_.EnableVoiceProcessing(false);
            }
            AudioServiceCallbacks callbacks;
            audioService_.SetCallbacks(callbacks);
        }
    }

    bridge_client::ClientError initialize()
    {
        const auto result = client_.initialize();
        if (result != bridge_client::ClientError::None) {
            return result;
        }
        auto* codec = Board::GetInstance().GetAudioCodec();
        if (codec != nullptr) {
#ifdef CONFIG_STACKCHAN_HERMES_TTS_GAIN_PERCENT
            audioService_.SetPlaybackGainPercent(CONFIG_STACKCHAN_HERMES_TTS_GAIN_PERCENT);
#endif
            AudioServiceCallbacks callbacks;
            callbacks.on_decode_result = [this](bool success) {
                std::lock_guard<std::mutex> lock(decodeFailureMutex_);
                if (success) {
                    decodeFailureGate_.observeSuccess();
                } else if (decodeFailureGate_.observeFailure()) {
                    decodeFailureRequested_.store(true);
                }
            };
            audioService_.SetCallbacks(callbacks);
            audioStarted_ = true;
            commandTarget_.setCancelSpeechCallback([this]() {
                audioService_.ResetDecoder();
            });
            if (touchEnabled_) {
                headTouchConnection_ = GetHAL().onHeadPetGesture.connect(
                    [this](HeadPetGesture gesture) {
                        if (gesture == HeadPetGesture::Press) {
                            touchTapRequested_.store(true);
                            inputStartRequested_.store(true);
                        } else if (gesture == HeadPetGesture::Release) {
                            inputEndRequested_.store(true);
                        }
                    }
                );
                headTouchConnected_ = true;
            }
        }
        return bridge_client::ClientError::None;
    }

    void onRunning() override
    {
        if (client_.state() == bridge_client::DeviceState::ConnectingWifi
            && WifiManager::GetInstance().IsConnected()) {
            client_.wifiConnected();
        }
        const std::uint32_t nowMs = GetHAL().millis();
        if (recording_) { hal_bridge::note_activity(); }
        commandTarget_.update(nowMs);
        client_.update(nowMs);
        cameraCapture_.update();
        CameraCaptureCompletion captureCompletion;
        if (cameraCapture_.completion(captureCompletion)) {
            const auto result = client_.sendCameraCompleted(
                captureCompletion.captureId,
                captureCompletion.ok,
                captureCompletion.error, captureCompletion.digest, captureCompletion.sizeBytes
            );
            ESP_LOGI("Capture", "capture_id=%s stage=completion_send ok=%d result=%d resources_released=1",
                captureCompletion.captureId.c_str(), captureCompletion.ok, static_cast<int>(result));
        }
        if (touchTapRequested_.exchange(false)) {
            client_.sendTouchTap(kHeadTouchEventX, kHeadTouchEventY);
        }
        if (audioStarted_) {
            if (decodeFailureRequested_.exchange(false)) {
                audioService_.ResetDecoder();
                client_.reportAudioDecodeFailure();
                std::lock_guard<std::mutex> lock(decodeFailureMutex_);
                decodeFailureGate_.reset();
            }
            handleAudioInputRequests();
            if (recording_ && client_.state() != bridge_client::DeviceState::Listening) {
                audioService_.EnableVoiceProcessing(false);
                recording_ = false;
                discardEncodedAudio();
            }
            if (recording_) {
                for (int index = 0; index < 4; ++index) {
                    auto packet = audioService_.PopPacketFromSendQueue();
                    if (!packet) {
                        break;
                    }
                    if (client_.sendAudioInputPacket(
                            packet->payload.data(), packet->payload.size()
                        ) != bridge_client::AudioInputError::None) {
                        audioService_.EnableVoiceProcessing(false);
                        recording_ = false;
                        discardEncodedAudio();
                        break;
                    }
                }
            }
            client_.deliverAudioOutputPacket(
                audioService_.IsIdle(),
                [this](
                    int sampleRate,
                    int frameMs,
                    const std::vector<std::uint8_t>& bytes
                ) {
                    auto packet = std::make_unique<AudioStreamPacket>();
                    packet->sample_rate = sampleRate;
                    packet->frame_duration = frameMs;
                    packet->payload = bytes;
                    return audioService_.PushPacketToDecodeQueue(std::move(packet), false);
                }
            );
            if (client_.audioOutputDeliveryComplete() && audioService_.IsIdle()) {
                client_.acknowledgeAudioOutputPlayback();
            }
        }
    }

private:
    void handleAudioInputRequests()
    {
        if (inputStartRequested_.exchange(false) && !recording_) {
            discardEncodedAudio();
            if (client_.beginAudioInput(
                    randomUuidV4(), randomUuidV4(), bridge_client::AudioInputTrigger::Touch
                ) == bridge_client::AudioInputError::None) {
                audioService_.EnableVoiceProcessing(true);
                recording_ = true;
            }
        }
        if (inputEndRequested_.exchange(false) && recording_) {
            for (int index = 0; index < 4; ++index) {
                auto packet = audioService_.PopPacketFromSendQueue();
                if (!packet) {
                    break;
                }
                if (client_.sendAudioInputPacket(
                        packet->payload.data(), packet->payload.size()
                    ) != bridge_client::AudioInputError::None) {
                    break;
                }
            }
            audioService_.EnableVoiceProcessing(false);
            recording_ = false;
            client_.endAudioInput(bridge_client::AudioInputEndReason::Silence);
            discardEncodedAudio();
        }
    }

    void discardEncodedAudio()
    {
        while (audioService_.PopPacketFromSendQueue()) {
        }
    }

    bool touchEnabled_ = true;
    OfficialCameraCapture cameraCapture_;
    OfficialDeviceCommandTarget commandTarget_;
    AudioService& audioService_ = hal_bridge::local_audio();
    std::mutex decodeFailureMutex_;
    bridge_client::ConsecutiveFailureGate decodeFailureGate_{3};
    std::atomic<bool> decodeFailureRequested_{false};
    bool audioStarted_ = false;
    bool recording_ = false;
    std::atomic<bool> touchTapRequested_{false};
    std::atomic<bool> inputStartRequested_{false};
    std::atomic<bool> inputEndRequested_{false};
    std::size_t headTouchConnection_ = 0;
    bool headTouchConnected_ = false;
    OfficialWebSocketTransport transport_;
    bridge_client::BridgeClient client_;
};

}  // namespace

bool startStackchanHermesBridgeClient()
{
    auto& board = Board::GetInstance();
    auto* network = board.GetNetwork();
    if (network == nullptr) {
        ESP_LOGE(kTag, "Network interface is unavailable");
        return false;
    }

    applyHermesRuntimeSettings(board);

    auto worker = std::make_unique<BridgeClientWorker>(*network, loadBridgeClientConfig(board));
    const auto initializationResult = worker->initialize();
    bool operational = initializationResult == bridge_client::ClientError::None;
    if (!operational) {
        ESP_LOGE(kTag, "Bridge configuration is missing or invalid");
    } else {
        GetHAL().startNetwork(nullptr);
    }

    const int abilityId = mooncake::GetMooncake().extensionManager()->createAbility(
        std::move(worker)
    );
    if (abilityId < 0) {
        ESP_LOGE(kTag, "Bridge worker registration failed");
        return false;
    }
    return operational;
}

}  // namespace stackchan::hermes

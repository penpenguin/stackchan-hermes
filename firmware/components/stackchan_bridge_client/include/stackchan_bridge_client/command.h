#pragma once

#include <cstdint>
#include <string>
#include <variant>
#include <vector>

#include <stackchan_bridge_client/protocol.h>

namespace stackchan::bridge_client {

enum class CommandName {
    Unknown,
    DeviceGetStatus,
    DeviceGetInfo,
    AudioSetVolume,
    DisplaySetBrightness,
    DisplayShowText,
    AvatarSetExpression,
    AvatarSetBlink,
    HeadGetAngles,
    HeadSetAngles,
    HeadHome,
    LedSet,
    LedSetAll,
    LedClear,
    CameraCapture,
    SpeechCancel,
};

enum class CommandParseError {
    None,
    MessageTooLarge,
    InvalidMessage,
    InvalidArgument,
};

enum class CommandErrorCode {
    None,
    InvalidArgument,
    InvalidState,
    DeviceBusy,
};

enum class CommandResultBuildError {
    None,
    InvalidArgument,
    MessageTooLarge,
};

using CommandResultValue = std::variant<bool, std::int64_t, double, std::string>;

struct CommandResultField {
    std::string name;
    CommandResultValue value;
};

struct CommandExecutionResult {
    bool ok = false;
    CommandErrorCode errorCode = CommandErrorCode::None;
    std::string errorMessage;
    std::vector<CommandResultField> fields;
};

struct CommandArguments {
    int volume = 0;
    int brightness = 0;
    std::string text;
    int durationMs = 0;
    int priority = 0;
    std::string expression;
    bool enabled = false;
    double yaw = 0;
    double pitch = 0;
    bool hasSpeed = false;
    int speed = 0;
    int index = 0;
    int red = 0;
    int green = 0;
    int blue = 0;
    std::string captureId;
    int quality = 0;
};

struct Command {
    CommandName name = CommandName::Unknown;
    std::string messageId;
    std::string requestId;
    std::string turnId;
    std::string streamId;
    std::string deviceId;
    std::uint64_t sentAtMs = 0;
    CommandArguments arguments;
};

CommandParseError parseCommandJson(const std::string& input, Command& output);

bool isSameCommandRequest(const Command& left, const Command& right);

CommandResultBuildError buildCommandResultJson(
    const EnvelopeMetadata& envelope,
    const std::string& requestId,
    const CommandExecutionResult& result,
    std::string& output
);

}  // namespace stackchan::bridge_client

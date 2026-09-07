"""Board-specific physical motion profiles shared by Bridge entry points."""

from __future__ import annotations

from dataclasses import dataclass

from stackchan_bridge.protocol.models import HomeHeadCommand, SetHeadAnglesCommand


@dataclass(frozen=True, slots=True)
class MotionSafetyProfile:
    yaw_minimum_degrees: float
    yaw_maximum_degrees: float
    pitch_minimum_degrees: float
    pitch_maximum_degrees: float
    speed_minimum: int
    speed_maximum: int
    default_speed: int
    home_yaw_degrees: float
    home_pitch_degrees: float


K151_HARDWARE_MODEL = "M5STACK-K151"
SIMULATOR_HARDWARE_MODEL = "SIMULATOR"
K151_MOTION_SAFETY = MotionSafetyProfile(
    yaw_minimum_degrees=-45.0,
    yaw_maximum_degrees=45.0,
    pitch_minimum_degrees=5.0,
    pitch_maximum_degrees=85.0,
    speed_minimum=1,
    speed_maximum=30,
    default_speed=15,
    home_yaw_degrees=0.0,
    home_pitch_degrees=45.0,
)


class MotionSafetyError(ValueError):
    """A protocol-valid command exceeds the connected board's physical profile."""


def validate_motion_command(
    hardware_model: str,
    command: SetHeadAnglesCommand | HomeHeadCommand,
) -> None:
    """Reject motion without an explicit board profile, and never clamp silently."""

    if hardware_model == SIMULATOR_HARDWARE_MODEL:
        return
    if hardware_model != K151_HARDWARE_MODEL:
        raise MotionSafetyError("unsupported hardware motion profile")
    profile = K151_MOTION_SAFETY
    speed = command.args.speed
    resolved_speed = profile.default_speed if speed is None else speed
    if isinstance(command, SetHeadAnglesCommand):
        valid = (
            profile.yaw_minimum_degrees <= command.args.yaw <= profile.yaw_maximum_degrees
            and profile.pitch_minimum_degrees <= command.args.pitch <= profile.pitch_maximum_degrees
            and profile.speed_minimum <= resolved_speed <= profile.speed_maximum
        )
    else:
        valid = profile.speed_minimum <= resolved_speed <= profile.speed_maximum
    if not valid:
        raise MotionSafetyError("command is outside the K151 motion safety profile")

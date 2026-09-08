#pragma once
#include <string>
#include <vector>

namespace uitk { struct Vector2i { int x = 0, y = 0; }; }
namespace stackchan::avatar {
struct Feature {
    void setPosition(uitk::Vector2i) { ++updates; }
    void setRotation(int) { ++updates; }
    void setWeight(int) { ++updates; }
    void setSize(int) { ++updates; }
    int updates = 0;
};
struct Avatar {
    Feature& leftEye() { return left; }
    Feature& rightEye() { return right; }
    Feature& mouth() { return lips; }
    Feature left, right, lips;
};
void update_from_json(Avatar*, const char*);
}
namespace stackchan::motion {
struct Servo {
    void rotate(int) { ++updates; }
    void move(int) { ++updates; }
    void moveWithSpeed(int, int) { ++updates; }
    void moveWithSpringParams(int, float, float) { ++updates; }
    int updates = 0;
};
struct Motion {
    Servo& yawServo() { return yaw; }
    Servo& pitchServo() { return pitch; }
    Servo yaw, pitch;
};
void update_from_json(Motion*, const char*);
}
namespace stackchan::animation {
struct FeatureKeyframe {
    uitk::Vector2i position;
    int rotation = 0, weight = 0, size = 0;
};
struct ServoKeyframe { int angle = 0, speed = 0; };
struct Keyframe {
    FeatureKeyframe leftEye, rightEye, mouth;
    ServoKeyframe yawServo, pitchServo;
    std::string leftRgbColor, rightRgbColor;
    int durationMs = 0;
};
using KeyframeSequence = std::vector<Keyframe>;
}
namespace stackchan::addon {
struct NeonLight {
    void setDuration(float) { ++updates; }
    void setColor(const std::string&) { ++updates; }
    int updates = 0;
};
void update_neon_light_from_json(NeonLight*, NeonLight*, const char*);
}

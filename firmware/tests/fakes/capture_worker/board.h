#pragma once
#include <camera.h>
class Board { public: Camera* camera=nullptr; Camera* GetCamera() const { return camera; } };

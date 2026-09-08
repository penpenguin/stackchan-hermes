#pragma once
class Camera { public: virtual ~Camera()=default; virtual bool Capture()=0; virtual bool SetHMirror(bool)=0; virtual bool SetVFlip(bool)=0; };

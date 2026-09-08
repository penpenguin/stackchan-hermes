#pragma once

#include <memory>
#include <utility>
#include <http.h>
#include <stackchan_bridge_client/camera_capture.h>

namespace stackchan::hermes {

// The pinned HttpClient returns redirects as status codes; it never follows Location.
class OfficialCameraUploadTransport final : public bridge_client::CameraUploadTransport {
public:
    explicit OfficialCameraUploadTransport(std::unique_ptr<Http> http)
        : http_(std::move(http))
    {
    }

    bool valid() const
    {
        return http_ != nullptr;
    }

    void setTimeoutMs(int timeoutMs) override
    {
        http_->SetTimeout(timeoutMs);
    }

    void setHeader(const std::string& name, const std::string& value) override
    {
        http_->SetHeader(name, value);
    }

    bool openPost(const std::string& url) override
    {
        return http_->Open("POST", url);
    }

    bool write(const std::uint8_t* data, std::size_t size) override
    {
        const char* bytes = size == 0 ? "" : reinterpret_cast<const char*>(data);
        return http_->Write(bytes, size) >= 0;
    }

    int statusCode() override
    {
        return http_->GetStatusCode();
    }

    void close() override
    {
        http_->Close();
    }

private:
    std::unique_ptr<Http> http_;
};

}  // namespace stackchan::hermes

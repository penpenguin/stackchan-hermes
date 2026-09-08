#pragma once

#include <algorithm>
#include <cstdint>
#include <deque>
#include <string>
#include <stackchan_bridge_client/camera_capture.h>

namespace stackchan::bridge_client {

class CaptureDeadline {
public:
    CaptureDeadline(std::uint64_t now, std::uint32_t budget)
        : end_(now + budget), reserve_(std::min<std::uint32_t>(1000, budget / 5)) {}
    void constrain(std::uint64_t requestStarted, std::uint32_t remainingMs)
    {
        end_ = std::min(end_, requestStarted + remainingMs);
    }
    std::uint32_t remaining(std::uint64_t now) const
    { return now < end_ ? static_cast<std::uint32_t>(end_ - now) : 0; }
    std::uint64_t end() const { return end_; }
    std::uint64_t workEnd() const { return end_ > reserve_ ? end_ - reserve_ : 0; }
    std::uint64_t operationDeadline(std::uint64_t now) const
    { return std::min(workEnd(), now + 3000); }
private:
    std::uint64_t end_;
    std::uint32_t reserve_;
};

enum class UploadDisposition { Succeeded, Retryable, Permanent };

inline UploadDisposition classifyCaptureUpload(int status)
{
    if (status == 201) { return UploadDisposition::Succeeded; }
    if (status < 0 || status == 408 || (status >= 500 && status <= 599 && status != 501 && status != 505)) {
        return UploadDisposition::Retryable;
    }
    return UploadDisposition::Permanent;
}

inline int captureRetryDelay(int status, const std::string& retryAfter, int attempt, int remainingMs)
{
    if (attempt >= 3 || remainingMs <= 0) { return -1; }
    int delay = attempt == 1 ? 250 : 500;
    if (status == 429) {
        if (retryAfter.empty() || retryAfter.size() > 3) { return -1; }
        delay = 0;
        for (char digit : retryAfter) {
            if (digit < '0' || digit > '9') { return -1; }
            delay = delay * 10 + digit - '0';
        }
        if (delay <= 0 || delay > 120) { return -1; }
        delay *= 1000;
    } else if (classifyCaptureUpload(status) != UploadDisposition::Retryable) {
        return -1;
    }
    return delay < remainingMs ? delay : -1;
}

struct CaptureCompletionNotice {
    std::string captureId;
    bool ok = false;
    CameraCompletionError error = CameraCompletionError::CaptureFailed;
    std::string digest;
    std::size_t sizeBytes = 0;
    std::uint64_t deadlineMs = 0;
    std::uint64_t nextSendMs = 0;
};

class CaptureCompletionQueue {
public:
    bool push(CaptureCompletionNotice notice)
    {
        if (queue_.size() >= 16) { return false; }
        queue_.push_back(std::move(notice));
        return true;
    }
    bool next(std::uint64_t now, CaptureCompletionNotice& output)
    {
        purge(now);
        for (auto& notice : queue_) {
            if (notice.nextSendMs <= now) {
                output = notice;
                notice.nextSendMs = now + 500;
                return true;
            }
        }
        return false;
    }
    void purge(std::uint64_t now)
    {
        for (auto it = queue_.begin(); it != queue_.end();) {
            if (it->deadlineMs <= now) { it = queue_.erase(it); } else { ++it; }
        }
    }
    bool acknowledge(const std::string& id)
    {
        for (auto it = queue_.begin(); it != queue_.end(); ++it) {
            if (it->captureId == id) { queue_.erase(it); return true; }
        }
        return false;
    }
    std::size_t size() const { return queue_.size(); }
private:
    std::deque<CaptureCompletionNotice> queue_;
};

} // namespace stackchan::bridge_client

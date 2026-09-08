#pragma once

#include <deque>
#include <functional>
#include <mutex>
#include <utility>

namespace stackchan::local {

class LocalTasks {
public:
    bool schedule(std::function<void()> task)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!task || tasks_.size() >= 8) { return false; }
        tasks_.push_back(std::move(task));
        return true;
    }

    void runOne()
    {
        std::function<void()> task;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (tasks_.empty()) { return; }
            task = std::move(tasks_.front());
            tasks_.pop_front();
        }
        task();
    }

private:
    std::mutex mutex_;
    std::deque<std::function<void()>> tasks_;
};

}  // namespace stackchan::local

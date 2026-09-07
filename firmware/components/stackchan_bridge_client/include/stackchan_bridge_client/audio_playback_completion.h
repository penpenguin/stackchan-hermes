/*
 * SPDX-FileCopyrightText: 2026 OpenAI
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

#include <cstdint>

namespace stackchan::bridge_client {

class AudioPlaybackCompletion {
public:
    using DecodeGeneration = std::uint64_t;

    DecodeGeneration beginDecode()
    {
        decodeInFlight_ = true;
        return decodeGeneration_;
    }

    bool finishDecode(DecodeGeneration generation)
    {
        decodeInFlight_ = false;
        return generation == decodeGeneration_;
    }

    void invalidateDecode()
    {
        ++decodeGeneration_;
    }

    void beginOutput()
    {
        outputInFlight_ = true;
    }

    void finishOutput()
    {
        outputInFlight_ = false;
    }

    bool isIdle(bool decodeQueueEmpty, bool playbackQueueEmpty) const
    {
        return decodeQueueEmpty && playbackQueueEmpty && !decodeInFlight_
            && !outputInFlight_;
    }

private:
    DecodeGeneration decodeGeneration_ = 0;
    bool decodeInFlight_ = false;
    bool outputInFlight_ = false;
};

}  // namespace stackchan::bridge_client

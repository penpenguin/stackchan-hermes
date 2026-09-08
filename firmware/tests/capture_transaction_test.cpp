#include <cassert>
#include <stackchan_bridge_client/capture_transaction.h>
#include <stackchan_bridge_client/command.h>

using namespace stackchan::bridge_client;

int main()
{
    Command command;
    assert(parseCommandJson(R"({"v":1,"type":"command","message_id":"11111111-1111-4111-8111-111111111111","request_id":"22222222-2222-4222-8222-222222222222","sent_at_ms":0,"payload":{"name":"camera.capture","args":{"capture_id":"33333333-3333-4333-8333-333333333333","quality":80,"timeout_ms":10000}}})", command) == CommandParseError::None);
    CaptureDeadline deadline(100, 10000);
    assert(deadline.remaining(101) == 9999);
    deadline.constrain(200, 9400);
    assert(deadline.remaining(500) == 9100);
    deadline.constrain(1000, 10000);
    assert(deadline.remaining(500) == 9100);
    assert(deadline.operationDeadline(500) == 3500);
    assert(deadline.operationDeadline(8500) == 8600);
    assert(deadline.remaining(9600) == 0);
    for (int status : {401, 403, 404, 409, 410, 413, 422, 301, 501, 505})
        assert(classifyCaptureUpload(status) == UploadDisposition::Permanent);
    for (int status : {-1, 408, 500, 502, 503, 504})
        assert(classifyCaptureUpload(status) == UploadDisposition::Retryable);
    assert(classifyCaptureUpload(201) == UploadDisposition::Succeeded);
    assert(captureRetryDelay(429, "2", 1, 2500) == 2000);
    assert(captureRetryDelay(429, "2", 1, 2000) == -1);
    assert(captureRetryDelay(429, "", 1, 10000) == -1);
    assert(captureRetryDelay(404, "", 1, 10000) == -1);
    assert(captureRetryDelay(-1, "", 3, 10000) == -1);
    CaptureCompletionQueue queue;
    CaptureCompletionNotice notice;
    notice.captureId = "first";
    notice.deadlineMs = 1000;
    assert(queue.push(notice));
    CaptureCompletionNotice out;
    assert(queue.next(0, out) && out.captureId == "first");
    assert(!queue.next(499, out));
    assert(queue.next(500, out));
    assert(queue.acknowledge("first"));
    assert(!queue.next(600, out));
    for (int i = 0; i < 16; ++i) { notice.captureId = std::to_string(i); assert(queue.push(notice)); }
    assert(!queue.push(notice));
    assert(!queue.next(1000, out));
    assert(queue.size() == 0);
}

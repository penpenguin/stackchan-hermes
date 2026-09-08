#include "platform.h"
#include <esp_tcp.h>
#include <esp_ssl.h>
#include <cassert>
#include <memory>
int main() {
    for (bool secure : {false, true}) {
        camera_fake::reset();
        camera_fake::failTask = true;
        std::unique_ptr<Tcp> connection = secure ? std::unique_ptr<Tcp>(new EspSsl) : std::unique_ptr<Tcp>(new EspTcp);
        assert(!connection->Connect("127.0.0.1", 80));
        assert(connection->GetLastError() == ENOMEM);
        assert(camera_fake::liveSockets == 0);
        connection.reset();
        assert(camera_fake::waits == 0);
    }
}

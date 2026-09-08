#include <wifi_board.h>
#include <cassert>

class TestBoard : public WifiBoard {
public:
    bool timerActive() const { return connect_timer_->active; }
    void fireTimeout() { connect_timer_->fire(); }
};

int main()
{
    auto& wifi = WifiManager::GetInstance();
    {
        TestBoard board;
        board.StartNetwork();
        board.EnterWifiConfigMode();
        assert(wifi.ap);
        board.ExitWifiConfigMode();
        assert(!wifi.ap && !board.IsInWifiConfigMode() && !wifi.station);
        assert(!board.timerActive());
        const int starts = wifi.apStarts;
        board.fireTimeout(); // A queued timeout must not reopen a dismissed hotspot.
        board.ExitWifiConfigMode();
        assert(!wifi.ap && wifi.apStarts == starts);

        board.EnterWifiConfigMode();
        assert(wifi.ap); // Setup can be entered again explicitly.
        board.ExitWifiConfigMode();
        assert(!wifi.ap);
    }
    wifi.reset();
    {
        SsidManager::GetInstance().ssids = {"saved-network"};
        TestBoard board;
        board.StartNetwork();
        board.EnterWifiConfigMode();
        board.ExitWifiConfigMode();
        assert(!wifi.ap && wifi.station && !board.timerActive());
        board.fireTimeout();
        assert(!wifi.ap && wifi.station);
        assert(SsidManager::GetInstance().ssids.size() == 1);

        board.EnterWifiConfigMode();
        wifi.StopConfigAp(); // Web submission still starts a connection attempt.
        assert(wifi.station && board.timerActive());
        board.fireTimeout(); // While setup is open, a failed connection can retry via AP.
        assert(wifi.ap);

        wifi.StopConfigAp();
        board.ExitWifiConfigMode(); // Done while the submitted connection is pending.
        assert(wifi.station && !board.timerActive() && !wifi.ap);
        wifi.connected = true;
        wifi.notify(WifiEvent::Connected);
        const int stationStarts = wifi.stationStarts;
        board.ExitWifiConfigMode(); // Closing after success preserves the station.
        assert(wifi.IsConnected() && wifi.stationStarts == stationStarts);
    }
    wifi.reset();
    {
        SsidManager::GetInstance().ssids = {"saved-network"};
        TestBoard board;
        board.StartNetwork();
        // Exit after a running timeout checked its flag, just before AP startup.
        wifi.beforeApStart = [&]() { board.ExitWifiConfigMode(); };
        board.fireTimeout();
        assert(!wifi.ap && wifi.station && !board.timerActive());

        board.EnterWifiConfigMode();
        wifi.StopConfigAp();
        // Exit just before that timeout stops the pending station connection.
        wifi.beforeStationStop = [&]() { board.ExitWifiConfigMode(); };
        board.fireTimeout();
        assert(!wifi.ap && wifi.station && !board.timerActive());
    }
    wifi.reset();
}

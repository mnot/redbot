import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from redbot.daemon import RedBotServer


def stub_server():
    """
    A stand-in for RedBotServer carrying just what watchdog_ping() touches, so
    the test doesn't have to build a whole server (config, sockets, signal
    handlers) to exercise a three-line method.
    """
    # watchdog_ping is what the method reschedules; it's never called through
    # the stub, since the tests invoke the real method explicitly.
    return SimpleNamespace(watchdog_freq=3, console=MagicMock(), watchdog_ping=MagicMock())


class TestWatchdogPing(unittest.TestCase):
    def test_reschedules_after_successful_notify(self):
        server = stub_server()
        with (
            patch("redbot.daemon.SYSTEMD_NOTIFIER") as notifier,
            patch("redbot.daemon.SYSTEMD_NOTIFICATION"),
            patch("redbot.daemon.thor.schedule") as schedule,
        ):
            RedBotServer.watchdog_ping(server)
        self.assertEqual(notifier.call_count, 1)
        schedule.assert_called_once_with(3, server.watchdog_ping)

    def test_reschedules_and_logs_when_notify_raises(self):
        # A failing notify must not end the ping chain: systemd would kill us
        # WatchdogSec later, and thor's scheduler doesn't catch this for us.
        server = stub_server()
        with (
            patch("redbot.daemon.SYSTEMD_NOTIFIER", side_effect=OSError("boom")),
            patch("redbot.daemon.SYSTEMD_NOTIFICATION"),
            patch("redbot.daemon.thor.schedule") as schedule,
        ):
            RedBotServer.watchdog_ping(server)
        schedule.assert_called_once_with(3, server.watchdog_ping)
        self.assertEqual(server.console.call_count, 1)
        self.assertIn("Watchdog notify failed", server.console.call_args[0][0])

    def test_does_nothing_without_systemd(self):
        server = stub_server()
        with (
            patch("redbot.daemon.SYSTEMD_NOTIFIER", None),
            patch("redbot.daemon.SYSTEMD_NOTIFICATION", None),
            patch("redbot.daemon.thor.schedule") as schedule,
        ):
            RedBotServer.watchdog_ping(server)
        schedule.assert_not_called()


if __name__ == "__main__":
    unittest.main()

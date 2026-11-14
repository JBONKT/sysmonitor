"""Unit tests for SystemMonitor core functions.

Covers metric collection, alert thresholds (matching observed disk warnings/
criticals from live runs), history recording, and file persistence.
"""

from __future__ import annotations

import json
import sys
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# Project root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from monitor import SystemMonitor  # noqa: E402

# psutil-like namedtuples
_Svmem = namedtuple(
    "svmem",
    "total available percent used free active inactive buffers cached shared",
)
_Sdiskusage = namedtuple("sdiskusage", "total used free percent")
_Sdiskpart = namedtuple("sdiskpart", "device mountpoint fstype opts")
_Snetio = namedtuple(
    "snetio",
    "bytes_sent bytes_recv packets_sent packets_recv errin errout dropin dropout",
)
_Scpufreq = namedtuple("scpufreq", "current min max")


def _mem(total=8 * 1024**3, used=4 * 1024**3, percent=50.0, available=None):
    free = total - used
    if available is None:
        available = free
    return _Svmem(
        total=total,
        available=available,
        percent=percent,
        used=used,
        free=free,
        active=0,
        inactive=0,
        buffers=0,
        cached=0,
        shared=0,
    )


def _disk(total=100 * 1024**2, used=50 * 1024**2, percent=50.0):
    free = total - used
    return _Sdiskusage(total=total, used=used, free=free, percent=percent)


def _part(device="/dev/disk0s1", mount="/"):
    return _Sdiskpart(device=device, mountpoint=mount, fstype="apfs", opts="rw")


def _net(rx=1000, tx=2000):
    return _Snetio(tx, rx, 0, 0, 0, 0, 0, 0)


class TestGetCpuPercent(unittest.TestCase):
    def setUp(self):
        self.monitor = SystemMonitor()

    @patch("monitor.psutil.cpu_percent", return_value=42.5)
    def test_returns_psutil_value(self, mock_cpu):
        self.assertEqual(self.monitor.get_cpu_percent(), 42.5)
        mock_cpu.assert_called_once_with(interval=0.1)


class TestGetCpuLoad(unittest.TestCase):
    def setUp(self):
        self.monitor = SystemMonitor()

    @patch("monitor.psutil.getloadavg", return_value=(2.0, 1.5, 1.0))
    @patch("monitor.psutil.cpu_count", return_value=4)
    def test_normalizes_load_to_percent(self, mock_count, mock_load):
        # (2.0 / 4) * 100 = 50.0
        self.assertEqual(self.monitor.get_cpu_load(), 50.0)

    @patch("monitor.psutil.getloadavg", return_value=(1.0, 0.0, 0.0))
    @patch("monitor.psutil.cpu_count", return_value=None)
    def test_falls_back_when_cpu_count_is_none(self, mock_count, mock_load):
        # cpu_count or 1 → 1; (1.0 / 1) * 100
        self.assertEqual(self.monitor.get_cpu_load(), 100.0)


class TestGetMemoryInfo(unittest.TestCase):
    def setUp(self):
        self.monitor = SystemMonitor()

    @patch(
        "monitor.psutil.virtual_memory",
        return_value=_mem(total=1024 * 1024 * 1024, used=512 * 1024 * 1024, percent=50.0),
    )
    def test_converts_bytes_to_mb(self, _mock_mem):
        info = self.monitor.get_memory_info()
        self.assertEqual(info["total"], 1024.0)
        self.assertEqual(info["used"], 512.0)
        self.assertEqual(info["percent"], 50.0)
        self.assertIn("free", info)
        self.assertIn("available", info)


class TestGetDiskInfo(unittest.TestCase):
    def setUp(self):
        self.monitor = SystemMonitor()

    @patch("monitor.psutil.disk_usage")
    @patch("monitor.psutil.disk_partitions")
    def test_maps_partitions_to_usage(self, mock_parts, mock_usage):
        mock_parts.return_value = [
            _part("/dev/disk3s5", "/System/Volumes/Data"),
            _part("/dev/disk5s1", "/Volumes/Backup"),
        ]
        mock_usage.side_effect = [
            _disk(percent=88.3),  # warning band from live run
            _disk(percent=99.7),  # critical band from live run
        ]
        info = self.monitor.get_disk_info()
        self.assertEqual(info["/dev/disk3s5"]["percent"], 88.3)
        self.assertEqual(info["/dev/disk3s5"]["mount"], "/System/Volumes/Data")
        self.assertEqual(info["/dev/disk5s1"]["percent"], 99.7)
        self.assertEqual(info["/dev/disk5s1"]["available"], info["/dev/disk5s1"]["free"])
        mock_parts.assert_called_once_with(all=False)

    @patch("monitor.psutil.disk_usage", side_effect=PermissionError("denied"))
    @patch("monitor.psutil.disk_partitions", return_value=[_part()])
    def test_skips_unreadable_partitions(self, _parts, _usage):
        self.assertEqual(self.monitor.get_disk_info(), {})


class TestGetNetworkIo(unittest.TestCase):
    def setUp(self):
        self.monitor = SystemMonitor()

    @patch("monitor.psutil.net_io_counters", return_value=_net(rx=111, tx=222))
    def test_returns_counters(self, mock_net):
        io = self.monitor.get_network_io()
        self.assertEqual(io.bytes_recv, 111)
        self.assertEqual(io.bytes_sent, 222)


class TestGetSystemInfo(unittest.TestCase):
    def setUp(self):
        self.monitor = SystemMonitor()

    @patch("monitor.psutil.virtual_memory", return_value=_mem(total=2 * 1024**3, available=1 * 1024**3))
    @patch("monitor.psutil.cpu_count", return_value=8)
    @patch("monitor.psutil.boot_time", return_value=1_700_000_000.0)
    @patch("monitor.psutil.cpu_freq", return_value=_Scpufreq(2400.0, 800.0, 3200.0))
    @patch("socket.gethostname", return_value="test-host")
    def test_collects_system_fields(self, *_mocks):
        info = self.monitor.get_system_info()
        self.assertEqual(info["hostname"], "test-host")
        self.assertEqual(info["uptime"], 1_700_000_000.0)
        self.assertEqual(info["cpu_count"], 8)
        self.assertEqual(info["cpu_freq"]["current"], 2400.0)
        self.assertEqual(info["memory_total"], 2048.0)

    @patch("monitor.psutil.virtual_memory", return_value=_mem())
    @patch("monitor.psutil.cpu_count", return_value=4)
    @patch("monitor.psutil.boot_time", return_value=100.0)
    @patch("monitor.psutil.cpu_freq", side_effect=SystemError("invalid CPU frequency data"))
    @patch("socket.gethostname", return_value="host")
    def test_cpu_freq_failure_yields_empty_dict(self, *_mocks):
        info = self.monitor.get_system_info()
        self.assertEqual(info["cpu_freq"], {})


class TestCheckAlerts(unittest.TestCase):
    """Thresholds from config; scenarios aligned with live monitor output."""

    def setUp(self):
        self.monitor = SystemMonitor()

    def test_no_alerts_when_below_warning(self):
        with (
            patch.object(self.monitor, "get_cpu_percent", return_value=10.0),
            patch.object(self.monitor, "get_memory_info", return_value={"percent": 20.0}),
            patch.object(self.monitor, "get_disk_info", return_value={}),
        ):
            self.assertEqual(self.monitor.check_alerts(), [])

    def test_cpu_warning_and_critical(self):
        with (
            patch.object(self.monitor, "get_memory_info", return_value={"percent": 10.0}),
            patch.object(self.monitor, "get_disk_info", return_value={}),
        ):
            with patch.object(self.monitor, "get_cpu_percent", return_value=config.CPU_THRESHOLD_WARNING):
                alerts = self.monitor.check_alerts()
                self.assertEqual(len(alerts), 1)
                self.assertEqual(alerts[0]["type"], "CPU_WARNING")
                self.assertEqual(alerts[0]["severity"], "warning")
                self.assertEqual(alerts[0]["threshold"], config.CPU_THRESHOLD_WARNING)

            with patch.object(self.monitor, "get_cpu_percent", return_value=config.CPU_THRESHOLD_CRITICAL):
                alerts = self.monitor.check_alerts()
                self.assertEqual(alerts[0]["type"], "CPU_CRITICAL")
                self.assertEqual(alerts[0]["severity"], "critical")

    def test_memory_warning_and_critical(self):
        with (
            patch.object(self.monitor, "get_cpu_percent", return_value=1.0),
            patch.object(self.monitor, "get_disk_info", return_value={}),
        ):
            with patch.object(
                self.monitor,
                "get_memory_info",
                return_value={"percent": float(config.MEMORY_THRESHOLD_WARNING)},
            ):
                self.assertEqual(self.monitor.check_alerts()[0]["type"], "MEMORY_WARNING")

            with patch.object(
                self.monitor,
                "get_memory_info",
                return_value={"percent": float(config.MEMORY_THRESHOLD_CRITICAL)},
            ):
                self.assertEqual(self.monitor.check_alerts()[0]["type"], "MEMORY_CRITICAL")

    def test_disk_alerts_match_live_run_levels(self):
        """Reproduce monitor output: 88.3% warning, 99.7% critical."""
        disks = {
            "/dev/disk3s5": {
                "mount": "/System/Volumes/Data",
                "percent": 88.3,
                "total": 0,
                "used": 0,
                "free": 0,
                "available": 0,
            },
            "/dev/disk5s1": {
                "mount": "/Volumes/Backup",
                "percent": 99.7,
                "total": 0,
                "used": 0,
                "free": 0,
                "available": 0,
            },
        }
        with (
            patch.object(self.monitor, "get_cpu_percent", return_value=5.0),
            patch.object(self.monitor, "get_memory_info", return_value={"percent": 50.0}),
            patch.object(self.monitor, "get_disk_info", return_value=disks),
        ):
            alerts = self.monitor.check_alerts()
            types = {a["type"] for a in alerts}
            self.assertIn("DISK_WARNING", types)
            self.assertIn("DISK_CRITICAL", types)
            by_disk = {a["disk"]: a for a in alerts}
            self.assertEqual(by_disk["/dev/disk3s5"]["severity"], "warning")
            self.assertIn("88.3%", by_disk["/dev/disk3s5"]["message"])
            self.assertEqual(by_disk["/dev/disk5s1"]["severity"], "critical")
            self.assertIn("99.7%", by_disk["/dev/disk5s1"]["message"])
            self.assertEqual(by_disk["/dev/disk5s1"]["threshold"], config.DISK_THRESHOLD_CRITICAL)

    def test_critical_takes_precedence_over_warning_for_cpu(self):
        with (
            patch.object(self.monitor, "get_cpu_percent", return_value=95.0),
            patch.object(self.monitor, "get_memory_info", return_value={"percent": 10.0}),
            patch.object(self.monitor, "get_disk_info", return_value={}),
        ):
            alerts = self.monitor.check_alerts()
            self.assertEqual(len(alerts), 1)
            self.assertEqual(alerts[0]["type"], "CPU_CRITICAL")


class TestRecordAndPersist(unittest.TestCase):
    def setUp(self):
        self.monitor = SystemMonitor()

    def test_record_metric_appends_history(self):
        self.monitor.record_metric("cpu_percent", 12.3)
        self.assertEqual(len(self.monitor.metrics_history), 1)
        entry = self.monitor.metrics_history[0]
        self.assertEqual(entry["metric"], "cpu_percent")
        self.assertEqual(entry["value"], 12.3)
        self.assertIn("timestamp", entry)

    def test_metrics_history_maxlen(self):
        for i in range(120):
            self.monitor.record_metric("n", i)
        self.assertEqual(len(self.monitor.metrics_history), 100)
        self.assertEqual(self.monitor.metrics_history[0]["value"], 20)
        self.assertEqual(self.monitor.metrics_history[-1]["value"], 119)

    @patch("monitor.os.makedirs")
    def test_save_metrics_to_file(self, mock_makedirs):
        self.monitor.record_metric("cpu_percent", 1.0)
        m = mock_open()
        with patch("builtins.open", m):
            self.monitor.save_metrics_to_file()
        handle = m()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        line = json.loads(written.strip())
        self.assertEqual(line["metric"], "cpu_percent")
        self.assertEqual(line["value"], 1.0)

    def test_save_alert_to_file(self):
        alert = {
            "type": "DISK_CRITICAL",
            "message": "Disk usage critical on /dev/disk5s1: 99.7%",
            "severity": "critical",
            "value": 99.7,
        }
        m = mock_open()
        with patch("builtins.open", m):
            self.monitor.save_alert_to_file(alert)
        handle = m()
        written = handle.write.call_args[0][0]
        self.assertEqual(json.loads(written), alert)


class TestLifecycle(unittest.TestCase):
    def test_stop_clears_running_flag(self):
        mon = SystemMonitor()
        self.assertTrue(mon.running)
        mon.stop()
        self.assertFalse(mon.running)


if __name__ == "__main__":
    unittest.main()

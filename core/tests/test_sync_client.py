import pytest

from netra_core import paths
from netra_core.dossier import crypto
from netra_core.persistence import queue_db
from netra_core.pipeline import run_demo_scan
from netra_core.sync import client


@pytest.fixture(autouse=True)
def data_dir(tmp_path):
    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    client.set_gateway(None)
    yield
    client.set_gateway(None)
    queue_db.reset()
    paths.set_data_dir(None)


class FakeTransport:
    def __init__(self, scripted=()):
        self.scripted = list(scripted)     # [(status, body)] | Exception
        self.calls = []

    def post(self, url, payload, headers=None, timeout=10.0):
        self.calls.append((url, payload, headers))
        step = self.scripted.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _two_scans():
    return [run_demo_scan(dossier=True)["scan_id"],
            run_demo_scan(label={"net_qty": "Net Quantity: 200 gms",
                                 "mrp": "MRP Rs 10.00"},
                          dossier=True)["scan_id"]]


def test_ping_reports_sync():
    from netra_core.bridge.schema import ping_payload
    assert ping_payload()["capabilities"]["sync"] is True


def test_envelope_shape_and_privacy():
    scan_id = run_demo_scan(dossier=True)["scan_id"]
    row = queue_db.get_db().get_scan(scan_id)
    env = client.envelope_from_row(row)
    assert env["kind"] == "netra.scan.v1"
    assert env["verdict"] == "VIOLATION"
    assert env["result"]["summary"]["total"] == 11
    assert "dossier_path" not in env                     # never leaves device
    assert env["dossier_sha256"] == row["dossier_sha256"]


def test_sync_once_marks_rows_synced():
    _two_scans()
    t = FakeTransport([(200, {"accepted": True, "duplicate": False})] * 2)
    s = client.SyncClient("http://gw", transport=t).sync_once()
    assert s.synced == 2 and s.failed == 0 and s.remaining == 0
    assert all(url == "http://gw/ingest" for url, _, _ in t.calls)
    assert queue_db.get_db().status()["pending_sync"] == 0


def test_duplicate_ingest_counts_as_synced():
    run_demo_scan(dossier=True)
    t = FakeTransport([(200, {"accepted": True, "duplicate": True})])
    s = client.SyncClient("http://gw", transport=t).sync_once()
    assert s.synced == 1 and s.offline is False


def test_validation_error_marks_failed():
    run_demo_scan(dossier=True)
    t = FakeTransport([(422, {"detail": "verdict must be PASS or VIOLATION"})])
    s = client.SyncClient("http://gw", transport=t).sync_once()
    assert s.failed == 1 and s.remaining == 0
    row = queue_db.get_db().get_scan(t.calls[0][1]["scan_id"])
    assert row["sync_state"] == "failed"
    assert "422" in row["last_error"] and row["attempts"] == 1


def test_offline_keeps_rows_pending():
    run_demo_scan(dossier=True)
    t = FakeTransport([OSError("connection refused")])
    s = client.SyncClient("http://gw", transport=t).sync_once()
    assert s.offline and s.deferred == 1 and s.remaining == 1
    row = queue_db.get_db().get_scan(t.calls[0][1]["scan_id"])
    assert row["sync_state"] == "pending" and row["attempts"] == 1


def test_server_error_defers_and_stops_batch():
    _two_scans()
    t = FakeTransport([(503, {})])
    s = client.SyncClient("http://gw", transport=t).sync_once()
    assert s.deferred == 1 and s.synced == 0 and s.remaining == 2
    assert len(t.calls) == 1                     # unhealthy gateway: stop


def test_sync_now_without_gateway():
    run_demo_scan(dossier=True)
    out = client.sync_now()
    assert out["attempted"] == 0 and out["error"]
    assert out["remaining"] == 1


def test_sync_now_round_trip_with_token():
    run_demo_scan(dossier=True)
    client.set_gateway("http://gw", token="secret")
    t = FakeTransport([(200, {"accepted": True})])
    out = client.sync_now(transport=t)
    assert out["synced"] == 1 and out["error"] is None
    url, payload, headers = t.calls[0]
    assert url == "http://gw/ingest"
    assert headers["Authorization"] == "Bearer secret"
    assert payload["kind"] == "netra.scan.v1"

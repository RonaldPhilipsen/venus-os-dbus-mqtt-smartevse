import logging

from smartevse.controller import Controller
from smartevse.state import EvseState


def make(mode=1):
    sent, stored = [], []
    c = Controller(lambda n, p: sent.append((n, p)), stored.append, mode, 60,
                   logging.getLogger("t"))
    return c, sent, stored


def live(mode="Smart"):
    s = EvseState(online=True, mode=mode)
    s.last_message = 100.0
    return s


def test_mode_write_sends_and_stores():
    c, sent, stored = make(mode=1)
    assert c.on_mode_write(0, live("Solar"), now=100)
    assert sent == [("Mode", "Smart")] and stored == [0] and c.mode == 0


def test_scheduled_rejected():
    c, sent, _ = make()
    assert not c.on_mode_write(2, live(), now=100) and sent == []


def test_mode_write_in_pause_is_stored_not_sent():
    c, sent, stored = make(mode=0)
    assert c.on_mode_write(1, live("Pause"), now=100)
    assert sent == [] and stored == [1]
    assert c.on_start_stop_write(1, live("Pause"), now=101)
    assert sent == [("Mode", "Solar")]


def test_stop_sends_pause():
    c, sent, _ = make()
    assert c.on_start_stop_write(0, live("Solar"), now=100)
    assert sent == [("Mode", "Pause")]


def test_start_stop_rejects_other_values():
    c, sent, _ = make()
    assert not c.on_start_stop_write(2, live(), now=100) and sent == []


def test_set_current():
    c, sent, _ = make(mode=0)
    assert c.on_set_current_write(8.3, live("Smart"), now=100)
    assert sent == [("CurrentOverride", "83")]
    c2, sent2, _ = make(mode=1)
    assert not c2.on_set_current_write(10, live("Solar"), now=100)
    assert sent2 == []


def test_set_current_limits():
    c, sent, _ = make(mode=0)
    s = live()
    s.max_current_da = 160
    assert not c.on_set_current_write(-1, s, now=100)
    assert not c.on_set_current_write(16.1, s, now=100)
    assert c.on_set_current_write(0, s, now=100)
    assert sent == [("CurrentOverride", "0")]


def test_writes_rejected_when_offline():
    c, sent, _ = make()
    stale = live()
    stale.last_message = 0.0
    assert not c.on_mode_write(0, stale, now=100)
    assert not c.on_start_stop_write(1, EvseState(online=False), now=100)
    assert not c.on_set_current_write(5, stale, now=100)
    assert sent == []


def test_mismatch_logs_warning_once(caplog):
    c, _, _ = make(mode=1)
    c.on_mode_write(0, live("Solar"), now=100)
    c.on_mode_report("Solar", now=105)
    assert c.mode == 0  # waiting for confirmation
    c.check_pending(now=111)
    c.check_pending(now=120)
    assert sum("did not" in r.message for r in caplog.records) == 1
    assert c.mode == 1  # follows the latest report after the timeout


def test_matching_report_clears_wait(caplog):
    c, _, stored = make(mode=1)
    c.on_mode_write(0, live("Solar"), now=100)
    c.on_mode_report("Smart", now=102)
    c.check_pending(now=120)
    assert not caplog.records and c.mode == 0 and stored == [0]


def test_report_follows_evse_when_idle():
    c, _, stored = make(mode=0)
    c.on_mode_report("Solar", now=100)
    assert c.mode == 1 and stored == [1]
    c.on_mode_report("Pause", now=101)
    c.on_mode_report("Off", now=102)
    assert c.mode == 1 and stored == [1]
    c.on_mode_report("Normal", now=103)
    assert c.mode == 0


def test_stop_waits_for_pause():
    c, _, _ = make(mode=1)
    c.on_start_stop_write(0, live("Solar"), now=100)
    c.on_mode_report("Solar", now=103)
    assert c.mode == 1
    c.on_mode_report("Pause", now=104)
    c.check_pending(now=120)

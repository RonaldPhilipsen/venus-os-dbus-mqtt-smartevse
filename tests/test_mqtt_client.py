import os
from dataclasses import replace

import pytest

from smartevse.config import load_config
from smartevse.mqtt_client import SmartEvseMqtt, topic_suffix

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "config.sample.ini")


class FakeMsg:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


class FakeClient:
    def __init__(self):
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None
        self.subscribed = []
        self.published = []
        self.calls = []
        self.credentials = None
        self.reconnect = None

    def username_pw_set(self, username, password=None):
        self.credentials = (username, password)

    def reconnect_delay_set(self, min_delay=1, max_delay=120):
        self.reconnect = (min_delay, max_delay)

    def connect_async(self, host, port=1883, keepalive=60):
        self.calls.append(("connect_async", host, port))

    def loop_start(self):
        self.calls.append(("loop_start",))

    def subscribe(self, topic, qos=0):
        self.subscribed.append((topic, qos))

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))

    def fire_connect(self, rc=0):
        self.on_connect(self, None, {}, rc)

    def fire_connect_v2(self, rc=0):
        self.on_connect(self, None, {}, rc, None)

    def fire_disconnect(self, rc=0):
        self.on_disconnect(self, None, rc)

    def fire_disconnect_v2(self, rc=0):
        self.on_disconnect(self, None, {}, rc, None)

    def fire_message(self, topic, payload):
        self.on_message(self, None, FakeMsg(topic, payload))


class Setup:
    def __init__(self, cfg=None):
        self.cfg = cfg or load_config(SAMPLE)
        self.fake = FakeClient()
        self.msgs, self.links, self.scheduled = [], [], 0
        self.m = SmartEvseMqtt(
            self.cfg, lambda s, p: self.msgs.append((s, p)),
            self.links.append, self.run_now, client_factory=lambda: self.fake)

    def run_now(self, fn, *a):
        self.scheduled += 1
        fn(*a)


@pytest.fixture
def s():
    return Setup()


def test_topic_suffix():
    assert topic_suffix("SmartEVSE/1", "SmartEVSE/1/State") == "/State"
    assert topic_suffix("SmartEVSE/1", "SmartEVSE/12/State") is None
    assert topic_suffix("SmartEVSE/1", "SmartEVSE/1") is None


def test_start_does_not_raise_and_subscribes_on_connect(s):
    s.m.start()
    assert ("loop_start",) in s.fake.calls
    assert s.fake.calls[0][0] == "connect_async"
    assert s.fake.reconnect == (1, 60)
    s.fake.fire_connect(rc=0)
    assert s.fake.subscribed == [("SmartEVSE/51446/#", 1)] and s.links == [True]


def test_connect_v2_signature_and_reason_code_object(s):
    class RC:
        value = 0
        is_failure = False
    s.m.start()
    s.fake.fire_connect_v2(rc=RC())
    assert s.links == [True]


def test_failed_connect_is_not_a_link(s):
    s.m.start()
    s.fake.fire_connect(rc=5)
    assert s.links == [] and s.fake.subscribed == []
    s.m.publish_set("Mode", "Smart")
    assert s.fake.published == []


def test_failed_connect_reason_code_object(s):
    class RC:
        value = 135
        is_failure = True
    s.m.start()
    s.fake.fire_connect_v2(rc=RC())
    assert s.links == []


def test_credentials_only_when_username_set(s):
    s.m.start()
    assert s.fake.credentials is None
    cfg = load_config(SAMPLE)
    cfg = replace(cfg, mqtt_username="u", mqtt_password="p")
    t = Setup(cfg)
    t.m.start()
    assert t.fake.credentials == ("u", "p")


def test_publish_set_uses_prefix_qos1_not_retained(s):
    s.m.start()
    s.fake.fire_connect(rc=0)
    s.m.publish_set("Mode", "Smart")
    assert s.fake.published == [("SmartEVSE/51446/Set/Mode", "Smart", 1, False)]


def test_no_publish_while_link_down(s):
    s.m.start()
    s.m.publish_set("Mode", "Smart")
    assert s.fake.published == []


def test_no_publish_after_disconnect(s):
    s.m.start()
    s.fake.fire_connect(rc=0)
    s.fake.fire_disconnect(rc=1)
    s.m.publish_set("Mode", "Smart")
    assert s.fake.published == []


def test_messages_go_through_schedule(s):
    s.m.start()
    s.fake.fire_message("SmartEVSE/51446/State", b"Charging")
    assert s.scheduled == 1 and s.msgs == [("/State", "Charging")]


def test_foreign_topic_ignored_and_bad_utf8_replaced(s):
    s.m.start()
    s.fake.fire_message("SmartEVSE/514460/State", b"x")
    assert s.msgs == []
    s.fake.fire_message("SmartEVSE/51446/Name", b"a\xffb")
    assert s.msgs == [("/Name", "a�b")]


def test_link_false_once_per_lost_link(s):
    s.m.start()
    s.fake.fire_connect(rc=0)
    s.fake.fire_disconnect(rc=1)
    s.fake.fire_disconnect(rc=1)
    assert s.links == [True, False]
    s.fake.fire_connect(rc=0)
    s.fake.fire_disconnect_v2(rc=1)
    assert s.links == [True, False, True, False]


def test_disconnect_without_link_does_not_report(s):
    s.m.start()
    s.fake.fire_disconnect(rc=1)
    assert s.links == []

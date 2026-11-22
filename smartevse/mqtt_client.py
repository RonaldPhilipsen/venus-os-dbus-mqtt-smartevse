"""MQTT adapter. paho callbacks run on paho's thread and only call schedule()."""
import logging
from typing import Any, Callable, Optional

log = logging.getLogger("smartevse.mqtt")


def topic_suffix(prefix: str, topic: str) -> Optional[str]:
    """Return the part of topic after prefix (starts with "/"), or None."""
    if topic.startswith(prefix + "/"):
        return topic[len(prefix):]
    return None


def _default_client_factory() -> Any:
    import paho.mqtt.client as mqtt  # imported here so tests run without paho
    version = getattr(mqtt, "CallbackAPIVersion", None)
    if version is not None:
        return mqtt.Client(version.VERSION2)
    return mqtt.Client()


def _is_success(rc: Any) -> bool:
    if hasattr(rc, "is_failure"):
        return not rc.is_failure
    return rc == 0


class SmartEvseMqtt:
    def __init__(self, cfg, on_message: Callable[[str, str], None],
                 on_link: Callable[[bool], None], schedule: Callable[..., Any],
                 client_factory: Optional[Callable[[], Any]] = None) -> None:
        self._cfg = cfg
        self._prefix = cfg.topic_prefix
        self._on_message = on_message
        self._on_link = on_link
        self._schedule = schedule
        self._connected = False
        self._client = (client_factory or _default_client_factory)()
        self._client.on_connect = self._handle_connect
        self._client.on_disconnect = self._handle_disconnect
        self._client.on_message = self._handle_message

    def start(self) -> None:
        if self._cfg.mqtt_username:
            self._client.username_pw_set(self._cfg.mqtt_username,
                                         self._cfg.mqtt_password)
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.connect_async(self._cfg.mqtt_host, self._cfg.mqtt_port)
        self._client.loop_start()

    def publish_set(self, name: str, payload: str) -> None:
        if not self._connected:
            return
        self._client.publish("%s/Set/%s" % (self._prefix, name), payload,
                             qos=1, retain=False)

    # paho 1.x: (client, userdata, flags, rc)
    # paho 2.x: (client, userdata, flags, reason_code, properties)
    def _handle_connect(self, client, userdata, flags, rc, *args) -> None:
        if not _is_success(rc):
            log.warning("MQTT connect refused: %s", rc)
            return
        self._connected = True
        client.subscribe(self._prefix + "/#", 1)
        log.info("MQTT connected")
        self._schedule(self._on_link, True)

    # paho 1.x: (client, userdata, rc)
    # paho 2.x: (client, userdata, flags, reason_code, properties)
    def _handle_disconnect(self, client, userdata, *args) -> None:
        if not self._connected:
            return
        self._connected = False
        log.warning("MQTT link lost")
        self._schedule(self._on_link, False)

    def _handle_message(self, client, userdata, msg) -> None:
        suffix = topic_suffix(self._prefix, msg.topic)
        if suffix is None:
            return
        payload = msg.payload.decode("utf-8", errors="replace")
        self._schedule(self._on_message, suffix, payload)

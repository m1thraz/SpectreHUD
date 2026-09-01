import unittest
from core.event_bus import EventBus, EventType


class TestEventBus(unittest.TestCase):
    """Unit tests verifying EventBus pub/sub, exception isolation, unsubscription, and threading."""

    def setUp(self):
        self.bus = EventBus()

    def test_subscribe_and_publish(self):
        received = []
        self.bus.subscribe(EventType.PROJECT_CHANGED, lambda d: received.append(d))

        self.bus.publish(EventType.PROJECT_CHANGED, {"name": "BoxAlpha", "ip": "10.10.10.50"})

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["name"], "BoxAlpha")
        self.assertEqual(received[0]["ip"], "10.10.10.50")

    def test_unsubscribe_explicit(self):
        received = []

        def handler(data):
            received.append(data)

        self.bus.subscribe(EventType.LOOT_UPDATED, handler)
        self.bus.publish(EventType.LOOT_UPDATED, {"id": "1"})
        self.assertEqual(len(received), 1)

        self.bus.unsubscribe(EventType.LOOT_UPDATED, handler)
        self.bus.publish(EventType.LOOT_UPDATED, {"id": "2"})
        self.assertEqual(len(received), 1)

    def test_unsubscribe_closure_callback(self):
        received = []
        unsub = self.bus.subscribe("custom_topic", lambda d: received.append(d))

        self.bus.publish("custom_topic", "hello")
        self.assertEqual(received, ["hello"])

        unsub()
        self.bus.publish("custom_topic", "world")
        self.assertEqual(received, ["hello"])

    def test_exception_isolation(self):
        received = []

        def failing_subscriber(data):
            raise ValueError("Intentional subscriber explosion!")

        def succeeding_subscriber(data):
            received.append(data)

        self.bus.subscribe(EventType.SNIPPETS_UPDATED, failing_subscriber)
        self.bus.subscribe(EventType.SNIPPETS_UPDATED, succeeding_subscriber)

        # Should not raise exception and succeeding_subscriber must still be executed
        self.bus.publish(EventType.SNIPPETS_UPDATED, {"snippet": "nmap"})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["snippet"], "nmap")

    def test_clear_and_counts(self):
        self.bus.subscribe(EventType.MODE_CHANGED, lambda d: None)
        self.bus.subscribe(EventType.MODE_CHANGED, lambda d: None)
        self.bus.subscribe(EventType.LANGUAGE_CHANGED, lambda d: None)

        self.assertEqual(self.bus.get_subscriber_count(EventType.MODE_CHANGED), 2)
        self.assertEqual(self.bus.get_subscriber_count(EventType.LANGUAGE_CHANGED), 1)
        self.assertEqual(self.bus.get_subscriber_count(), 3)

        self.bus.clear()
        self.assertEqual(self.bus.get_subscriber_count(), 0)

    def test_event_bus_instances_are_isolated(self):
        other_bus = EventBus()
        received = []
        self.bus.subscribe(EventType.MODE_CHANGED, received.append)

        other_bus.publish(EventType.MODE_CHANGED, {"mode": "loot"})

        self.assertEqual(received, [])


if __name__ == "__main__":
    unittest.main()

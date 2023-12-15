import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from utils.proactive_messaging_utils import (
    calculate_next_schedule_time,
    should_reschedule,
)


class TestProactiveMessaging(unittest.TestCase):
    """
    Test class for proactive messaging functionality.

    Tests the functions related to proactive messaging, including Firestore updates,
    scheduling logic, and task management.
    """

    def setUp(self) -> None:
        """Set up test environment for each test."""
        self.bot_id = "test_bot_id"
        self.proactive_config = {
            "system_prompt": "Test prompt",
            "slack_channel": "test_channel",
            "interval_days": 1.0,
        }
        self.firestore_mock = MagicMock()

    def test_should_reschedule(self) -> None:
        """Test the should_reschedule function for detecting configuration changes."""
        old_config = {"interval_days": 1.0}
        new_config = {"interval_days": 2.0}
        self.assertTrue(should_reschedule(old_config, new_config))

    def test_calculate_next_schedule_time(self) -> None:
        """Test the calculate_next_schedule_time function."""
        interval_days = float(self.proactive_config["interval_days"])
        expected_time = datetime.now() + timedelta(days=interval_days)
        calculated_time = calculate_next_schedule_time(self.proactive_config)
        self.assertTrue(
            expected_time <= calculated_time <= expected_time + timedelta(days=1)
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytz

from config.settings.proactive_messaging_settings import ProactiveMessagingSettings
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
        self.proactive_config = ProactiveMessagingSettings(
            system_prompt="Test prompt",
            slack_channel="test_channel",
            interval_days=1.0,
            enabled=True,
        )
        self.firestore_mock = MagicMock()

    def test_should_reschedule(self) -> None:
        """Test the should_reschedule function for detecting configuration changes."""
        old_config = ProactiveMessagingSettings(interval_days=1.0)
        new_config = ProactiveMessagingSettings(interval_days=2.0)
        self.assertTrue(should_reschedule(old_config, new_config))

    def test_calculate_next_schedule_time(self) -> None:
        """Test the calculate_next_schedule_time function."""
        if self.proactive_config.interval_days is not None:
            interval_days = self.proactive_config.interval_days

            # Use timezone-aware datetime
            expected_time_start = datetime.now(pytz.utc)
            calculated_time = calculate_next_schedule_time(self.proactive_config)
            expected_time_end = datetime.now(pytz.utc) + timedelta(
                days=interval_days * 2
            )

            self.assertTrue(expected_time_start <= calculated_time <= expected_time_end)


if __name__ == "__main__":
    unittest.main()

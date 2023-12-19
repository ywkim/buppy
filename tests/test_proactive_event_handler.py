from __future__ import annotations
import unittest
from unittest.mock import Mock, patch

from google.cloud import firestore
from celery import Celery

import event_handlers.proactive_event_handler as event_handler

class TestProactiveEventHandler(unittest.TestCase):
    def setUp(self):
        self.mock_db = Mock(spec=firestore.Client)
        self.mock_celery_app = Mock(spec=Celery)
        self.event_data = {
            "id": "test_bot_id",
            "oldValue": {"fields": {"proactive_messaging": {"interval_days": 1}}},
            "newValue": {"fields": {"proactive_messaging": {"interval_days": 2}}}
        }

    @patch("event_handlers.proactive_event_handler.schedule_proactive_message")
    def test_process_proactive_event(self, mock_schedule_message):
        """
        Test process_proactive_event function to ensure it correctly processes events and schedules tasks.
        """
        bot_doc_mock = Mock()
        bot_doc_mock.to_dict.return_value = {"proactive_messaging": {"key": "value"}}

        self.mock_db.collection.return_value.document.return_value.get.return_value = bot_doc_mock

        event_handler.process_proactive_event(
            self.mock_db,
            self.mock_celery_app,
            self.event_data
        )

        self.mock_db.collection.assert_called_with("Bots")
        self.mock_db.collection.return_value.document.assert_called_with("test_bot_id")
        mock_schedule_message.assert_called_with(
            self.mock_celery_app,
            self.mock_db.collection.return_value.document.return_value,
            {"key": "value"},
            "test_bot_id"
        )

if __name__ == "__main__":
    unittest.main()

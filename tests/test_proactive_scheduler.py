from __future__ import annotations
import unittest
from unittest.mock import patch, Mock
import json

from flask import Flask
from google.cloud import firestore

# Import the module you're testing
import proactive_scheduler

class TestProactiveScheduler(unittest.TestCase):
    def setUp(self):
        proactive_scheduler.app.testing = True
        self.app = proactive_scheduler.app.test_client()
        self.bot_id = "test_bot_id"
        self.proactive_config = {"config_key": "config_value"}
        self.event_data = {
            "id": self.bot_id,
            "oldValue": {"fields": {"proactive_messaging": self.proactive_config}},
            "newValue": {}
        }

    @patch("proactive_scheduler.db.collection")
    @patch("proactive_scheduler.schedule_proactive_message")
    def test_handle_proactive_event(self, mock_schedule_message, mock_collection):
        """
        Test the handle_proactive_event route to ensure it processes the event and calls schedule_proactive_message correctly.
        """
        # Mock Firestore document reference
        mock_doc_ref = Mock(spec=firestore.DocumentReference)
        mock_collection.return_value.document.return_value = mock_doc_ref

        # Mock Firestore document snapshot
        mock_doc_snapshot = Mock()
        mock_doc_snapshot.to_dict.return_value = {"proactive_messaging": self.proactive_config}
        mock_doc_ref.get.return_value = mock_doc_snapshot

        response = self.app.post("/", data=json.dumps(self.event_data), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        mock_schedule_message.assert_called_once_with(
            proactive_scheduler.celery_app,
            mock_doc_ref,
            self.proactive_config,
            self.bot_id
        )

    # Additional tests can be added here to cover other scenarios and edge cases

if __name__ == "__main__":
    unittest.main()

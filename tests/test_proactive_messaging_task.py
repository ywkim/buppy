from __future__ import annotations
import unittest
from unittest.mock import Mock, patch

from celery import Celery
from google.cloud import firestore
from google.cloud.firestore import DocumentReference

# Import the module you're testing
import celery_tasks.proactive_messaging_task as messaging_task


class TestProactiveMessagingTask(unittest.TestCase):
    def setUp(self):
        # Mocks for Celery and Firestore
        self.mock_celery_app = Mock(spec=Celery)
        self.mock_firestore_client = Mock(spec=firestore.Client)
        self.mock_document_ref = Mock(spec=DocumentReference)
        self.bot_id = "test_bot_id"
        self.proactive_config = {"config_key": "config_value"}

    @patch("celery_tasks.proactive_messaging_task.update_proactive_messaging_settings")
    def test_schedule_proactive_message(self, mock_update_settings):
        """
        Test the schedule_proactive_message function to ensure it calls the update_proactive_messaging_settings function with correct parameters.
        """
        messaging_task.schedule_proactive_message(
            self.mock_celery_app,
            self.mock_document_ref,
            self.proactive_config,
            self.bot_id
        )

        mock_update_settings.assert_called_once_with(
            self.mock_firestore_client.transaction(),
            self.mock_celery_app,
            self.mock_document_ref,
            self.proactive_config,
            self.bot_id
        )

    # Additional tests can be added here to cover other scenarios and edge cases

if __name__ == "__main__":
    unittest.main()

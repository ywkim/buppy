from __future__ import annotations
import unittest
from unittest.mock import Mock, patch, MagicMock

import mockfirestore
from google.cloud.firestore import Transaction, DocumentReference
from celery import Celery

import event_handlers.proactive_event_handler as event_handler

class TestProactiveEventHandler(unittest.TestCase):
    def setUp(self):
        self.mock_db = mockfirestore.MockFirestore()
        self.mock_celery_app = Mock(spec=Celery)
        self.mock_transaction = MagicMock(spec=Transaction)
        self.mock_document_ref = Mock(spec=DocumentReference)
        self.bot_id = "test_bot_id"
        self.task_id = "test_task_id"
        self.proactive_config = {"config_key": "config_value"}
        self.event_data = {
            "id": "test_bot_id",
            "oldValue": {"fields": {"proactive_messaging": {"interval_days": 1}}},
            "newValue": {"fields": {"proactive_messaging": {"interval_days": 2}}}
        }

    def test_update_proactive_messaging_settings(self):
        """
        Test the update_proactive_messaging_settings function to ensure it correctly handles Firestore transactions and updates.
        """
        event_handler.update_proactive_messaging_settings(
            self.mock_db.transaction(),
            self.mock_celery_app,
            self.mock_document_ref,
            self.proactive_config,
            self.bot_id
        )

        # Check if Firestore transaction is initiated
        self.mock_db.transaction.assert_called_once()

        # Check if the Firestore document is updated within a transaction
        self.mock_document_ref.update.assert_called()

    def test_update_task_id_in_firestore(self):
        # Setup mock for Firestore document
        mock_doc_ref = self.mock_db.collection("Bots").document(self.bot_id)

        # Call the function under test
        event_handler.update_task_id_in_firestore(
            self.mock_db, self.bot_id, self.task_id
        )

        # Assert the expected call
        mock_doc_ref.update.assert_called_with(
            {"proactive_messaging.current_task_id": self.task_id}
        )

    def test_process_proactive_event(self):
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

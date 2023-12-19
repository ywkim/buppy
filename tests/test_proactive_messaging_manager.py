from __future__ import annotations
import unittest
from unittest.mock import Mock, patch, MagicMock

import mockfirestore
from google.cloud.firestore import Transaction, DocumentReference
from celery import Celery

# Import the module you're testing
import firestore_managers.proactive_messaging_manager as messaging_manager


class TestProactiveMessagingManager(unittest.TestCase):
    def setUp(self):
        # Mocks for Firestore client and Celery
        self.mock_db_client = mockfirestore.MockFirestore()
        self.mock_celery_app = Mock(spec=Celery)
        self.mock_transaction = MagicMock(spec=Transaction)
        self.mock_document_ref = Mock(spec=DocumentReference)
        self.bot_id = "test_bot_id"
        self.task_id = "test_task_id"
        self.proactive_config = {"config_key": "config_value"}

    def test_update_proactive_messaging_settings(self):
        """
        Test the update_proactive_messaging_settings function to ensure it correctly handles Firestore transactions and updates.
        """
        messaging_manager.update_proactive_messaging_settings(
            self.mock_db_client.transaction(),
            self.mock_celery_app,
            self.mock_document_ref,
            self.proactive_config,
            self.bot_id
        )

        # Check if Firestore transaction is initiated
        self.mock_db_client.transaction.assert_called_once()

        # Check if the Firestore document is updated within a transaction
        self.mock_document_ref.update.assert_called()

    def test_update_task_id_in_firestore(self):
        # Setup mock for Firestore document
        mock_doc_ref = self.mock_db_client.collection("Bots").document(self.bot_id)

        # Call the function under test
        messaging_manager.update_task_id_in_firestore(
            self.mock_db_client, self.bot_id, self.task_id
        )

        # Assert the expected call
        mock_doc_ref.update.assert_called_with(
            {"proactive_messaging.current_task_id": self.task_id}
        )

if __name__ == "__main__":
    unittest.main()

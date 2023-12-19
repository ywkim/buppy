from __future__ import annotations
import unittest
from unittest.mock import Mock, patch, MagicMock

from google.cloud import firestore
from google.cloud.firestore import Transaction, DocumentReference
from celery import Celery

# Import the module you're testing
import firestore_managers.proactive_messaging_manager as messaging_manager


class TestProactiveMessagingManager(unittest.TestCase):
    def setUp(self):
        # Mocks for Firestore client and Celery
        self.mock_db_client = Mock(spec=firestore.Client)
        self.mock_celery_app = Mock(spec=Celery)
        self.mock_transaction = MagicMock(spec=Transaction)
        self.mock_document_ref = Mock(spec=DocumentReference)
        self.bot_id = "test_bot_id"
        self.task_id = "test_task_id"
        self.proactive_config = {"config_key": "config_value"}

    @patch('google.cloud.firestore.Client.transaction')
    def test_update_proactive_messaging_settings(self, mock_transaction):
        """
        Test the update_proactive_messaging_settings function to ensure it correctly handles Firestore transactions and updates.
        """
        mock_transaction.return_value = self.mock_transaction
        messaging_manager.update_proactive_messaging_settings(
            self.mock_db_client,
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
        """
        Test the update_task_id_in_firestore function to ensure it correctly updates the task ID in Firestore.
        """
        messaging_manager.update_task_id_in_firestore(
            self.mock_db_client,
            self.bot_id,
            self.task_id
        )

        # Check if the Firestore document is updated with the new task ID
        self.mock_document_ref.update.assert_called_with(
            {"proactive_messaging.current_task_id": self.task_id}
        )

    # Additional tests can be added here to cover more scenarios and edge cases

if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from celery import Celery
from mockfirestore import MockFirestore

import event_handlers.proactive_event_handler as event_handler
from config.settings.proactive_messaging_settings import ProactiveMessagingSettings
from config.slack_config import SlackAppConfig
from utils.proactive_messaging_utils import ProactiveMessagingContext


class TestProactiveEventHandler(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockFirestore()
        self.mock_celery_app = Mock(spec=Celery)
        self.bot_id = "test_bot_id"
        self.task_id = "test_task_id"
        self.proactive_config = ProactiveMessagingSettings(interval_days=1)
        self.event_data = {
            "id": self.bot_id,
            "oldValue": {"fields": {"proactive_messaging": {"interval_days": 1}}},
            "newValue": {"fields": {"proactive_messaging": {"interval_days": 2}}}
        }
        self.app_config = SlackAppConfig()
        self.app_config.proactive_messaging_settings = self.proactive_config

    def test_update_proactive_messaging_settings(self):
        """
        Test the update_proactive_messaging_settings function to ensure it correctly
        handles Firestore transactions and updates.
        """
        context = ProactiveMessagingContext(
            client=None,
            app_config=self.app_config,
            bot_user_id=self.bot_id
        )

        with self.mock_db.transaction() as transaction:
            event_handler.update_proactive_messaging_settings(
                transaction,
                self.mock_celery_app,
                context,
                self.mock_db.collection("Bots").document(self.bot_id)
            )

        # Fetch updated document and validate changes
        updated_doc = self.mock_db.collection("Bots").document(self.bot_id).get()
        self.assertIsNotNone(updated_doc.to_dict())

    def test_update_task_id_in_firestore(self):
        """
        Test the update_task_id_in_firestore function to ensure it correctly updates
        the task ID in Firestore.
        """
        bot_ref = self.mock_db.collection("Bots").document(self.bot_id)
        bot_ref.set({"proactive_messaging": {}})  # Initialize document

        # Call the function under test
        event_handler.update_task_id_in_firestore(
            self.mock_db, self.bot_id, self.task_id
        )

        updated_doc = bot_ref.get()
        self.assertEqual(updated_doc.to_dict()["proactive_messaging"]["current_task_id"],
                         self.task_id)

    @patch('event_handlers.proactive_event_handler.generate_and_send_proactive_message')
    def test_process_proactive_event(self, mock_schedule_message):
        """
        Test process_proactive_event function to ensure it correctly processes events
        and schedules tasks.
        """
        bot_ref = self.mock_db.collection("Bots").document(self.bot_id)
        bot_ref.set({"proactive_messaging": {"key": "value"}})

        event_handler.process_proactive_event(
            self.mock_db,
            self.mock_celery_app,
            self.event_data
        )

        mock_schedule_message.assert_called_once_with(
            self.mock_celery_app,
            self.mock_db.collection("Bots").document(self.bot_id),
            {"key": "value"},
            self.bot_id
        )

if __name__ == "__main__":
    unittest.main()

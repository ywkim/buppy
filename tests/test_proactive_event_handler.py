from __future__ import annotations

import unittest
from unittest.mock import Mock

from celery import Celery
from mockfirestore import MockFirestore
from slack_sdk.web.async_client import AsyncWebClient

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
        self.app_config = SlackAppConfig()
        self.app_config.proactive_messaging_settings = self.proactive_config

    def test_update_proactive_messaging_settings(self):
        """
        Test the update_proactive_messaging_settings function to ensure it correctly
        handles Firestore transactions and updates.
        """
        client = AsyncWebClient()
        context = ProactiveMessagingContext(
            client=client,
            app_config=self.app_config,
            bot_user_id=self.bot_id
        )

        event_handler.execute_proactive_messaging_update(
            self.mock_db.transaction(),
            self.mock_db.collection("Bots").document(self.bot_id),
            context.app_config.proactive_messaging_settings,
            self.mock_celery_app,
            context,

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

if __name__ == "__main__":
    unittest.main()

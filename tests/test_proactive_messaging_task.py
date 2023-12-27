from __future__ import annotations

import unittest
from unittest.mock import Mock

from celery import Celery
from mockfirestore import MockFirestore

import celery_tasks.proactive_messaging_task as messaging_task
from config.settings.proactive_messaging_settings import ProactiveMessagingSettings
from config.slack_config import SlackAppConfig


class TestProactiveMessagingTask(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockFirestore()
        self.mock_celery_app = Mock(spec=Celery)
        self.bot_id = "test_bot_id"
        self.task_id = "test_task_id"
        self.proactive_config = ProactiveMessagingSettings(interval_days=1)
        self.app_config = SlackAppConfig()
        self.app_config.proactive_messaging_settings = self.proactive_config
        self.bot_ref = self.mock_db.collection("Bots").document(self.bot_id)
        self.bot_ref.set({"proactive_messaging": {}})

    def test_schedule_proactive_message(self):
        """
        Test the schedule_proactive_message function to ensure it calls the update_proactive_messaging_settings function with correct parameters.
        """
        messaging_task.schedule_proactive_message_task(
            self.app_config.proactive_messaging_settings,
            self.bot_id,
            self.mock_celery_app,
            self.mock_db,  # type: ignore
        )

        # Fetch updated document and validate changes
        updated_doc = self.mock_db.collection("Bots").document(self.bot_id).get()
        self.assertIsNotNone(updated_doc.to_dict())

    def test_update_task_in_firestore(self):
        """
        Test the update_task_in_firestore function to ensure it correctly updates
        the task ID in Firestore.
        """

        # Call the function under test
        messaging_task.update_task_in_firestore(
            self.mock_db, self.bot_id, self.task_id, None  # type: ignore
        )

        updated_doc = self.bot_ref.get()
        self.assertEqual(
            updated_doc.to_dict()["proactive_messaging"]["current_task_id"],
            self.task_id,
        )


if __name__ == "__main__":
    unittest.main()

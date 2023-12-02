import unittest
from unittest.mock import Mock, patch

from upload_companion import document_exists, upload_bot_data, upload_companion_data

class TestUploadCompanion(unittest.TestCase):
    """
    Test suite for the upload companion module.

    This class tests the functionality of the upload_companion_data, upload_bot_data,
    and document_exists functions, using mock Firestore clients to ensure independence
    from the actual Firestore service.
    """

    def setUp(self) -> None:
        """
        Set up the test environment.

        Creates a mock Firestore client to be used in the tests.
        """
        self.mock_db = Mock()  # Mock Firestore client object

    def test_upload_companion_data(self) -> None:
        """
        Test the upload_companion_data function.

        Ensures that the function correctly interacts with the Firestore client
        to upload companion data.
        """
        companion_id = "test_companion"
        companion_data = {
            "chat_model": "gpt-4",
            "system_prompt": "You are a helpful assistant.",
        }

        upload_companion_data(self.mock_db, companion_id, companion_data)

        self.mock_db.collection.assert_called_with("Companions")
        self.mock_db.collection().document.assert_called_with(companion_id)
        self.mock_db.collection().document().set.assert_called_with(companion_data)

    def test_upload_bot_data(self) -> None:
        """
        Test the upload_bot_data function.

        Verifies that the function correctly uses the Firestore client to upload bot data.
        """
        bot_id = "test_bot"
        bot_data = {"CompanionId": "test_companion"}

        upload_bot_data(self.mock_db, bot_id, bot_data)

        self.mock_db.collection.assert_called_with("Bots")
        self.mock_db.collection().document.assert_called_with(bot_id)
        self.mock_db.collection().document().set.assert_called_with(bot_data)

    def test_document_exists(self) -> None:
        """
        Test the document_exists function.

        Checks whether the function accurately determines the existence of a document
        in Firestore.
        """
        # Simulate an existing document
        self.mock_db.collection().document().get().exists = True
        self.assertTrue(document_exists(self.mock_db, "Companions", "existing_doc"))

        # Simulate a non-existing document
        self.mock_db.collection().document().get().exists = False
        self.assertFalse(document_exists(self.mock_db, "Companions", "non_existing_doc"))


if __name__ == "__main__":
    unittest.main()

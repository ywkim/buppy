import unittest
from unittest.mock import patch, Mock
from upload_companion import upload_companion_data, upload_bot_data, document_exists

class TestUploadCompanion(unittest.TestCase):
    def setUp(self):
        self.mock_db = Mock()  # Firestore 클라이언트 모의 객체

    def test_upload_companion_data(self):
        """Companion 데이터 업로드 테스트"""
        with patch('main.firestore.Client', return_value=self.mock_db):
            companion_id = "test_companion"
            companion_data = {"chat_model": "gpt-4", "system_prompt": "You are a helpful assistant."}
            upload_companion_data(self.mock_db, companion_id, companion_data)
            self.mock_db.collection.assert_called_with("Companions")
            self.mock_db.collection().document.assert_called_with(companion_id)
            self.mock_db.collection().document().set.assert_called_with(companion_data)

    def test_upload_bot_data(self):
        """Bot 데이터 업로드 테스트"""
        with patch('main.firestore.Client', return_value=self.mock_db):
            bot_id = "test_bot"
            bot_data = {"CompanionId": "test_companion"}
            upload_bot_data(self.mock_db, bot_id, bot_data)
            self.mock_db.collection.assert_called_with("Bots")
            self.mock_db.collection().document.assert_called_with(bot_id)
            self.mock_db.collection().document().set.assert_called_with(bot_data)

    def test_document_exists(self):
        """Firestore 문서 존재 여부 테스트"""
        with patch('main.firestore.Client', return_value=self.mock_db):
            self.mock_db.collection().document().get().exists = True
            self.assertTrue(document_exists(self.mock_db, "Companions", "existing_doc"))
            self.mock_db.collection().document().get().exists = False
            self.assertFalse(document_exists(self.mock_db, "Companions", "non_existing_doc"))

if __name__ == '__main__':
    unittest.main()

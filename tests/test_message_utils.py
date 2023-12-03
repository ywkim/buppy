from __future__ import annotations

import unittest
from unittest.mock import patch

from streamlit_app import format_messages
from utils.message_utils import InvalidRoleError, load_prefix_messages_from_file


class TestMessageUtils(unittest.TestCase):
    def test_format_messages_valid_input(self) -> None:
        """Test format_messages function with valid input data."""
        input_data = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = format_messages(input_data)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].content, "Hello!")
        self.assertEqual(result[1].content, "Hi there!")

    def test_load_prefix_messages_from_file_valid(self) -> None:
        """Test load_prefix_messages_from_file function with a valid file path."""
        valid_file_path = "path/to/valid/prefix_messages.csv"
        # Mocking file reading operation
        with patch(
            "builtins.open",
            new_callable=unittest.mock.mock_open,
            read_data="AI,Hello\nHuman,Hi",
        ) as mock_file:
            result = load_prefix_messages_from_file(valid_file_path)
            mock_file.assert_called_with(valid_file_path, "r", encoding="utf-8")
            self.assertEqual(len(result), 2)

    def test_load_prefix_messages_from_file_invalid_role(self) -> None:
        """Test load_prefix_messages_from_file function with an invalid role in the file."""
        invalid_file_path = "path/to/invalid/prefix_messages.csv"
        # Mocking file reading operation with invalid role
        with patch(
            "builtins.open",
            new_callable=unittest.mock.mock_open,
            read_data="Invalid,Hello",
        ):
            with self.assertRaises(InvalidRoleError):
                load_prefix_messages_from_file(invalid_file_path)

    # Additional tests can be added for other utility functions and components


if __name__ == "__main__":
    unittest.main()

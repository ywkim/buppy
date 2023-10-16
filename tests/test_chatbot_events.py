import unittest

from main import get_valid_emoji_codes, is_valid_emoji_code


class TestChatbotEvents(unittest.TestCase):
    def test_get_valid_emoji_codes(self) -> None:
        """Test get_valid_emoji_codes() function to verify if it correctly extracts and validates the emoji codes."""
        input_string = (
            "I feel happy :smile: but also sad :sad_face: and confused :unknown_emoji:"
        )
        expected_output = ["smile"]
        result = get_valid_emoji_codes(input_string)
        self.assertEqual(result, expected_output)

    def test_get_valid_emoji_codes_no_emojis(self) -> None:
        """Test get_valid_emoji_codes() function when there are no emojis in the input string."""
        input_string = "There are no emojis here."
        expected_output: list[str] = []
        result = get_valid_emoji_codes(input_string)
        self.assertEqual(result, expected_output)

    def test_is_valid_emoji_code(self) -> None:
        """Test is_valid_emoji_code() function to verify if it correctly validates the emoji codes."""
        self.assertTrue(is_valid_emoji_code("smile"))
        self.assertFalse(is_valid_emoji_code("unknown_emoji"))


if __name__ == "__main__":
    unittest.main()

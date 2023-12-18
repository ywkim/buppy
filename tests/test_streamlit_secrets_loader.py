from __future__ import annotations

import unittest
from unittest.mock import patch

from pydantic import BaseModel, ValidationError

from config.loaders.streamlit_loader import load_settings_from_streamlit_secrets


class DummySettings(BaseModel):
    parameter1: str = "default1"
    parameter2: int = 1
    parameter3: bool = False


class TestStreamlitSecretsLoader(unittest.TestCase):
    """Test class for the Streamlit secrets loader functionality."""

    def setUp(self) -> None:
        """Mock the Streamlit secrets."""
        self.mocked_secrets = {
            "Dummy": {"parameter1": "value1", "parameter2": 10, "parameter3": True}
        }

    def get_mocked_secrets(self):
        """Return the current state of the mocked secrets."""
        return self.mocked_secrets

    def test_load_settings_from_valid_section(self):
        """Test loading settings from a valid section of the Streamlit secrets."""
        with patch("streamlit.secrets", self.mocked_secrets):
            loaded_settings = load_settings_from_streamlit_secrets(
                DummySettings, "Dummy"
            )
            self.assertEqual(loaded_settings.parameter1, "value1")
            self.assertEqual(loaded_settings.parameter2, 10)
            self.assertTrue(loaded_settings.parameter3)

    def test_load_settings_from_invalid_section(self):
        """Test loading settings from a non-existent section."""
        with patch("streamlit.secrets", self.mocked_secrets):
            loaded_settings = load_settings_from_streamlit_secrets(
                DummySettings, "NonExistent"
            )
            self.assertIsInstance(loaded_settings, DummySettings)
            self.assertEqual(loaded_settings.parameter1, "default1")
            self.assertEqual(loaded_settings.parameter2, 1)
            self.assertFalse(loaded_settings.parameter3)

    def test_load_settings_with_type_mismatch(self):
        """Test loading settings with a type mismatch."""
        # Modify the secrets for this specific test
        self.mocked_secrets["Dummy"]["parameter2"] = "not a number"
        with patch("streamlit.secrets", self.mocked_secrets):
            with self.assertRaises(ValidationError):
                load_settings_from_streamlit_secrets(DummySettings, "Dummy")


if __name__ == "__main__":
    unittest.main()

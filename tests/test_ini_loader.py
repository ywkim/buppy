from __future__ import annotations

import os
import unittest
from configparser import ConfigParser
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ValidationError

from config.loaders.ini_loader import load_settings_from_ini_section


class DummySettings(BaseModel):
    parameter1: str = "default1"
    parameter2: int = 1
    parameter3: bool = False


class TestIniLoader(unittest.TestCase):
    """Test class for the INI loader functionality."""

    def setUp(self) -> None:
        """Set up a temporary INI file for testing."""
        with NamedTemporaryFile(delete=False, mode="w", suffix=".ini") as temp_file:
            self.temp_ini_file_name = temp_file.name
            config_parser = ConfigParser()
            config_parser.add_section("Dummy")
            config_parser.set("Dummy", "parameter1", "value1")
            config_parser.set("Dummy", "parameter2", "10")
            config_parser.set("Dummy", "parameter3", "True")
            config_parser.write(temp_file)

    def tearDown(self) -> None:
        """Clean up the temporary file after tests."""
        os.remove(self.temp_ini_file_name)

    def test_load_settings_from_valid_section(self):
        """Test loading settings from a valid section of the INI file."""
        loaded_settings = load_settings_from_ini_section(
            DummySettings, self.temp_ini_file_name, "Dummy"
        )
        self.assertEqual(loaded_settings.parameter1, "value1")
        self.assertEqual(loaded_settings.parameter2, 10)
        self.assertTrue(loaded_settings.parameter3)

    def test_load_settings_from_invalid_section(self):
        """Test loading settings from a non-existent section."""
        # Load settings from a section that doesn't exist
        loaded_settings = load_settings_from_ini_section(
            DummySettings, self.temp_ini_file_name, "NonExistent"
        )

        # Assert that a default instance of DummySettings is returned
        self.assertIsInstance(loaded_settings, DummySettings)
        self.assertEqual(loaded_settings.parameter1, "default1")
        self.assertEqual(loaded_settings.parameter2, 1)
        self.assertFalse(loaded_settings.parameter3)

    def test_load_settings_with_type_mismatch(self):
        """Test loading settings with a type mismatch."""
        with open(self.temp_ini_file_name, "w", encoding="utf-8") as file:
            config_parser = ConfigParser()
            config_parser.add_section("Dummy")
            config_parser.set("Dummy", "parameter1", "value1")
            config_parser.set("Dummy", "parameter2", "not a number")
            config_parser.set("Dummy", "parameter3", "True")
            config_parser.write(file)

        with self.assertRaises(ValidationError):
            load_settings_from_ini_section(
                DummySettings, self.temp_ini_file_name, "Dummy"
            )


if __name__ == "__main__":
    unittest.main()

import unittest

from backend.app.config import Settings


BASE_SETTINGS = {
    "secret_key": "x" * 32,
    "encryption_key": "y" * 44,
    "job_shared_secret": "z" * 32,
}


class SettingsTests(unittest.TestCase):
    def test_parse_cors_origins_accepts_json_array(self) -> None:
        settings = Settings.model_validate(
            {
                **BASE_SETTINGS,
                "cors_origins": '["https://admin.example.com", "http://localhost:3000"]',
            }
        )

        self.assertEqual(
            settings.cors_origins,
            ["https://admin.example.com", "http://localhost:3000"],
        )

    def test_parse_cors_origins_accepts_csv(self) -> None:
        settings = Settings.model_validate(
            {
                **BASE_SETTINGS,
                "cors_origins": "https://admin.example.com, http://localhost:3000",
            }
        )

        self.assertEqual(
            settings.cors_origins,
            ["https://admin.example.com", "http://localhost:3000"],
        )

    def test_parse_ops_command_allowed_chat_ids(self) -> None:
        settings = Settings.model_validate(
            {
                **BASE_SETTINGS,
                "ops_command_allowed_chat_ids": "8349784231, 123456789",
            }
        )

        self.assertEqual(settings.ops_command_allowed_chat_ids_list, ["8349784231", "123456789"])


if __name__ == "__main__":
    unittest.main()

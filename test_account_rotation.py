import json
import os
import tempfile
import unittest

from state_store import select_rotating_account


class AccountRotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state_dir = self.temp.name
        self.env = {}
        for number in range(1, 4):
            self.env[f"SITE_USERNAME_{number}"] = f"user-{number}"
            self.env[f"SITE_PASSWORD_{number}"] = f"password-{number}"

    def tearDown(self):
        self.temp.cleanup()

    def test_round_robin_persists_across_calls_and_wraps(self):
        observed = []
        for _ in range(7):
            account, username, password = select_rotating_account(self.env, self.state_dir)
            observed.append((account, username, password))

        self.assertEqual([item[0] for item in observed], [1, 2, 3, 1, 2, 3, 1])
        self.assertEqual([item[1] for item in observed], [f"user-{n}" for n in [1, 2, 3, 1, 2, 3, 1]])
        self.assertEqual([item[2] for item in observed], [f"password-{n}" for n in [1, 2, 3, 1, 2, 3, 1]])

        cursor_path = os.path.join(self.state_dir, "account_rotation.json")
        with open(cursor_path, "r", encoding="utf-8") as file:
            cursor = json.load(file)
        self.assertEqual(cursor, {"next_account": 2})
        with open(cursor_path, "r", encoding="utf-8") as file:
            saved = file.read()
        self.assertNotIn("user-", saved)
        self.assertNotIn("password-", saved)

    def test_missing_secret_fails_without_advancing_cursor(self):
        del self.env["SITE_PASSWORD_2"]
        with self.assertRaisesRegex(ValueError, "SITE_PASSWORD_2"):
            select_rotating_account(self.env, self.state_dir)
        self.assertFalse(os.path.exists(os.path.join(self.state_dir, "account_rotation.json")))

    def test_invalid_cursor_fails_closed_without_overwriting(self):
        cursor_path = os.path.join(self.state_dir, "account_rotation.json")
        with open(cursor_path, "w", encoding="utf-8") as file:
            file.write('{"next_account": 9}\n')
        with self.assertRaisesRegex(ValueError, "Invalid next_account"):
            select_rotating_account(self.env, self.state_dir)
        with open(cursor_path, "r", encoding="utf-8") as file:
            self.assertEqual(json.load(file), {"next_account": 9})


if __name__ == "__main__":
    unittest.main()

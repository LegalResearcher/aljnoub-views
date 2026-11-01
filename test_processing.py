import json
import main as main_module
import os
import tempfile
import unittest
from unittest.mock import patch
from main import (
    discover_new_links,
    load_previous_batch,
    pending_links,
    prepare_run_batch,
    run_browser_send,
)
from processing_state import (
    FATAL_PAUSE_RESET_FILES,
    is_automation_paused,
    load_account_history,
    pause_automation,
)
from retry_link import process_manual_retry


class FakeSender:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [])
        self.calls = []

    def __call__(self, link):
        self.calls.append(link)
        return self.outcomes.pop(0) if self.outcomes else "ok"


class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = self.temp.name
        self.links = [f"https://t.me/aljnoubvoice/{number}" for number in range(8943, 8950)]
        self.sleep_patch = patch("main.time.sleep", return_value=None)
        self.sleep_patch.start()

    def tearDown(self):
        self.sleep_patch.stop()
        self.temp.cleanup()

    def test_new_links_precede_previous_batch_and_are_deduplicated(self):
        with open(os.path.join(self.state, "previous_batch.json"), "w", encoding="utf-8") as file:
            json.dump([self.links[0], self.links[1]], file)
        batch = prepare_run_batch([self.links[2], self.links[0]], self.state)
        self.assertEqual(batch, [self.links[2], self.links[0], self.links[1]])
        self.assertEqual(load_previous_batch(self.state), batch)

    def test_legacy_queue_migration_keeps_all_incomplete_links(self):
        with open(os.path.join(self.state, "telegram_links.txt"), "w", encoding="utf-8") as file:
            file.write("\n".join(self.links) + "\n")
        with open(os.path.join(self.state, "success_counts.json"), "w", encoding="utf-8") as file:
            json.dump({self.links[0]: 9}, file)
        migrated = load_previous_batch(self.state)
        self.assertEqual(migrated, self.links[1:])

    def test_only_new_links_are_discovered_once(self):
        found = discover_new_links(self.state, [self.links[0], self.links[1]])
        self.assertEqual(found, self.links[:2])
        self.assertEqual(discover_new_links(self.state, [self.links[0], self.links[1], self.links[2]]), [self.links[2]])

    def test_start_after_post_id_excludes_anchor_and_older_links(self):
        before = "https://t.me/aljnoubvoice/8941"
        anchor = "https://t.me/aljnoubvoice/8942"
        after = "https://t.me/aljnoubvoice/8943"
        self.assertEqual(discover_new_links(self.state, [before, anchor, after]), [after])

        with open(os.path.join(self.state, "previous_batch.json"), "w", encoding="utf-8") as file:
            json.dump([before, anchor, after], file)
        self.assertEqual(prepare_run_batch([], self.state), [after])

    def test_account_is_not_given_same_link_twice_but_next_account_can_process_it(self):
        batch = self.links[:2]
        first = FakeSender()
        self.assertEqual(run_browser_send(first, self.state, 1, batch), 0)
        self.assertEqual(first.calls, batch)
        repeated = FakeSender()
        self.assertEqual(run_browser_send(repeated, self.state, 1, batch), 0)
        self.assertEqual(repeated.calls, [])
        next_account = FakeSender()
        self.assertEqual(run_browser_send(next_account, self.state, 2, batch), 0)
        self.assertEqual(next_account.calls, batch)
        self.assertEqual(load_account_history(self.state), {link: [1, 2] for link in batch})

    def test_failed_attempt_is_still_recorded_for_that_account(self):
        sender = FakeSender(["fail"])
        run_browser_send(sender, self.state, 3, [self.links[0]])
        self.assertEqual(pending_links([self.links[0]], 3, self.state), [])
        self.assertEqual(pending_links([self.links[0]], 4, self.state), [self.links[0]])

    def test_scheduled_run_skips_links_at_success_or_failure_limit(self):
        with open(os.path.join(self.state, "success_counts.json"), "w", encoding="utf-8") as file:
            json.dump({self.links[0]: 9}, file)
        with open(os.path.join(self.state, "failed_attempts.json"), "w", encoding="utf-8") as file:
            json.dump({self.links[1]: 3}, file)

        sender = FakeSender()
        run_browser_send(sender, self.state, 1, self.links[:3])

        self.assertEqual(sender.calls, [self.links[2]])

    def test_run_processes_all_eligible_links_without_a_nine_request_cap(self):
        batch = [f"https://t.me/aljnoubvoice/{number}" for number in range(1, 12)]
        sender = FakeSender()
        run_browser_send(sender, self.state, 1, batch)
        self.assertEqual(sender.calls, batch)
        self.assertEqual(pending_links(batch, 1, self.state), [])

    def test_main_selects_next_account_with_eligible_links(self):
        with open(os.path.join(self.state, "account_rotation.json"), "w", encoding="utf-8") as file:
            json.dump({"next_account": 1}, file)
        with patch.object(main_module, "STATE_DIR", self.state), \
             patch.object(main_module, "discover_new_links", return_value=[]), \
             patch.object(main_module, "prepare_run_batch", return_value=self.links[:2]), \
             patch.object(main_module, "pending_links", side_effect=lambda links, account, state: [links[0]] if account == 2 else []), \
             patch.object(main_module, "select_rotating_account", return_value=(2, "user", "pass")) as select_account, \
             patch("browser_sender.BrowserSender") as browser_sender, \
             patch.object(main_module, "run_browser_send", return_value=0):
            browser_sender.return_value.__enter__.return_value = object()
            self.assertEqual(main_module.main(), 0)
            select_account.assert_called_once_with(os.environ, self.state, selected_account=2)

    def test_prepare_batch_prunes_completed_and_failure_limited_links(self):
        with open(os.path.join(self.state, "success_counts.json"), "w", encoding="utf-8") as file:
            json.dump({self.links[0]: 9}, file)
        with open(os.path.join(self.state, "failed_attempts.json"), "w", encoding="utf-8") as file:
            json.dump({self.links[1]: 3}, file)
        batch = prepare_run_batch(self.links[:3], self.state)
        self.assertEqual(batch, [self.links[2]])
        self.assertEqual(load_previous_batch(self.state), [self.links[2]])

    def test_finished_link_is_removed_from_saved_batch_after_target_success(self):
        with open(os.path.join(self.state, "success_counts.json"), "w", encoding="utf-8") as file:
            json.dump({self.links[0]: 8}, file)
        save_previous = main_module.save_previous_batch
        save_previous([self.links[0]], self.state)
        sender = FakeSender()
        self.assertEqual(run_browser_send(sender, self.state, 1, [self.links[0]]), 0)
        self.assertEqual(load_previous_batch(self.state), [])

    def test_main_does_not_select_account_or_open_browser_when_no_account_has_work(self):
        with patch.object(main_module, "STATE_DIR", self.state), \
             patch.object(main_module, "discover_new_links", return_value=[]), \
             patch.object(main_module, "prepare_run_batch", return_value=self.links[:2]), \
             patch.object(main_module, "pending_links", return_value=[]), \
             patch.object(main_module, "select_rotating_account") as select_account:
            self.assertEqual(main_module.main(), 0)
            select_account.assert_not_called()

    def test_manual_retry_does_not_send_when_automation_is_paused(self):
        pause_automation(self.state, "test pause")
        sender = FakeSender()
        self.assertEqual(process_manual_retry(self.links[0], sender, self.state), 1)
        self.assertEqual(sender.calls, [])

    def test_normal_manual_link_failure_does_not_pause_automation(self):
        sender = FakeSender(["fail"])
        self.assertEqual(process_manual_retry(self.links[0], sender, self.state), 1)
        self.assertEqual(sender.calls, [self.links[0]])
        self.assertFalse(is_automation_paused(self.state))

    def test_normal_link_failure_does_not_clear_processing_state(self):
        targets = list(FATAL_PAUSE_RESET_FILES) + [".gitkeep"]
        for filename in targets:
            with open(os.path.join(self.state, filename), "w", encoding="utf-8") as file:
                file.write("keep me")
        sender = FakeSender(["fail"])

        self.assertEqual(process_manual_retry(self.links[0], sender, self.state), 1)

        self.assertFalse(is_automation_paused(self.state))
        for filename in targets:
            self.assertTrue(os.path.exists(os.path.join(self.state, filename)), filename)

    def test_fatal_pause_clears_processing_files_but_preserves_pause_marker_and_gitkeep(self):
        targets = list(FATAL_PAUSE_RESET_FILES)
        for filename in targets + [".gitkeep"]:
            with open(os.path.join(self.state, filename), "w", encoding="utf-8") as file:
                file.write("keep me")
        sender = FakeSender(["fatal"])

        self.assertEqual(process_manual_retry(self.links[0], sender, self.state), 1)

        self.assertTrue(is_automation_paused(self.state))
        self.assertTrue(os.path.exists(os.path.join(self.state, "automation_paused")))
        self.assertTrue(os.path.exists(os.path.join(self.state, ".gitkeep")))
        for filename in targets:
            self.assertFalse(os.path.exists(os.path.join(self.state, filename)), filename)

    def test_fatal_result_does_not_retry_link_on_same_account(self):
        sender = FakeSender(["fatal"])
        self.assertEqual(run_browser_send(sender, self.state, 5, [self.links[0]]), 1)
        self.assertTrue(is_automation_paused(self.state))
        self.assertEqual(load_account_history(self.state), {})


if __name__ == "__main__":
    unittest.main()

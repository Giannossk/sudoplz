from __future__ import annotations

import argparse
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sudoplz import askpass, manager


def config_args(**overrides: bool | int | None) -> argparse.Namespace:
    values: dict[str, bool | int | None] = {
        "show": False,
        "auto_approve": False,
        "require_confirmation": False,
        "no_expire": False,
        "expire_hours": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class AutoApproveConfigTests(unittest.TestCase):
    def test_auto_approve_requires_explicit_interactive_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            config_file = config_dir / "config.json"
            current = {"require_user_confirmation": True, "expiration_hours": 168}
            fake_stdin = Mock()
            fake_stdin.isatty.return_value = True

            with (
                patch.object(manager, "CONFIG_DIR", config_dir),
                patch.object(manager, "CONFIG_FILE", config_file),
                patch.object(manager, "load_config", return_value=current),
                patch.object(manager.sys, "stdin", fake_stdin),
                patch("builtins.input", return_value="AUTO-APPROVE"),
            ):
                self.assertTrue(manager.cmd_config(config_args(auto_approve=True)))

            saved = json.loads(config_file.read_text())
            self.assertFalse(saved["require_user_confirmation"])
            self.assertEqual(stat.S_IMODE(config_file.stat().st_mode), 0o600)

    def test_auto_approve_is_rejected_without_a_tty(self) -> None:
        fake_stdin = Mock()
        fake_stdin.isatty.return_value = False
        with (
            patch.object(manager, "load_config", return_value={"require_user_confirmation": True}),
            patch.object(manager.sys, "stdin", fake_stdin),
        ):
            self.assertFalse(manager.cmd_config(config_args(auto_approve=True)))

    def test_confirmation_mode_can_be_restored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            config_file = config_dir / "config.json"
            current = {"require_user_confirmation": False, "expiration_hours": 168}

            with (
                patch.object(manager, "CONFIG_DIR", config_dir),
                patch.object(manager, "CONFIG_FILE", config_file),
                patch.object(manager, "load_config", return_value=current),
            ):
                self.assertTrue(
                    manager.cmd_config(config_args(require_confirmation=True))
                )

            saved = json.loads(config_file.read_text())
            self.assertTrue(saved["require_user_confirmation"])


class AutoApproveAskpassTests(unittest.TestCase):
    def test_auto_approve_skips_dialog_and_totp_but_keeps_security_checks(self) -> None:
        config = {
            "require_user_confirmation": False,
            "allowed_paths": ["/tmp"],
            "expiration_hours": 0,
            "allowed_processes": ["sudo"],
            "max_attempts_per_hour": 30,
            "lockout_minutes": 15,
        }

        with (
            patch.object(askpass, "check_rate_limit", return_value=True) as rate_limit,
            patch.object(askpass, "process_name", return_value="sudo"),
            patch.object(askpass, "show_dialog") as dialog,
            patch.object(askpass, "prompt_totp") as totp,
            patch.object(askpass.os, "getcwd", return_value="/tmp/project"),
            patch.dict(askpass.os.environ, {"TERM": "xterm"}, clear=True),
        ):
            self.assertTrue(askpass.check_security(config, identity=None))

        rate_limit.assert_called_once_with(30, 15)
        dialog.assert_not_called()
        totp.assert_not_called()

    def test_audit_records_auto_approved_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audit_file = Path(directory) / "audit.log"
            with (
                patch.object(askpass, "AUDIT_LOG_FILE", audit_file),
                patch.object(askpass.os, "getcwd", return_value="/tmp/project"),
            ):
                askpass.write_audit_entry(123, "sudo", "apt install foo", "auto-approved")

            entry = json.loads(audit_file.read_text())
            self.assertEqual(entry["status"], "auto-approved")
            self.assertEqual(entry["command"], "apt install foo")


if __name__ == "__main__":
    unittest.main()

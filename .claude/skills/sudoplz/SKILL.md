---
name: sudoplz
description: Use whenever a task needs root/sudo privileges on this machine — installing packages, editing system files, managing services, touching sudoers, etc. Run the command through sudoplz's askpass helper instead of plain sudo or asking the user to run it manually via `!`.
---

When a command needs elevated (root) privileges, run it as `sudo -A <command>` via Bash directly — don't fall back to asking the user to type it themselves.

Usage: `SUDO_ASKPASS="$HOME/.local/bin/askpass" sudo -A <command> [args...]`, e.g.:
```
SUDO_ASKPASS="$HOME/.local/bin/askpass" sudo -A dnf install -y akmod-nvidia
```
Set the env var inline on every call — Bash tool invocations run non-interactively and may not source the user's shell rc files, so don't rely on it being exported already.

How it works: the sudo password is stored at `~/.sudo_askpass.age` (or `~/.sudo_askpass.ssh`), encrypted with the user's SSH key. On every `sudo -A` call, the `askpass` helper decrypts it and hands it to sudo — but only after popping a native GUI dialog on the user's screen showing the exact command about to run. They click Allow or Deny each time; the password itself never passes through the conversation, a tool call, or the terminal. Works for any command — there is no allowlist to pre-declare.

Before calling it, say one sentence stating what the command will actually do. The dialog shows the raw command line but not necessarily why — the user needs your text, not just the dialog, to know what they're approving. Still apply the normal rules around destructive/hard-to-reverse actions (confirm first, explain blast radius); the dialog authenticates the request, it is not a substitute for that confirmation.

Notes:
- `sudo -n` explicitly disallows prompting and will never trigger askpass — always use `-A`.
- If a call fails with "Error: no password found in secure storage," the user hasn't run `sudoplz set` yet (or it expired — 1 week by default). That command reads the password from their own terminal via `getpass`; tell them to run it themselves, never type or ask for the password yourself.
- Passwords expire automatically (`sudoplz config --show` to check, `--expire-hours N` / `--no-expire` to change).
- Requires an active GUI session (zenity/osascript dialog). If ever invoked headless/over SSH with no display, askpass fails fast unless TOTP is set up (`sudoplz totp-setup`) — otherwise fall back to handing the user the raw command to run via `!`.
- If a call seems to hang, the dialog is almost certainly sitting on screen waiting for a click — tell the user to check, rather than retrying or killing it.
- `sudoplz audit` shows recent askpass usage (approved/denied, command, timestamp) if something needs debugging.

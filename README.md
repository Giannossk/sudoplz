# sudoplz

Give Claude Code, Cursor, and other AI coding agents the ability to run `sudo` — with case-by-case GUI approval by default, or explicit auto-approval for environments that already ask the user to approve each command. No passwordless sudo or `/etc/sudoers` allowlists.

Your sudo password is encrypted with your SSH private key. By default, it is only decrypted after you approve a dialog showing the exact command about to run. An explicit auto-approve mode can instead trust the coding environment's own user-approval prompt.

![Sudo approval dialog showing a command about to run, with Deny and Allow buttons](assets/screenshot.png)

## Why

Coding agents can't handle interactive terminal prompts. Ask Claude Code to run `sudo apt install foo` and you get `sudo: Authentication failed`. The common workarounds all have problems:

- **Passwordless sudo** gives the agent — and anything else running as your user — unrestricted root.
- **`/etc/sudoers` allowlists** require predicting every command the agent will ever need. No case-by-case review.
- **Manual copy-paste** is tedious and breaks the agent's flow.

`sudoplz` plugs into `sudo -A`, so the agent runs `sudo -A <command>`. In the default mode, you see the exact command in a dialog and click Allow or Deny. In auto-approve mode, the coding environment is responsible for asking you first. Both modes work without pre-declaring commands.

This threat model assumes a personal workstation with an encrypted disk and a passphrase-protected SSH key. Not appropriate for shared or production systems.

## Installation

1. **Use traditional `sudo`, not `sudo-rs`.** `sudo-rs` doesn't support askpass. Check with `sudo --version` — it should say "Sudo version 1.x.x". If you're on `sudo-rs`, switch:
   ```bash
   sudo update-alternatives --install /usr/bin/sudo sudo /usr/bin/sudo.ws 100
   sudo update-alternatives --config sudo   # pick sudo.ws
   ```
2. Make sure you have an SSH key (ed25519, ecdsa, rsa, or dsa).
3. Install system dependencies:
   - [`age`](https://github.com/FiloSottile/age) — required if your SSH key is Ed25519 (the most common case today). `sudo pacman -S age` / `sudo apt install age` / `brew install age`.
   - `zenity` on Linux — provides the GUI approval dialog. Pre-installed on most GNOME-based distros; `sudo apt install zenity` if missing. Not needed on macOS (uses AppleScript).
4. Install from PyPI with [`uv`](https://docs.astral.sh/uv/):
   ```bash
   uv tool install sudoplz
   ```
   This puts `askpass` and `sudoplz` on your PATH. (For development: clone the repo and run `uv tool install .` instead.)
5. Point `SUDO_ASKPASS` at the installed binary (add to `~/.bashrc`, `~/.zshrc`, etc.):
   ```bash
   export SUDO_ASKPASS="$(which askpass)"
   ```
6. Store your sudo password:
   ```bash
   sudoplz set
   ```

## Usage

Your agent (or you) runs `sudo -A <command>`. In the default mode, a dialog pops up showing the command for approval.

```bash
sudo -A apt install foo
```

If your coding-agent environment already shows its own trusted user-approval prompt, you can explicitly opt out of sudoplz's second dialog:

```bash
sudoplz config --auto-approve
# Read the warning, then type AUTO-APPROVE.
```

Restore case-by-case sudoplz confirmation at any time:

```bash
sudoplz config --require-confirmation
```

Auto-approve trusts the upstream environment; sudoplz cannot verify that another approval actually happened. Path and process allowlists, rate limiting, expiration, encrypted storage, integrity checks, and auditing remain active. A locked SSH key may still need its separate passphrase prompt once per session.

Gotcha: `sudo -n` explicitly disallows prompting and will never trigger askpass. Always use `-A`.

Test the integration with:

```bash
sudoplz test
```

## Security

### Encryption at rest

Passwords are encrypted with your SSH key:

- **Ed25519**: `age` encryption, stored at `~/.sudo_askpass.age`
- **RSA/ECDSA/DSA**: OpenSSL asymmetric encryption, stored at `~/.sudo_askpass.ssh`

Encrypted files have 600 permissions. Key preference: ed25519 > ecdsa > rsa > dsa. Falls back to the system keyring if available. Refuses plain text storage.

### Defense in depth

Encryption alone doesn't cover every abuse path — anything running as your user can in principle request decryption. The askpass script runs these checks on every invocation; any failure means no decryption:

- **Caller path whitelist.** Only decrypts when the caller's working directory is on an allowlist (home, `/tmp`, etc.). Blocks invocations from unexpected locations like `/var/tmp/malicious`.
- **Caller process whitelist.** Parent process must be on an allowlist (sudo, your shell, your IDE, your deploy tool). Keeps arbitrary binaries from invoking askpass directly.
- **User confirmation.** By default, a GUI dialog asks for approval on each decryption, so any sudo elevation you didn't initiate is visible and can be denied. Auto-approve is an explicit opt-in for environments that provide their own approval layer.
- **Rate limiting.** Configurable max-attempts-per-hour and lockout window. Contains runaway scripts and brute-force attempts.
- **Password expiration.** Stored passwords age out automatically (default: 1 week). A stolen blob becomes useless once it expires, even with your SSH key.

Configure these in `~/.config/sudoplz/config.json` — an example is shipped as `askpass-config.json` in the repo; copy it and edit.

### Why age for Ed25519?

Ed25519 is a signing algorithm (EdDSA), not encryption. OpenSSL handles RSA encryption directly, but Ed25519 keys can't do asymmetric encryption at all. `age` was designed to work with SSH keys including Ed25519.

### SSH key unlocking

If your SSH key has a passphrase (recommended), the askpass tool will:

1. Check whether the key is loaded in ssh-agent
2. Prompt for the passphrase via GUI if it isn't
3. Load the key into ssh-agent for the session

You enter the passphrase once per session. After that, sudo commands use the configured approval mode. You need a running ssh-agent — most desktop environments start one on login; if not, `eval "$(ssh-agent -s)"` in your shell startup.

This works under `sudo -A` even though sudo strips `SSH_AUTH_SOCK`: the script reconnects to your running ssh-agent.

## Commands

```bash
sudoplz set        # Store password (terminal prompt; expires per config, 1 week default)
sudoplz set-totp   # Store password with TOTP verification (headless)
sudoplz totp-setup # Set up TOTP for headless sessions
sudoplz get        # Check if password exists
sudoplz clear      # Remove password
sudoplz test       # Test sudo integration
sudoplz audit      # Show recent askpass usage
sudoplz config --auto-approve          # Trust upstream approval; skip command dialog
sudoplz config --require-confirmation  # Restore per-command GUI/TOTP approval
```

## Headless/SSH usage with TOTP

For servers or SSH sessions without a display, authenticate with TOTP.

### Initial setup (run once from a GUI session)

```bash
sudoplz totp-setup
```

Prints a TOTP secret and an `otpauth://` URL to add to your authenticator app.

### Setting a password from a headless session

```bash
sudoplz set-totp
```

Enter your 6-digit TOTP code, then your password.

### Using sudo with TOTP

When `DISPLAY` isn't set, askpass prompts for a TOTP code:

```bash
# Interactive — prompts for TOTP code
sudo -A command

# Non-interactive — pass TOTP via environment
TOTP="123456" sudo -A command
```

## Credits

The idea — an SSH-key-encrypted sudo password served via `SUDO_ASKPASS`, gated by a confirmation dialog — is from [GlassOnTin/secure-askpass](https://github.com/GlassOnTin/secure-askpass). That project is dormant; `sudoplz` is a substantially rewritten and cleaned up fork. Thanks to [@GlassOnTin](https://github.com/GlassOnTin) for the original idea.

## License

MIT — see LICENSE.

# Security

Clover runs AI-chosen commands on your Mac, so its safety gate matters.

- **Permission modes:** *Ask first* (default) shows an Allow card before deleting, sending, buying or changing files. *Auto* asks only before deleting or buying. *Bypass* never asks.
- **Hard denials in every mode:** `rm`, `sudo`, `dd`, disk tools, shutdown/reboot and `git push` are always refused, for Claude Code, Antigravity and every API key provider.
- **Keys** stay in `~/.config/clover/settings.json` (mode 0600) and are sent only to the provider you chose.
- **Voice** is transcribed on your Mac; audio never leaves it.

## Reporting a vulnerability

Please don't open a public issue. Use GitHub's private vulnerability reporting on this repository (Security → Report a vulnerability). We aim to reply within 3 working days.

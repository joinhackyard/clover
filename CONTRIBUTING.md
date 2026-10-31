# Contributing to Clover

Thanks for helping Clover grow. 🍀

## Setup

```bash
git clone https://github.com/joinhackyard/clover.git && cd clover
./build.sh                                  # builds and runs ~/Applications/Clover.app (macOS 26)
python3 -m unittest discover -s tests       # offline regressions; no AI calls, no Mac actions
```

UI pages can be checked in any browser with a mock native bridge:

```bash
python3 -m http.server 8765 --bind 127.0.0.1   # then open http://127.0.0.1:8765/tests/ui.html or tests/settings.html
```

## Where things live

| Path | What it is |
|---|---|
| `Clover.swift` | The app: hotkey, wake word, speech, overlay window, sounds, menu bar, Settings and setup windows |
| `clover.py` | The brain: instant commands, system prompt, Mac helpers, the safety gate, AI clients |
| `clover_engine.py` | Clover's own model engine for API keys (Claude, OpenAI, Azure, Gemini, OpenRouter, Groq, Mistral, DeepSeek, xAI, Ollama, custom) |
| `ui/` | Overlay, Settings, setup, agents and meeting pages; `orbs.js` is the orb and answer renderer |
| `scripts/` | Generators for the sound pack, icon and banner |

## Pull requests

- Keep changes focused and covered by a test in `tests/`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org): `feat:`, `fix:`, `perf:`, `docs:`, `ci:`…
- New features must fit the [budget](README.md#budget): instant commands cost nothing, AI asks stay fast and cheap, waiting costs nothing.
- Never weaken the safety gate: hard denials (`rm`, `sudo`, disk tools, shutdown) hold in every permission mode and for every AI provider.

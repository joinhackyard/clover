<p align="center"><img src="docs/banner.png" alt="Clover by Hackyard. Your whole Mac, one sentence away." width="100%"></p>

<p align="center">
  <a href="https://github.com/joinhackyard/clover/releases/latest"><img src="docs/readme/button-download.png" alt="Download for Mac" height="58"></a>&nbsp;&nbsp;
  <a href="https://joinhackyard.github.io/clover/"><img src="docs/readme/button-website.png" alt="Website" height="58"></a>&nbsp;&nbsp;
  <a href="https://joinhackyard.github.io/clover/docs.html"><img src="docs/readme/button-docs.png" alt="Docs" height="58"></a>
</p>

<p align="center">
  A little clover that lives on your Mac. Hold <kbd>⌃</kbd> <kbd>⌥</kbd> <kbd>space</kbd> or just say <b>“Clover”</b>, and ask.<br>
  It moves your windows, finds your files, reads your screen and types for you anywhere.<br>
  Free, open source, and your voice never leaves your Mac.
</p>

<p align="center">
  <a href="https://github.com/joinhackyard/clover/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/joinhackyard/clover?color=2E9E6A&label=release&style=flat-square"></a>
  <img alt="macOS 26+" src="https://img.shields.io/badge/macOS-26%2B-1A6B46?logo=apple&logoColor=white&style=flat-square">
  <a href="https://github.com/joinhackyard/clover/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/joinhackyard/clover/ci.yml?label=CI&color=2E9E6A&style=flat-square"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-2E9E6A?style=flat-square"></a>
  <a href="https://github.com/joinhackyard/clover/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/joinhackyard/clover?color=2E9E6A&style=flat-square"></a>
</p>

<br>

<img src="docs/readme/chat.png" alt="Say it like you’d say it to a friend. “Code on my big screen, Chrome and Terminal on the laptop.” Done, three windows, two displays." width="100%">

<br>

<h3 align="center">One line and you’re in</h3>

```bash
curl -fsSL https://raw.githubusercontent.com/joinhackyard/clover/main/install.sh | bash
```

<p align="center"><sub>Needs macOS 26 and one AI: Claude Code on your Claude plan, Antigravity on your Google plan, your own API key, or Ollama on your Mac.<br>Prefer a ready-made app? Grab it from <a href="https://github.com/joinhackyard/clover/releases/latest">Releases</a>. Every way to install is <a href="#install">below</a>.</sub></p>

<br>

<img src="docs/readme/features.png" alt="Hands-free. Dictate anywhere. Sees your screen. Draws to explain. Works in the background. Any AI you already have." width="100%">

<br>

<img src="docs/readme/gestures.png" alt="Flick it away. Pinch it small. Force click to hear. Turn the page." width="100%">

<p align="center"><sub>Things follow your fingers, keep their speed when you let go, and you can catch them mid-air.<br>On a Force Touch trackpad you feel a little tick when a gesture lands. Reduce Motion turns it all into a calm fade.</sub></p>

<br>

<h3 align="center">Everything else, tucked in</h3>

<details>
<summary><b>Things to say</b></summary>
<br>

| You say | Clover |
|---|---|
| *“Code on my big screen, Chrome and Terminal on the laptop.”* | Arranges three windows across two displays. |
| *“Open Spotify.”* or *“Terminal on the left.”* | Runs instantly, with no AI at all. |
| *“Find my notes about the Tokyo trip.”* | Searches your files by what’s inside them and opens the match on your other screen. |
| *“What’s wrong with this code?”* | Looks at your screen and answers in a line. |
| *“Reply to this. Thursday works, send me a time.”* | Reads the email on screen and writes the reply. Insert puts it at your cursor. It never sends. |
| *“Move my dentist appointment to 4.”* | Shows the old and new time on a card and moves it when you approve. Adding is immediate; moving or deleting asks first. |
| *“Find me a desk lamp under $30 on Amazon.”* | Works in Chrome behind your apps; a live mini screen shows it. |
| *“Where do I turn on Night Shift?”* | A ring lights up the exact spot on your screen. |
| *“Play my late night coding playlist.”* | Plays it in a second, no clicks. |
| *“When I say focus mode, close Slack and open my to-do list.”* | Remembers it. Next time, two words do it all. |

Ask for something new once and Clover works out the steps. Ask again and it runs in a blink, with no AI. Say “remember…” and every ask after that knows it.

</details>

<details>
<summary><b>Hands-free and voice commands</b></summary>
<br>

Turn on **Wake word** in Settings → General → Hands-free (off by default). The word is “Clover” unless you type your own. Say it, with or without “hey” first; a little chirp means Clover is listening. Speech is recognized on your Mac only.

After each answer Clover listens again. In hands-free chats it reads answers aloud (Settings → **Read answers aloud in hands-free chats**) and plays a soft chime when it’s your turn. Clicking other apps never closes a hands-free chat. While the wake word is on, macOS shows the orange mic dot.

**Voice commands** never reach the AI:

| Say | Clover |
|---|---|
| “stop”, “cancel”, “that’s all”, “thanks Clover”, “bye” | Ends the hands-free chat |
| “copy that” | Copies the last answer |
| “say that again”, “repeat that” | Reads the last answer again |
| “be quiet”, “shush” | Stops talking and listening until you say “Clover” |

Clover has its own little sound pack too (Pip, Hop, Bloom, Hush, Chirp), or classic Mac sounds, or silence.

</details>

<details>
<summary><b>Bring your own AI</b></summary>
<br>

Settings → Intelligence → **AI provider**:

| Provider | What you enter | Notes |
|---|---|---|
| **Claude Code** (default) | Nothing: your Claude plan sign-in | Background agents, connectors and routines run here. |
| **Antigravity** | Nothing: your Antigravity (Google) sign-in | Runs the `agy` CLI headless on your existing plan. Clover’s safety gate is installed as its `PreToolUse` hook; if Antigravity doesn’t load the hook, Clover only lets it answer, never act. Optional model override. |
| **Claude API** | Anthropic key | Defaults: `claude-haiku-5-5` fast, `claude-sonnet-5-5` for real work. Uses prompt caching. |
| **OpenAI** | OpenAI key (base URL optional) | Defaults: `gpt-5-mini` fast, `gpt-5` for work. **Load models** lists your chat models. |
| **Azure OpenAI** | Endpoint, key, deployment (+ optional work deployment), API version | Classic `…/openai/deployments/<name>` URLs, or `v1` for the Azure AI Foundry v1 API. |
| **Google Gemini** | Gemini API key | `gemini-3.5-flash` fast, `gemini-3.1-pro` for work. |
| **OpenRouter, Groq, Mistral, DeepSeek, xAI** | That service’s key | Sensible fast/work defaults; change them or load the model list. |
| **Ollama** | Nothing (local) | Talks to `http://localhost:11434/v1`; pick a model you’ve pulled. |
| **Custom** | Base URL, optional key, model, format | Any OpenAI-compatible chat completions server (LM Studio, vLLM, Together…) or Anthropic Messages. |

**Test connection** makes one tiny real call and tells you what’s wrong (bad key, wrong deployment, unreachable). With an API key, Clover runs its own tool loop: the model gets a `bash` tool and a `read_file` tool (screenshots come back as images), and every call goes through the same safety gate as Claude Code. **Cheapest** keeps every ask on the fast model, **Balanced** moves long jobs to the work model, **Most capable** always uses the work model. Keys stay in `~/.config/clover/settings.json` (mode 0600) and only go to the provider you chose.

</details>

<details>
<summary><b>Permissions and safety</b></summary>
<br>

Settings → Account & Access → **Safety** has three modes:

| Mode | What Clover does |
|---|---|
| **Ask first** (default) | Shows an Allow card before anything deletes, sends, buys, runs a program or changes a file. |
| **Auto** | Acts on its own and only asks before deleting or buying. |
| **Bypass permissions** | Never asks. |

In every mode, for every AI provider, `rm`, `sudo`, disk tools, shutdown and `git push` stay blocked. Every exact command is in the ask log.

</details>

<details>
<summary><b>Every gesture</b></summary>
<br>

| Where | Gesture | What happens |
|---|---|---|
| The box | Two fingers sideways | Follows your fingers. Past a third of its width, or flicked, it flies off and closes. Short of that it springs home. |
| The box | Pinch in | Tucks into the small bar with its live steps. |
| The small bar | Pinch out, or pull down with two fingers | Opens the full box again. |
| An answer | Force click | Presses in with your finger and reads the answer aloud. |
| An agent card or an idea | Two fingers down | Its quiet choice: *Later* or ✕. |
| Settings | Two fingers sideways | The next or previous section. The ends stretch and bounce back. |
| Setup | Two fingers sideways | Back, or on to the next step. |

Only clearly sideways (or, on a card, clearly downward) movement counts, never over something that scrolls that way. Turn them off in Settings → General → Gestures.

</details>

<details>
<summary><b>The shortcut, the box, dictation and pointing</b></summary>
<br>

**Shortcut.** Choose **Hold to talk** or **Press to toggle** in Settings → General → Shortcut behavior. Pressing it while Clover answers stops it; during spoken playback it stops the voice. Esc cancels listening without sending.

**The box.** Click any answer to copy it. Click your request to edit and ask again, or press ↑ in an empty typing box to recall it. Answers come with code blocks and copy buttons, link chips, tables and math. While Clover works in a covered window, another Space or another display, a live mini screen shows that window.

**Dictate anywhere.** Hold fn to talk, let go to insert. Double-tap to lock it on. **Verbatim** types Apple’s on-device transcript with no AI. **Clean up** makes one quick AI pass that keeps your words, fixes what it clearly misheard, drops the “um”s, honours “scratch that”, and turns “new line” into formatting. For other languages pick **Whisper** in Settings → General → Speech model; it runs [whisper.cpp](https://github.com/ggml-org/whisper.cpp) on your Mac.

**Point at your screen.** Click it next to the mic, then click, circle or scribble on anything and ask about it. The other way around, ask “where do I…?” or “explain this and draw it” and Clover draws boxes, arrows and labels over your screen, one step at a time.

</details>

<details>
<summary><b>Agents, routines and Meeting Copilot</b></summary>
<br>

Ask for something big (“find me USB-C hubs”) and Clover hands it to a background agent while you keep working; a chip shows its live steps. Say “every weekday at 8, summarize my calendar” for a routine, or “tell me when the build is done” to watch a window with no AI while it waits. Agents and routines run on Claude Code.

**Meeting Copilot** (Settings → Meetings): live answers during calls, local transcripts under `~/.config/clover/meetings/`, and a recap afterwards, by AI or fully on your Mac.

</details>

<details id="install">
<summary><b>Install, update and remove</b></summary>
<br>

You need **macOS 26** or later, Apple’s command line tools (`xcode-select --install`), and one AI: [Claude Code](https://claude.com/claude-code) on a Claude Pro/Max plan, the [Antigravity CLI](https://github.com/google-antigravity/antigravity-cli), an API key for any provider above, or [Ollama](https://ollama.com).

**One line.** Checks your Mac, downloads Clover to `~/.clover`, builds `~/Applications/Clover.app` and opens it. Clover starts at login and updates itself (Settings → About & Updates). The first launch walks you through each macOS permission.

```bash
curl -fsSL https://raw.githubusercontent.com/joinhackyard/clover/main/install.sh | bash
```

**The app.** Every version is built by CI and attached to [Releases](https://github.com/joinhackyard/clover/releases/latest) as `Clover-vX.Y.Z-macOS.zip` with its SHA-256. It’s signed ad hoc, not notarized, so after unzipping into `~/Applications` run `xattr -dr com.apple.quarantine ~/Applications/Clover.app` once, or right-click → Open.

**Nix.** Run it again to update. Nix installations show this update path in Settings instead of using Clover's Git updater.

```bash
nix run github:joinhackyard/clover
```

**From source.**

```bash
git clone https://github.com/joinhackyard/clover.git && cd clover && ./build.sh
```

**Remove.** `launchctl bootout gui/$(id -u)/org.hackyard.clover`, then delete `~/Applications/Clover.app`, `~/.clover`, `~/.config/clover` and `~/Library/LaunchAgents/org.hackyard.clover.plist`.

</details>

<details>
<summary><b>Peek inside</b></summary>
<br>

```bash
python3 -m unittest discover -s tests
```

Offline regressions for the brain, the provider engine (against mock Claude, OpenAI and Azure servers) and the pages. For UI checks run `python3 -m http.server 8765 --bind 127.0.0.1` and open `tests/ui.html` or `tests/settings.html`: they use a mock native bridge and make no Mac actions or AI calls. CI also compiles the app on macOS 26.

| Where | What lives there |
|---|---|
| `Clover.swift` | The app: hotkey, wake word, speech, overlay, sounds, gestures, windows |
| `clover.py` | The brain: instant commands, system prompt, helpers for windows, web and screen, the safety gate |
| `clover_engine.py` | Clover’s own model engine for API keys |
| `ui/` | The overlay, setup, Settings, agents and meeting pages, the orb and the sound pack |
| `docs/` | The website, published to [joinhackyard.github.io/clover](https://joinhackyard.github.io/clover/) by `.github/workflows/pages.yml` |
| `scripts/` | The sounds and the clover art, drawn from code |

**Budget.** Instant commands cost nothing. AI asks aim for a median under $0.002 and 6 s (`python3 clover.py --budget`). The system prompt stays under 10,000 characters, enforced by tests.

**Privacy.** Clover sends nothing anywhere except to the AI you chose. Anonymous usage counts are off unless a build sets `CLOVER_POSTHOG_KEY`.

</details>

<br>

<a href="https://hackyard.org"><img src="docs/readme/footer.png" alt="Free, open source, and yours. Made by Hackyard." width="100%"></a>

<p align="center"><sub>MIT © <a href="https://hackyard.org">Hackyard</a>. See <code>LICENSE</code>, and <code>THIRD_PARTY_NOTICES.md</code> for the small pieces that keep their own notices.</sub></p>

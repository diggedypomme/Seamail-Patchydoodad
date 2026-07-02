# SeaMail — Restoration & Tools


A local toolkit for running **SeaMail for Windows Ver. 1.0 (Baby Gillman Edition)** on modern Windows, plus tools for poking at its internals.

> **You need a copy of the original software to use any of this.** None of the game files are included here. The `SeaMail/` folder in this repo is a working directory that expects you to copy your own installation into it.

[![Seamail](https://img.youtube.com/vi/8fsnSh2YX80/maxresdefault.jpg)](https://www.youtube.com/watch?v=8fsnSh2YX80)

[![Watch the video](https://img.youtube.com/vi/wGaRfUntTLA/maxresdefault.jpg)](https://www.youtube.com/watch?v=wGaRfUntTLA)
---

## What is SeaMail?

SeaMail is a 2003 desktop application by Vivarium Inc. — the same studio behind the original Dreamcast Seaman. A baby Gillman lives on your Windows desktop, reacts to what you do, and is designed to interact with your email and calendar.

It's the thing that the planned Seaman for Windows was to become. Vivarium announced a full Windows port of Seaman in late 2000, developed with IBM, but what actually shipped three years later was SeaMail — a scaled-down desktop companion version rather than the full game. There's also an Adult Gillman edition.

It was Japan-only, quietly released, and is largely unknown outside of preservation circles. One of the few places it's documented at all:

- [SeaMail for Windows Ver. 1.0 (Baby Gillman Edition) on the Internet Archive](https://archive.org/details/seamail) — the ISO is archived here with an activation code
- [Seaman (video game) on Wikipedia](https://en.wikipedia.org/wiki/Seaman_(video_game)) — brief mention of SeaMail under the Windows section
- [Seaman PC – Unreleased? on Unseen64](https://www.unseen64.net/2008/05/21/seaman-pc-unreleased/) — covers the history of the cancelled full Windows port and how it relates to SeaMail

---

## The software

SeaMail requires Windows 98/XP, talks to a live JMA weather server, sends and receives email through a custom mail system, and installs hooks that crash modern Windows Explorer. Getting it running in 2025 required patching a handful of DLLs, replacing the network endpoints with local servers, and working around several legacy assumptions.

It also allowed for unlocking a lot of the features that were planned for the full Windows port of Seaman, but never made it into the final product.

Underneath it's still the Seaman AI — the Gillman grows through life stages (egg, baby, child, adult, frog), tracks what you've said, remembers what it knows about you, and changes mood and behaviour over time.

---

## What the DLL patches do

The game's DLLs contain Japanese text for UI elements, some hardcoded URLs, and hooks that are incompatible with Windows 11. The `Surgical Patcher` (part of the launcher) handles five DLL patches:

- **FriendList.dll** — UI string translations (Japanese → English for friend/contact screens)
- **InputDLL_VC.dll** — Minor compatibility fixes
- **Preference.dll** — Settings panel UI string translations
- **SeaMailer.dll** — SeaMail client string translations
- **WeatherGet.dll** — Redirects the hardcoded JMA weather URL (`www.jma.go.jp/...`) to `127.0.1` so the local weather server handles it instead

The patcher works by keeping a clean copy of each DLL in `SeaMail_original/` and diffing against your working copy in `SeaMail/`. You can apply and revert patches individually, check their status, and see exactly which bytes change and what text they correspond to.

---

## What the EXE patches do

The `EXE Builder` (in the installation tab) is used to generate four specialized versions of `Seaman.exe`. These are often referred to as the **1_2_57** builds, because they all include three critical compatibility fixes found during reverse engineering:

- **[1] Shell Enumeration Fix** — Prevents the game from recursively scanning your entire hard drive for system folders on Win11, which causes massive hangs and UI freezes.
- **[2] Active Desktop Spoof** — Tricks the game into thinking legacy Windows Active Desktop is enabled. This skips a 30-second COM timeout that otherwise happens every time you start the game.
- **[57] Stuttering Pause Fix** (at `0x3C250`) — NOPs out a legacy screensaver polling loop that causes the game's frame rate to hitch/stutter every couple of seconds on modern hardware.

### Stage-Locked EXEs
Because the software was shipping as the "Baby Gillman Edition," much of the original "Adult" game logic is suppressed. The builder generates four stage-specific EXEs (`Seaman_Stage1_Baby.exe`, `Stage3_Child.exe`, `Stage5_Adult.exe`, and `Stage8_Frog.exe`). 

Each one applies surgical patches to the engine's internal initialization routines. This forces the creature to bypass the default egg-hatching state and load the conversational AI and 3D models for your chosen life stage immediately on boot.

---

## What's in the launcher

The launcher is a local Flask app (port 5000) that manages all the supporting tools as child processes. It lives in `launcher/`.

The main things it runs:

- **SeaMail SMTP/POP server** — lets the game send and receive in-game mail
- **Weather server** — serves a fake JMA weather response so the game gets weather data
- **Menu Overlay** — transparent window that sits over the game, shows translated speech and lets you interact without the broken click hooks
- **Menu Translation Hook** — Frida hook that intercepts Japanese dialogue and reinjects English text in real time
- **Fix Loop / Interaction Hook** — required for the Adult and Frog life stages; fixes the game's input loop which breaks on those stages without it
- **DB Manager** — reads and edits the IDEA-encrypted `.udb` save files (creature state, user profile, calendar)
- **Surgical Patcher** — the DLL patching tool described above
- **SDP Monitor** — watches the game's script output and diffs it between sessions
- **Variable Tracker** — polls ~280 memory fields from the running game process and displays them live

---

## Setup

You need Python 3.10+ and your own copy of the SeaMail software.

### 1. Install the game files

Copy your SeaMail installation into the `SeaMail/` folder inside this repo. The expected result is that `SeaMail/Seaman.exe` exists alongside the rest of the game's files.

You also need `d3drm.dll` in the `SeaMail/` folder. This is a legacy Direct3D Retained Mode DLL that the game depends on but that is no longer shipped with Windows. The correct version is **350,208 bytes** (342 KB). You can find it bundled with a number of old DirectX-era games or preservation archives.

If you have an existing save to bring across, copy the `hostDB/` folder into `SeaMail/` as well. If you're starting fresh, the game will create it on first boot.

### 2. Set up the Python environments

You need two virtual environments. Run these from the `launcher/` folder:

```bat
setup_launcher_app_env.bat
setup_launcher_frida_env.bat
```

The first env (`launcher-app`) covers Flask, the DB tools, mail server, weather server, and FTP. The second (`launcher-frida`) adds Frida and everything needed for the hooks and overlay.

Both scripts create their envs under `launcher/venvs/`. The launcher UI shows a status indicator for each one on the home tab.

### 3. Start the launcher

```bat
launcher\run_launcher.bat
```

Then open `http://127.0.0.1:5000` in a browser.

### 4. Build the stage EXEs

Go to the **Installation** tab and run **Build Stage EXEs**. This generates the four patched executables (`Seaman_Stage1_Baby.exe`, `Stage3_Child.exe`, `Stage5_Adult.exe`, `Stage8_Frog.exe`) into the `SeaMail/` folder.

### 5. Apply the DLL patches

Still in the Installation tab, open **Surgical Patcher**. Click the patcher entry in the list to expand it, then click **Install All**. This applies the five DLL patches (translations + weather redirect) to your `SeaMail/` folder.

### 6. Launch a session

Before launching, close Steam and any other game platforms. This project uses Frida to inject hooks into the game process, and some anti-cheat background monitors can react to Frida even when the target is unrelated. See the [Frida and Steam](#frida-and-steam) note below.

Go to the **Suggested** tab and click **Full Session Launch**. This starts the game and all the supporting hooks together.

The game will open alongside the **Menu Overlay** — a transparent window that sits over it. The overlay has a few key controls:

- **Striped fish button** — adds a render window for the Seaman viewport
- **Top-left button** (tickle) — triggers a tickle interaction
- **Round button** — calls the creature over to your cursor

---

## Frida and Steam

**Note on background processes**

This project uses Frida to inject hooks into the Seaman process. While the game itself has no DRM and is not on Steam, you should be aware that some aggressive anti-cheat systems on modern game platforms can theoretically detect Frida running in the background.

There should be no risk to your Steam account just by running this project, and I personally haven't had any issues as you are not targeting Steam-managed games. However, as a "better safe than sorry" measure, we still recommend closing Steam and other game platforms before starting a session to avoid any possibility of being erroneously flagged by background monitors.

---

## Life stages

The game has five stages — Egg, Baby, Child, Adult, Frog — selected from the header of the launcher. Changing the stage selector updates which executable the launcher points to. Adult and Frog stages require the Fix Loop hook to be running; the launcher will warn you if you select one of those without it active.

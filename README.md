# SeaMail — Restoration & Tools

A local toolkit for running **SeaMail for Windows Ver. 1.0 (Baby Gillman Edition)** on modern Windows, plus tools for poking at its internals.

> **You need a copy of the original software to use any of this.** None of the game files are included here. The `SeaMail/` folder in this repo is a working directory that expects you to copy your own installation into it.

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

You need Python 3.10+ and two virtual environments. Run these from the `launcher/` folder:

```bat
setup_launcher_app_env.bat
setup_launcher_frida_env.bat
```

The first env (`launcher-app`) covers Flask, the DB tools, mail server, weather server, and FTP. The second (`launcher-frida`) adds Frida and everything needed for the hooks and overlay.

Both scripts create their envs under `launcher/venvs/`. The launcher UI shows a status indicator for each one on the home tab so you can see at a glance if something is missing.

Once both envs are set up, start the launcher:

```bat
launcher\run_launcher.bat
```

Then open `http://127.0.0.1:5000` in a browser.

The **Suggested** tab has a Full Session Launch button that starts the game and all the hooks together, and a Tools in Tabs button that opens them as separate Windows Terminal panes.

---

## Frida and Steam

**Do not run this at the same time as Steam** (or any other game platform with anti-cheat active).

The hooks use Frida to inject into the game process. Anti-cheat systems on your machine — including Steam's — can flag this as cheat software. Seaman has no DRM and is not on Steam, so there's no conflict with the game itself, but if you have Steam open and running other games with anti-cheat, there's a real risk of getting flagged. Just close Steam before running a session.

---

## Game files / installation

Copy your Seaman installation into the `SeaMail/` folder. The launcher settings (accessible from the Settings tab) let you point it at whichever folder you've put the files in, so you don't have to use the default path.

The game expects a specific folder structure under `SeaMail/hostDB/` for the save files. If you're starting fresh those will be created by the game on first boot. If you're copying an existing save, bring the whole `hostDB/` folder.

---

## Life stages

The game has five stages — Egg, Baby, Child, Adult, Frog — selected from the header of the launcher. Changing the stage selector updates which executable the launcher points to. Adult and Frog stages require the Fix Loop hook to be running; the launcher will warn you if you select one of those without it active.

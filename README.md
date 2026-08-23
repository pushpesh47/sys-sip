# SysSIP

**SysSIP** is a production-ready SIP/VoIP desktop application for Linux, built with PySide6 (Qt 6) and PJSUA2 (JFC PJSIP). It features a modern dialer, contact management, call history, system tray integration, and automatic Jio Fiber SIP provisioning.

---

## Overview

SysSIP provides a complete VoIP calling experience on Linux desktops:

- **SIP/VoIP Calling** — Make and receive calls with bidirectional audio
- **Jio Fiber Auto-Provisioning** — One-click setup via OTP from your Jio router
- **Generic SIP Provider Support** — Configure any SIP/VoIP provider manually
- **Multiple Account Management** — Switch between providers instantly
- **Contact Management** — Create, edit, search, and dial contacts
- **Call History** — Persistent log of incoming, outgoing, missed, and failed calls
- **System Tray Integration** — Minimize to tray, keep SIP registration alive
- **Modern Qt 6 GUI** — Responsive, accessible interface with Fusion style

---

## Features

### Dialer
- Number/SIP URI entry via keyboard or on-screen dial pad
- Real-time call state display (Calling, Ringing, Connecting, Connected, Disconnected, Failed)
- Active SIP account/provider status indicator
- Microphone mute/unmute during calls
- Call duration timer

### Voice Calling
- Outgoing calls to phone numbers or SIP URIs
- Incoming call handling with answer/reject dialog
- Bidirectional audio (AMR-WB/AMR prioritized, G.711/G.722 disabled)
- Echo cancellation and audio frame timing optimized for Jio IMS
- Automatic P-Preferred-Identity and P-Access-Network-Info headers

### Audio
- Microphone capture and speaker playback via PJSUA2 audio devices
- Mute/unmute toggle with visual feedback
- Codec priority: AMR-WB (16kHz) > AMR (8kHz)
- Custom SDP formatting for Jio IMS compatibility

### Contacts
- Create, edit, delete contacts with name, number/SIP URI, and notes
- Search by name or number
- Flexible number matching (handles +91, 0-prefix, and bare 10-digit variants)
- Dial directly from contact list

### Call History / Recent Calls
- Persistent log with direction (incoming/outgoing), status (answered/missed/rejected/failed), duration, timestamps
- SIP account/provider used per call
- Redial from history
- Contact name resolution for known numbers

### SIP Account Management
- **Jio Fiber** (default, auto-provisioned via OTP)
- **Generic SIP** (manual configuration: username, password, domain, registrar, proxy, transport, realm)
- Multiple providers stored simultaneously
- One-click connect/disconnect per provider
- Set active provider for outgoing calls
- Edit existing provider configuration
- Remove provider (de-authorizes device from Jio router for Jio Fiber)

### System Tray
- Hide main window to tray (SIP registration stays active)
- Context menu: Show/Hide, About, Exit
- Complete SIP/PJSUA2 shutdown on Exit
- Desktop notifications for registration, call events, errors

### Settings
- Audio input/output device selection (framework in place)
- Default SIP account selection
- Ringtone selection (framework in place)
- Call duration display toggle
- Auto-answer framework

---

## Architecture

```
┌─────────────────────────────┐
│           GUI               │
│     PySide6 / Qt 6          │
│  (Dialer, Accounts, OTP,    │
│   Contacts, History, Tray)  │
└──────────────┬──────────────┘
               │ Qt Signals/Slots (thread-safe)
┌──────────────▼──────────────┐
│      Application Layer      │
│  SipApplicationService      │
│  Provider Registry          │
│  Data Store (JSON, 0600)    │
│  Settings Management        │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│         SIP Engine          │
│          PJSUA2             │
│  Endpoint, Transport,       │
│  Account, Call Callbacks    │
│  Event Loop (dedicated     │
│  thread, command queue)     │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│      SIP Providers          │
│  ┌─────────┐ ┌───────────┐  │
│  │Jio Fiber│ │  Generic  │  │
│  │Provision│ │  Config   │  │
│  └─────────┘ └───────────┘  │
└─────────────────────────────┘
```

**Layer Responsibilities:**

| Layer | Responsibility |
|-------|----------------|
| GUI | All user interaction, windows, dialogs, system tray, notifications |
| Application Service | Coordinates providers, engine, data store; Qt thread bridging |
| Data Store | JSON persistence for contacts, call history, settings (atomic writes, 0600 perms) |
| SIP Engine | PJSUA2 endpoint lifecycle, transport, account, calls, media, codecs |
| Providers | Jio Fiber (auto-provisioning, OTP, device removal) / Generic (manual config) |

---

## Requirements

### Platform
- **Linux only** (tested on Ubuntu 24.04+, Debian-based distributions)
- X11 or XWayland session (Qt forced to `xcb` platform)
- Jio Fiber router on same LAN (for Jio Fiber provisioning)

### Runtime Dependencies (handled by `setup.py`)
- Python 3.10+ (verified on 3.11, 3.12)
- PySide6 ≥ 6.7
- python-dotenv ≥ 1.0
- requests ≥ 2.32, urllib3 ≥ 2.5

### Build Dependencies (installed by `setup.py` via `apt`)
- `build-essential` (gcc, g++, make)
- `swig`
- `libasound2-dev` (ALSA headers)
- `libopencore-amrnb-dev`, `libopencore-amrwb-dev`, `libvo-amrwbenc-dev` (AMR codecs)
- `patchelf` (RPATH patching)
- `qt6-base-dev` (qmake6, Qt 6 headers)
- XCB runtime libraries: `libxcb-cursor0`, `libxcb-icccm4`, `libxcb-image0`, `libxcb-keysyms1`, `libxcb-render-util0`

> **Do not install these manually.** Run `python3 setup.py` — it detects missing packages and installs them via `sudo apt`.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/pushpesh47/sys-sip.git
cd sys-sip

# Run the installer (creates venv, builds JFC PJSIP, builds PJSUA2 Python bindings, installs desktop entry)
python3 setup.py
```

### What `setup.py` Does

1. **Verifies Linux** — Exits on non-Linux platforms
2. **Creates virtual environment** — `.venv/` in project root
3. **Installs Python packages** — PySide6, requests, python-dotenv, etc. into `.venv`
4. **Installs system dependencies** — Prompts for `sudo apt` to install build/runtime packages
5. **Fetches JFC PJSIP source** — Clones `https://github.com/JFC-Group/JFC-pjproject.git` at branch `v2.15.1` into `jfc-pjproject/`
6. **Builds JFC PJSIP native libraries** — `./configure --enable-shared && make dep && make -jN`
7. **Builds PJSUA2 Python bindings** — Compiles `_pjsua2.cpython-*.so` and `pjsua2.py` against the venv Python
8. **Installs bindings into venv** — Copies to `.venv/lib/pythonX.Y/site-packages/`
9. **Patches RPATHs** — Uses `patchelf` to embed `$ORIGIN`-relative library paths in all native `.so` files
10. **Verifies PJSUA2** — Imports `pjsua2`, confirms version `2.15.1`
11. **Installs desktop entry** — Creates `~/.local/share/applications/SysSIP.desktop` with correct venv Python and project paths

The installer is **idempotent** — re-running it only rebuilds when the JFC revision, Python version, SWIG version, or ALSA headers change.

---

## Starting SysSIP

After installation, launch the application:

```bash
python3 run.py
```

Or use the **SysSIP** entry in your desktop Applications menu (installed by `setup.py`).

### What `run.py` Does

- Activates the `.venv` Python
- Sets `LD_LIBRARY_PATH` to JFC native library directories
- Forces `QT_QPA_PLATFORM=xcb` (required for Ubuntu 24.04+/Wayland)
- Sets `PYTHONPATH` to project root
- Executes `python -m app` (entry point: `app/__main__.py`)

---

## Jio Fiber SIP Provisioning

Jio Fiber does not expose SIP credentials directly. SysSIP includes an automated provisioning workflow that obtains them from your Jio router.

### Prerequisites
- Computer connected to the **same LAN** as the Jio Fiber router
- Router in **AP mode** with **SIP endpoints enabled** (see [ankurpandeyvns/gist](https://gist.github.com/ankurpandeyvns/03d11b7137ecbebc9bf7775489b30774))
- Router reachable at `jiofiber.local.html` (or know its LAN IP, e.g., `192.168.29.1`)

### Provisioning Flow

1. Open **SIP Accounts** window (`SIP` menu → `SIP Accounts` or click `+ Add Jio Fiber`)
2. Click **`+ Add Jio Fiber`**
3. SysSIP contacts `http://jiofiber.local.html:8080/request_account`
   - If hostname fails, enter router LAN IP manually
4. SysSIP sends device-add request to `https://<router>:8443/` with deterministic MAC derived from hostname `ParikaSIPProxy`
5. **Jio sends OTP via SMS** to your registered Jio number
6. Enter the 6-digit OTP in the dialog
7. SysSIP verifies OTP, fetches SIP provisioning XML, extracts credentials
8. Configuration saved to `~/.config/sys-sip/sip-providers.json` (0600 permissions)
9. SIP engine initializes and registers automatically

### Re-provisioning / Account Removal

- **Re-provision**: Right-click Jio Fiber in SIP Accounts → `Re-provision`
- **Remove account**: Right-click → `Remove` — de-authorizes device from router and deletes local config

> **Security:** OTP is never logged. Credentials are stored only in `sip-providers.json` with user-only permissions. The `.env` file (legacy) is migrated once and no longer used.

---

## Adding Other SIP Providers

SysSIP supports any standard SIP/VoIP provider.

1. Open **SIP Accounts** window
2. Click **`+ Add SIP Provider`**
3. Fill in:
   - **Name** — Display name (e.g., "My SIP Provider")
   - **Username** — SIP username (often the phone number or account ID)
   - **Password** — SIP password
   - **Domain** — SIP domain/realm (e.g., `sip.example.com`)
   - **Registrar Host** — Registrar hostname/IP
   - **Registrar Port** — Usually `5060` (UDP/TCP) or `5061` (TLS)
   - **Proxy Host** — Outbound proxy (optional)
   - **Proxy Port** — Proxy port (optional)
   - **Transport** — `UDP`, `TCP`, or `TLS`
   - **Realm** — Authentication realm (defaults to domain)
4. Click **OK** — provider added, select it, click **Connect**

---

## Using the Dialer

### Making a Call
1. Ensure a provider shows **Registered** (green indicator)
2. Enter destination number or SIP URI in the dialer input
3. Press **CALL** or hit `Enter`
4. Call progresses: `Calling...` → `Ringing...` → `Connected`
5. Use **MIC ON/MIC OFF** to mute/unmute
6. Press **HANG UP** to end

### Receiving a Call
- Incoming call dialog appears with caller name/number
- **ANSWER** — Accept call (audio connects)
- **REJECT** — Decline call
- Missed/rejected calls logged in history

### During a Call
- **Mute/Unmute** — Toggle microphone
- **Call duration** — Displayed in `MM:SS` format
- **Contact name** — Resolved from contacts if number matches

---

## Contacts and Call History

### Contacts
- **File** menu → **Contacts** (`Ctrl+T`)
- **Add** — New contact with name, number, notes
- **Edit/Delete** — Select contact, use buttons
- **Search** — Type in search box to filter
- **Dial** — Double-click or select and click **Call**

### Call History
- **File** menu → **Call History** (`Ctrl+H`)
- Shows all calls with direction, status, duration, time, SIP account
- **Redial** — Double-click or select and click **Call**
- **Clear History** — Remove all records

---

## System Tray

- **Close window** (×) → hides to tray, SIP stays registered
- **Tray icon** → Right-click for menu:
  - **Show** — Restore main window
  - **About** — Version and developer info
  - **Exit** — Full shutdown (SIP unregister, PJSUA2 destroy, process exit)

---

## Configuration

### Settings Files

| File | Location | Purpose |
|------|----------|---------|
| `sip-providers.json` | `~/.config/sys-sip/` | SIP provider configs, active provider index (0600) |
| `call_history.json` | `~/.config/sys-sip/` | Call records |
| `contacts.json` | `~/.config/sys-sip/` | Contact list |
| `phone_settings.json` | `~/.config/sys-sip/` | App settings (audio devices, ringtone, etc.) |

### Legacy `.env` Migration

On first run, if `sip-providers.json` is empty and `.env` exists in the project root, SysSIP migrates Jio Fiber credentials automatically. The `.env` file is **not used** for normal operation afterward.

---

## Troubleshooting

| Problem | Cause | Resolution |
|---------|-------|------------|
| `python3 setup.py` fails on system deps | `apt` not available or packages missing | Install packages manually, then re-run setup |
| `ModuleNotFoundError: pjsua2` | Native build failed | Check `setup.py` output; re-run after fixing deps |
| Application won't start | Not in project root / venv missing | Run `python3 run.py` from project root |
| "Virtual environment not found" | `setup.py` not run | Run `python3 setup.py` first |
| SIP account not registering | Wrong credentials / network | Verify router SIP enabled; re-provision Jio; check generic provider fields |
| Jio provisioning fails at `request_account` | Router unreachable / SIP disabled | Ensure on same LAN, router AP mode, SIP enabled per gist |
| OTP not received / verification fails | SMS delay / wrong entry | Wait 30s, re-enter; request new OTP via Re-provision |
| No audio / one-way audio | ALSA device / codec mismatch | Check PulseAudio/PipeWire; Jio requires AMR-WB/AMR (handled by engine) |
| Desktop launcher missing | `update-desktop-database` failed | Run `update-desktop-database ~/.local/share/applications` manually |
| Qt errors on Wayland | `QT_QPA_PLATFORM` not forced | `run.py` sets `xcb`; ensure not overridden in environment |
| `patchelf` errors | Missing/incompatible `patchelf` | `setup.py` installs it; ensure `build-essential` present |

---

## Development and Testing

### Project Structure

```
sys-sip/
├── app/
│   ├── __main__.py           # Application entry point
│   ├── __init__.py           # Version metadata
│   ├── config/
│   │   ├── settings.py       # Settings, provider config, persistence
│   │   └── __init__.py
│   ├── data/
│   │   ├── models.py         # CallRecord, Contact, PhoneSettings
│   │   ├── store.py          # JSON persistence (DataStore)
│   │   └── __init__.py
│   ├── gui/
│   │   ├── main_window.py    # SIP Accounts management window
│   │   ├── dialer_window.py  # Main dialer window (Phase 3)
│   │   ├── otp_dialog.py     # OTP input dialog
│   │   ├── add_provider_dialog.py
│   │   ├── qt_bridge.py      # Thread-safe Qt signal bridge
│   │   ├── assets.py         # Icon/logo loading
│   │   ├── notifications.py  # Toast notifications
│   │   └── __init__.py
│   ├── providers/
│   │   ├── base.py           # Abstract provider, ProvisioningResult
│   │   ├── jio_fiber.py      # Jio Fiber provisioning integration
│   │   └── __init__.py       # ProviderRegistry factory
│   ├── sip/
│   │   ├── engine.py         # PJSUA2 engine, callbacks, media, codecs
│   │   ├── service.py        # Application service layer
│   │   └── __init__.py
│   └── assets/
│       ├── logo/sys-sip.png
│       ├── logo/sys-sip-small.png
│       └── sound/ringtone-iphone.wav
├── test/                     # (Not present in current build)
├── setup.py                  # Full installer (venv, deps, JFC build, bindings, desktop entry)
├── run.py                    # Launcher (venv, LD_LIBRARY_PATH, QT_QPA_PLATFORM)
├── jio_fiber_sip_provisioner.py  # Standalone provisioning CLI
├── sip_config.py             # Legacy .env config helper (unused at runtime)
└── README.md
```

### Running Tests

No automated test suite is currently included. Manual testing steps:

1. `python3 setup.py` — verify clean install
2. `python3 run.py` — verify GUI launches
3. Add Jio Fiber → provision → verify **Registered**
4. Add generic SIP provider → connect → verify **Registered**
5. Make/receive test calls
6. Verify contacts, history, tray, notifications

### Development Notes

- **SIP engine runs on dedicated thread** — All PJSUA2 callbacks marshaled to Qt via `QtEventBridge` (queued connections)
- **Commands queued to engine thread** — `hangup`, `answer`, `mute` executed on PJSUA2 event loop to avoid cross-thread SWIG crashes
- **Codec configuration hardcoded for Jio** — AMR-WB/AMR prioritized; other codecs disabled
- **SDP manipulation in `_SipCallCallback.onCallSdpCreated`** — Ensures Jio IMS compatibility (origin line, fmtp, bandwidth, ptime)

---

## Security Notes

- **Credentials stored locally only** — `sip-providers.json` at `0600` permissions
- **OTP never logged** — Input dialog only; verification via HTTPS with cert verification disabled (router self-signed)
- **No telemetry / no network calls except SIP and Jio provisioning endpoints**
- **Jio provisioning uses deterministic device identity** — MAC derived from hostname `ParikaSIPProxy` (matches JFC reference)
- **Legacy `.env` migrated once** — Not used at runtime; safe to delete after migration

---

## License

This project is based on reverse-engineering and testing of Jio Fiber's locally exposed provisioning and SIP behavior.

Use only with a Jio Fiber connection and account you are authorized to use. Do not use to access, provision, impersonate, or place calls through accounts or devices you do not control or have permission to use.

---

## Credits

- **JFC PJSIP** — `https://github.com/JFC-Group/JFC-pjproject` (v2.15.1)
- **PJSUA2** — Python bindings built from JFC source
- **PySide6 / Qt 6** — GUI framework
- **Developer** — Pushpesh Sharma
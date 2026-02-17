# MicStream + CrankshaftNG Wireless Android Auto

A complete wireless Android Auto head unit system built on a Raspberry Pi 3B/4 running [CrankshaftNG](https://github.com/nicka-car/crankshaft), with a companion Android app for microphone streaming and remote touchpad control.

## Why This Exists

Google's Android Auto updates in late 2024/2025 broke compatibility with OpenAuto-based head units like CrankshaftNG. The upstream projects (aasdk, OpenAuto, CrankshaftNG) are largely abandoned and no longer maintained, leaving DIY Pi-based head units non-functional with modern phones.

This project is a working fork that patches the broken pieces back together, with additional solutions for common pain points:

- **Broken wireless AA handshake** - The btservice WiFi credential exchange needed fixes to work with current Android Auto versions.
- **No touchscreen support for HDMI setups** - Many people run CrankshaftNG with HDMI output to a car stereo or monitor that has no touchscreen. There was no way to interact with Android Auto without a physical touch panel. This project adds a virtual touchscreen controlled remotely from the phone via a companion app.
- **No microphone in wireless mode** - Wireless AA doesn't pass phone microphone audio to the head unit, so Google Assistant and phone calls had no mic input. The MicStream app streams the phone's mic over UDP to fill this gap.
- **Bluetooth pairings lost on every reboot** - CrankshaftNG's ramfs filesystem design wiped all BT link keys on power cycle, requiring manual re-pairing every time you started the car.

## Overview

This project turns a Raspberry Pi 3B or Pi 4 into a fully wireless Android Auto head unit with HDMI output. The phone connects via Bluetooth for the initial handshake, then switches to WiFi for the Android Auto data stream. Audio output goes through HDMI to the car stereo.

**Key features:**
- Wireless Android Auto over WiFi (no USB cable needed)
- Phone microphone streaming to the Pi via UDP (for Google Assistant / calls)
- Remote touchpad control from the phone app
- Automatic Bluetooth reconnection on reboot
- CPU clock management based on AA connection state
- HDMI audio output

## Architecture

```
┌─────────────────┐     BT RFCOMM      ┌──────────────────────┐
│                 │◄───────────────────►│                      │
│  Android Phone  │     WiFi (AP)       │  Raspberry Pi 3B/4   │
│  (Samsung)      │◄───────────────────►│  CrankshaftNG        │
│                 │                     │                      │
│  MicStream App  │──UDP:8000 (mic)───►│  udp_mic_receiver.py │
│                 │──UDP:8001 (touch)──►│  aa_remote.py        │
│                 │                     │                      │
│                 │     AA TCP:5000     │  OpenAuto (autoapp)  │
│                 │◄───────────────────►│        │             │
│                 │                     │        ▼ HDMI        │
│  Phone (AG)     │  BT HFP SCO (mSBC) │  sco_enhancer.py     │
│                 │◄───────────────────►│  (ofono agent)       │
│                 │  call audio ↔ HDMI  │        │             │
└─────────────────┘                     │  ┌──────────┐       │
                                        │  │Car Stereo│       │
                                        │  └──────────┘       │
                                        └──────────────────────┘
```

### Connection Flow

1. **Boot** - Pi starts, loads Bluetooth pairings from persistent storage
2. **BT Pairing** - Phone auto-connects via Bluetooth (RFCOMM)
3. **btservice** - Exchanges WiFi credentials over BT (SSID, password, IP)
4. **WiFi** - Phone connects to Pi's WiFi hotspot (`CRANKSHAFT-NG`)
5. **Android Auto** - AA stream starts over TCP port 5000
6. **Mic/Touch** - MicStream app sends mic audio (UDP:8000) and touch events (UDP:8001)

## Components

### Android App (`app/`)

**MicStream** - An Android app that provides:
- **Microphone streaming**: Captures phone mic audio at 16kHz mono S16LE and sends it to the Pi via UDP port 8000. This feeds into PulseAudio as a virtual mic source for Google Assistant and phone calls.
- **Remote touchpad**: A touch area that sends touch events (down/move/up) to the Pi via UDP port 8001, creating a virtual touchscreen for controlling Android Auto.
- **Navigation buttons**: Scroll up/down, home, and back buttons mapped to AA coordinates.

Key files:
- `MainActivity.kt` - UI and service binding
- `MicStreamService.kt` - Foreground service for mic capture and UDP streaming
- `RemoteTouchSender.kt` - UDP touch event sender with WiFi network binding
- `TouchpadView.kt` - Custom touch input view

### Pi Scripts (`pi/scripts/`)

| Script | Description |
|--------|-------------|
| `aa_remote.py` | Virtual touchscreen via uinput - receives UDP touch events and injects them as Linux input events. Creates a 1024x768 multitouch device. |
| `udp_mic_receiver.py` | Receives UDP mic audio and pipes it to PulseAudio via `pacat` into the `android_mic` null sink. |
| `aa_clock_monitor.sh` | CPU governor manager - sets `performance` (1400MHz Pi 3 / 1850MHz Pi 4) when AA is connected, `ondemand` when idle, `powersave` on thermal throttle. |
| `bt_watchdog.sh` | Monitors BT connection to phone - restarts OpenAuto when phone disconnects so it returns to the waiting screen. |
| `sco_enhancer.py` | Custom ofono HandsfreeAudioAgent with mSBC wideband (16kHz) support. Handles SCO socket lifecycle including deferred accept, mSBC encode/decode via libsbc, and bidirectional audio routing (call audio → HDMI, mic → SCO TX). |
| `udp_call_receiver.py` | Receives call audio from MicStream Android app via UDP port 8002 and plays on HDMI output. |
| `call_audio.sh` | Legacy BT HFP call audio routing (superseded by sco_enhancer.py). |
| `aa_autolaunch.py` | (Experimental) Auto-taps the media button when AA connects to open Spotify. |

### Pi Systemd Services (`pi/systemd/`)

Key custom services:
- `btservice.service` - BT RFCOMM server for AA wireless handshake
- `openauto.service` - OpenAuto (Android Auto) display server
- `aa-remote.service` - Virtual touchscreen UDP receiver
- `udp-mic-receiver.service` - Mic audio UDP receiver
- `aa-clock-monitor.service` - CPU clock management
- `bt-watchdog.service` - BT disconnect handler
- `sco-enhancer.service` - mSBC wideband call audio via ofono
- `hotspot.service` - WiFi AP (hostapd + dnsmasq)

### Pi Configs (`pi/config/`)

| File | Description |
|------|-------------|
| `boot/config.txt` | RPi boot config - HDMI settings, overclock (Pi 3: 1400MHz/192MB GPU, Pi 4: 1850MHz/256MB GPU) |
| `boot/crankshaft/crankshaft_env.sh` | CrankshaftNG environment - enables BT, hotspot, dev mode |
| `boot/crankshaft/openauto.ini` | OpenAuto settings - resolution, FPS, touchscreen, wireless AA |
| `etc/fstab` | Filesystem mounts - **modified** to persist BT pairings (see below) |
| `etc/hostapd/hostapd.conf` | WiFi AP config - SSID, channel, security |
| `etc/dnsmasq.conf` | DHCP server for WiFi clients (192.168.254.0/28) |
| `etc/pulse/system.pa` | PulseAudio config - android mic sink, HDMI audio output |
| `openauto.ini` | Working OpenAuto config snapshot |

### Source Code (`pi/aasdk-src/`, `pi/openauto-src/`)

Forked source code for the Android Auto SDK and OpenAuto display server. Key modifications documented below.

## Fixes and Modifications

### 1. Persistent Bluetooth Pairings (Critical Fix)

**Problem:** CrankshaftNG mounts `/tmp/bluetooth` as ramfs (volatile RAM filesystem) in `/etc/fstab`, and `/var/lib/bluetooth` is symlinked to it. All Bluetooth pairings (link keys) were lost on every reboot.

**Fix:**
- Commented out the ramfs mount for `/tmp/bluetooth` in `/etc/fstab`
- Removed the symlink at `/var/lib/bluetooth`
- Created a real `/var/lib/bluetooth` directory on the ext4 root filesystem
- BT pairings now persist across reboots, enabling automatic reconnection

**File:** `pi/config/etc/fstab` (line 16 - commented out)

### 2. HDMI Audio Output

**Problem:** Audio was going to the 3.5mm jack instead of HDMI.

**Fix:** Added `set-default-sink alsa_output.platform-bcm2835_audio.digital-stereo` to PulseAudio system config.

**File:** `pi/config/etc/pulse/system.pa` (last line)

### 3. Phone Microphone Streaming

**Problem:** AA wireless mode doesn't support microphone input from the phone natively.

**Fix:** Created a PulseAudio null sink (`android_mic`) that receives audio from the MicStream Android app via UDP. The null sink's monitor is remapped as the default audio source, making it available to OpenAuto for Google Assistant and calls.

**Files:**
- `pi/config/etc/pulse/system.pa` (android_mic sink config)
- `pi/scripts/udp_mic_receiver.py`
- `pi/systemd/udp-mic-receiver.service`
- `app/` (MicStream Android app)

### 4. Remote Touch Control

**Problem:** No physical touchscreen connected - needed a way to control AA from the phone.

**Fix:** Created `aa_remote.py` which sets up a Linux uinput virtual touchscreen (1024x768) and listens for UDP touch events. The MicStream Android app sends touch coordinates using a simple protocol: `[cmd(1)][x(2)][y(2)]` little-endian, where cmd is `D` (down), `M` (move), or `U` (up).

**Files:**
- `pi/scripts/aa_remote.py`
- `pi/systemd/aa-remote.service`
- `app/src/main/java/com/micstream/RemoteTouchSender.kt`
- `app/src/main/java/com/micstream/TouchpadView.kt`

### 5. CPU Overclock and Thermal Management

**Problem:** Default clock speeds are too slow for smooth AA rendering.

**Fix:**
- **Pi 3B:** Overclocked to 1400MHz with `over_voltage=2`, 500MHz SDRAM, 192MB GPU memory
- **Pi 4:** Overclocked to 1850MHz with `over_voltage=6`, 256MB GPU memory
- Dynamic clock management: full speed when AA is connected, ondemand when idle, throttle on high temps

**Files:**
- `pi/config/boot/config.txt` (overclock settings)
- `pi/scripts/aa_clock_monitor.sh`

### 7. Phone Call Audio (mSBC Wideband via ofono)

**Problem:** During phone calls, audio stays on the phone instead of routing through the car speakers. PulseAudio's built-in HFP support only handles CVSD (8kHz narrowband) and conflicts with ofono's profile management.

**Fix:** A custom ofono `HandsfreeAudioAgent` (`sco_enhancer.py`) that:
- Registers with ofono supporting both CVSD and mSBC codecs
- Handles SCO socket lifecycle including **BT_DEFER_SETUP** (kernel deferred accept)
- Decodes mSBC H2-framed audio (16kHz wideband) via libsbc for playback on HDMI
- Encodes mic audio to mSBC for SCO TX
- Auto-sets HCI voice to Transparent mode (0x0063) for mSBC passthrough on startup

PulseAudio's bluetooth module is **disabled** (`module-bluetooth-discover` commented out in `system.pa`) to prevent conflicts. ofono is the sole HFP handler.

**Key technical details:**
- ofono uses `BT_DEFER_SETUP` on its SCO listening socket. The agent must call `recv()` on the delivered fd to trigger `sco_conn_defer_accept()` in the kernel, which sends HCI Accept SCO Connection to the BT controller. Without this, the socket stays in `BT_CONNECT2` state and all I/O returns `ENOTCONN`.
- SCO SEQPACKET sockets require `libc.recv()` via ctypes - Python's `os.read()` returns empty on BT SCO sockets.
- mSBC frames are 60 bytes: `[01] [08/38/C8/F8] [AD ...SBC_data(57B)...] [FF]`

**Known limitation:** During phone calls, Android silences all non-telephony mic capture at the OS level. A USB microphone on the Pi is needed for SCO TX (uplink audio to the remote caller). Without it, the remote party cannot hear you.

**Files:**
- `pi/scripts/sco_enhancer.py`
- `pi/systemd/sco-enhancer.service`
- `pi/config/etc/pulse/system.pa` (bluetooth module disabled)

### 6. WiFi AP Configuration

The Pi runs a WiFi access point that the phone connects to for the AA data stream:
- **SSID:** `CRANKSHAFT-NG`
- **Security:** WPA2-PSK
- **Default password:** `1234567890` (change in `hostapd.conf`)
- **Subnet:** 192.168.254.0/28 (DHCP range .2-.14)
- **Pi IP:** 192.168.254.1

## Known Issues

### Call Microphone (SCO TX Uplink)

During phone calls, Android silences all non-telephony microphone capture at the kernel level. The MicStream app successfully streams the phone's mic to the Pi outside of calls (for Google Assistant), but during cellular calls it receives silence. This is a hard Android platform restriction that cannot be bypassed by any audio source, mode, or device routing change.

**Workaround:** Plug a USB microphone or USB sound card with mic input into the Pi. The sco_enhancer will automatically use it via PulseAudio's `android_mic_source` (or reconfigure to use the USB mic source directly).

### Samsung Dual BT MAC Addresses

Samsung phones use different Bluetooth MAC addresses for different protocols:
- Classic BT scanning: one MAC (e.g., `5C:xx:xx:xx:xx:xx`)
- RFCOMM connections (btservice): different MAC (e.g., `9C:xx:xx:xx:xx:xx`)

This is normal behavior but can be confusing when debugging BT pairing issues.

## Building

### Android App

Requirements: Android SDK, JDK 17

```bash
# macOS with Homebrew
export JAVA_HOME="/opt/homebrew/opt/openjdk@17"
export ANDROID_HOME="$HOME/Library/Android/sdk"
cd /path/to/MicStream
./gradlew assembleDebug
```

The APK will be at `app/build/outputs/apk/debug/app-debug.apk`.

### Pi Setup

#### Option 1: Pre-built Image (Recommended)

Flash a pre-built image to your SD card:

- **Pi 3B:** [v1.0 Release](https://github.com/vteckz/MicStream/releases/tag/v1.0)
- **Pi 4:** [v1.1 Release](https://github.com/vteckz/MicStream/releases/tag/v1.1)

```bash
xz -d -c crankshaft-micstream-pi4.img.xz | sudo dd of=/dev/sdX bs=4M status=progress
```

#### Option 2: Automated Setup Script

Flash a stock CrankshaftNG image, boot the Pi, SSH in, then run:

```bash
curl -sL https://raw.githubusercontent.com/vteckz/MicStream/master/pi/setup.sh | sudo bash
```

The script auto-detects Pi 3 vs Pi 4 and applies the appropriate config (overclock, HDMI sink, BT settings).

#### Option 3: Manual Setup

Deploy the configs and scripts in `pi/` to their respective locations:

```
pi/config/etc/fstab          → /etc/fstab
pi/config/etc/pulse/system.pa → /etc/pulse/system.pa
pi/config/etc/hostapd/hostapd.conf → /etc/hostapd/hostapd.conf
pi/config/etc/dnsmasq.conf   → /etc/dnsmasq.conf
pi/config/boot/config.txt    → /boot/config.txt
pi/config/boot/crankshaft/*  → /boot/crankshaft/
pi/scripts/*                 → /home/pi/
pi/systemd/*                 → /etc/systemd/system/
```

After deploying:
```bash
# Fix BT persistence (critical)
sudo umount /tmp/bluetooth 2>/dev/null
sudo rm -f /var/lib/bluetooth  # remove symlink if exists
sudo mkdir -p /var/lib/bluetooth
sudo chmod 700 /var/lib/bluetooth

# Enable custom services
sudo systemctl enable aa-remote aa-clock-monitor udp-mic-receiver bt-watchdog
sudo systemctl daemon-reload
```

## Hardware

Supported boards:
- **Raspberry Pi 3B** (BCM2837, 1GB RAM)
- **Raspberry Pi 4** (BCM2711, 1GB+ RAM)

Other requirements:
- **HDMI display/car stereo** with audio passthrough
- **Android phone** with Android Auto support
- USB power supply (2.5A+ for Pi 3, 3A+ for Pi 4)
- (Recommended) **USB microphone or USB sound card with mic** - needed for call uplink audio (other party hearing you). Android blocks mic streaming during calls.
- The Pi 4's built-in BCM43455 Bluetooth supports mSBC wideband (16kHz) call audio via the sco_enhancer.

## Network Topology

```
Phone ──── BT ────► Pi (B8:27:EB:xx:xx:xx)
  │                   │
  └── WiFi (client) ──┘ AP: CRANKSHAFT-NG
                         192.168.254.1/28
     Phone gets DHCP:    192.168.254.2-14

     Ports:
       TCP 5000 ← Android Auto stream
       UDP 8000 ← Mic audio (phone → Pi)
       UDP 8001 ← Touch events (phone → Pi)
```

## License

The CrankshaftNG scripts and configs are based on [CrankshaftNG](https://github.com/nicka-car/crankshaft) by nicka-car.
The aasdk and OpenAuto source code are from their respective upstream projects.
Custom scripts and the MicStream Android app are provided as-is.

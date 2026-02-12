# MicStream + CrankshaftNG Wireless Android Auto

A complete wireless Android Auto head unit system built on a Raspberry Pi 3B running [CrankshaftNG](https://github.com/nicka-car/crankshaft), with a companion Android app for microphone streaming and remote touchpad control.

## Overview

This project turns a Raspberry Pi 3B into a fully wireless Android Auto head unit with HDMI output. The phone connects via Bluetooth for the initial handshake, then switches to WiFi for the Android Auto data stream. Audio output goes through HDMI to the car stereo.

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
│  Android Phone  │     WiFi (AP)       │  Raspberry Pi 3B     │
│  (Samsung)      │◄───────────────────►│  CrankshaftNG        │
│                 │                     │                      │
│  MicStream App  │──UDP:8000 (mic)───►│  udp_mic_receiver.py │
│                 │──UDP:8001 (touch)──►│  aa_remote.py        │
│                 │                     │                      │
│                 │     AA TCP:5000     │  OpenAuto (autoapp)  │
│                 │◄───────────────────►│        │             │
└─────────────────┘                     │        ▼ HDMI        │
                                        │  ┌──────────┐       │
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
| `aa_clock_monitor.sh` | CPU governor manager - sets `performance` (1400MHz) when AA is connected, `ondemand` when idle, `powersave` on thermal throttle. |
| `bt_watchdog.sh` | Monitors BT connection to phone - restarts OpenAuto when phone disconnects so it returns to the waiting screen. |
| `aa_autolaunch.py` | (Experimental) Auto-taps the media button when AA connects to open Spotify. |
| `bt_restore.sh` | (Disabled) Legacy BT pairing restore from backup tar. |
| `bt_backup_monitor.sh` | (Disabled) Legacy BT pairing backup to `/boot`. |

### Pi Systemd Services (`pi/systemd/`)

Key custom services:
- `btservice.service` - BT RFCOMM server for AA wireless handshake
- `openauto.service` - OpenAuto (Android Auto) display server
- `aa-remote.service` - Virtual touchscreen UDP receiver
- `udp-mic-receiver.service` - Mic audio UDP receiver
- `aa-clock-monitor.service` - CPU clock management
- `bt-watchdog.service` - BT disconnect handler
- `hotspot.service` - WiFi AP (hostapd + dnsmasq)

### Pi Configs (`pi/config/`)

| File | Description |
|------|-------------|
| `boot/config.txt` | RPi boot config - HDMI settings, overclock (1400MHz/192MB GPU) |
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

**Problem:** Pi 3B was sluggish running AA at default clocks.

**Fix:**
- Overclocked to 1400MHz with `over_voltage=2`, 500MHz SDRAM, 192MB GPU memory
- Dynamic clock management: full speed when AA is connected, ondemand when idle, throttle on high temps

**Files:**
- `pi/config/boot/config.txt` (overclock settings)
- `pi/scripts/aa_clock_monitor.sh`

### 6. WiFi AP Configuration

The Pi runs a WiFi access point that the phone connects to for the AA data stream:
- **SSID:** `CRANKSHAFT-NG`
- **Security:** WPA2-PSK
- **Default password:** `1234567890` (change in `hostapd.conf`)
- **Subnet:** 192.168.254.0/28 (DHCP range .2-.14)
- **Pi IP:** 192.168.254.1

## Known Issues

### btservice WPA2_ENTERPRISE Bug

The `btservice` component (which handles BT-to-WiFi handshake for wireless AA) hardcodes `WPA2_ENTERPRISE` as the WiFi security mode in its protobuf response, but the actual AP uses `WPA2-PSK` (personal). This means on a completely fresh pairing, the phone may fail to auto-connect to WiFi.

**Workaround:** After first BT pairing, manually connect to the `CRANKSHAFT-NG` WiFi network on the phone. Once saved, it will auto-connect on subsequent sessions.

**Root cause:** `openauto-src/src/btservice/AndroidBluetoothServer.cpp` line 172-173 hardcodes `WPA2_ENTERPRISE` instead of `WPA2_PERSONAL` (value 5 in `WifiSecurityMode.proto`).

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

The Pi runs CrankshaftNG (a Raspberry Pi distro for Android Auto). The configs and scripts in `pi/` should be deployed to their respective locations on the Pi:

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

- **Raspberry Pi 3B** (BCM2837, 1GB RAM)
- **HDMI display/car stereo** with audio passthrough
- **Android phone** with Android Auto support
- USB power supply (2.5A+ recommended for stable overclock)

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

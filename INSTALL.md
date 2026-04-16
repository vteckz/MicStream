# MicStream Install Guide

A step-by-step guide to get wireless Android Auto running in your car. No coding or command line needed — just follow the steps.

**Time required:** About 30–45 minutes (most of it waiting for downloads and flashing).

---

## What You Need

### Hardware
- **Raspberry Pi 3B or Pi 4** (Pi 4 recommended — better performance)
- **SD card**, 16 GB or bigger (Class 10 / A1 speed)
- **USB power supply** (2.5A for Pi 3, 3A for Pi 4 — the official Pi charger is ideal)
- **HDMI cable** to connect the Pi to your car screen or monitor
- **Android phone** that supports Android Auto
- **SD card reader** for your computer (most laptops have a slot; otherwise use a USB reader)
- *(Optional but recommended)* **USB microphone** — needed if you want people to hear you during phone calls

### Software (free downloads)
- **Balena Etcher** — the tool that writes the system onto the SD card
  https://etcher.balena.io/
- The **MicStream image file** (the "operating system" for the Pi) — link below in Step 1

---

## Part 1: Flash the SD Card

This copies the MicStream system onto your SD card so the Pi can boot from it.

### Step 1 — Download the image

Go to the MicStream releases page and download the right image for your Pi:

- **If you have a Pi 4:** download `crankshaft-micstream-pi4.img.xz` from v1.1
  https://github.com/vteckz/MicStream/releases/tag/v1.1

- **If you have a Pi 3B:** download the image from v1.0
  https://github.com/vteckz/MicStream/releases/tag/v1.0

The file is about 1.4 GB. It will take a few minutes to download.

You do **not** need to unzip the `.xz` file — Balena Etcher handles that automatically.

### Step 2 — Install Balena Etcher

Download and install from https://etcher.balena.io/. It works on Windows, Mac, and Linux.

### Step 3 — Insert your SD card

Plug the SD card into your computer's card reader. If Windows or macOS pops up a dialog asking you to "format" or "initialize" the card, **click Cancel / Ignore**.

### Step 4 — Flash the image

1. Open **Balena Etcher**
2. Click **"Flash from file"** and select the `.img.xz` file you downloaded
3. Click **"Select target"** and choose your SD card
   > ⚠️ Double-check you picked the right drive. Etcher will erase everything on the selected drive.
4. Click **"Flash!"**
5. Wait. It takes 5–15 minutes. Etcher will show progress and then verify the write.
6. When it says "Flash Complete!" you can close Etcher and remove the SD card.

---

## Part 2: First Boot

### Step 5 — Set up the hardware

1. Put the SD card into the slot on the underside of the Pi
2. Plug the HDMI cable from the Pi into your car screen (or a monitor for testing)
3. Plug in the power supply **last**

The Pi will boot. First boot takes **2–3 minutes** and you may see the screen flicker or show some text. That's normal.

When you see the **CrankshaftNG / OpenAuto waiting screen** (a dark screen saying "Waiting for Android Auto" or similar), the Pi is ready.

---

## Part 3: Install the Phone App

The **MicStream app** runs on your phone. It streams your phone's microphone to the Pi and gives you a remote touchpad to control Android Auto.

### Step 6 — Install the APK on your phone

1. On your phone, download the MicStream APK from the same GitHub releases page as above (look for `app-debug.apk`)
2. Open the file after it downloads
3. Android will warn you about installing from an unknown source — tap **"Settings"** → enable **"Allow from this source"** → go back and tap **Install**
4. Open the app once to confirm it works. It will ask for:
   - **Microphone permission** → Allow
   - **Notification permission** → Allow
   - **Location permission** (used by Android for WiFi scanning) → Allow

---

## Part 4: Pair Your Phone

### Step 7 — Bluetooth pairing

1. On your phone, open **Settings → Bluetooth**
2. Tap **"Scan"** or **"Pair new device"**
3. Look for a device called **`CRANKSHAFT-<something>`** in the list
4. Tap it to pair. Confirm the pairing code matches on both the phone and the Pi screen, then tap **Pair** on both.

### Step 8 — Android Auto

1. Open **Android Auto** on your phone (you may need to install it from the Play Store if you haven't used it before)
2. In Android Auto settings, enable **"Add new cars to Android Auto"** (some phones call this "Developer settings" — tap the version number 10 times to unlock it)
3. Your phone should now offer to start Android Auto on the Pi. Tap **Yes / Start**.

The Pi will show the Android Auto home screen on your car display. 🎉

---

## Part 5: Use the Remote Touchpad

Because your car screen probably isn't a touchscreen, you control Android Auto using the MicStream app on your phone.

### Step 9 — Open MicStream

1. Open the **MicStream** app on your phone
2. Tap **Start** — this begins streaming mic audio and activates the touchpad
3. The touchpad area in the app acts as a virtual mouse for the car screen. Drag your finger to move, tap to click.
4. The **Home**, **Back**, and **scroll** buttons work like the Android Auto buttons.

---

## Everyday Use (after first-time setup)

Once the initial pairing is done, everyday use is automatic:

1. **Get in the car, start the engine** — the Pi powers on with your car's accessory power
2. **Phone auto-connects** via Bluetooth within 10–20 seconds
3. **Android Auto starts** automatically on the car screen
4. **Open MicStream** on your phone for mic/touch control

---

## Troubleshooting

### The Pi screen stays black
- Check the HDMI cable is plugged in **before** powering on the Pi
- Try a different HDMI port on your car screen
- Make sure the SD card is fully inserted

### "Waiting for Android Auto" never disappears
- On your phone, **forget the Bluetooth pairing** and re-pair
- Make sure Android Auto is installed on your phone from the Play Store
- Turn WiFi **off and on** on your phone after Bluetooth pairs

### Google Assistant doesn't hear me / no mic input
- Make sure the MicStream app is running (tap **Start**)
- Check the app has microphone permission (Settings → Apps → MicStream → Permissions)
- The app must stay in the foreground or as a persistent notification — don't swipe it away

### People can't hear me on phone calls
This is a known Android limitation — Android silences the mic during calls. Plug a **USB microphone** into the Pi to fix this (see the hardware list above).

### Bluetooth disconnects every reboot
This was a bug in the original CrankshaftNG and is already fixed in the MicStream image. If you're still seeing it, you may have flashed the wrong image — re-check you downloaded the MicStream version, not a plain CrankshaftNG image.

### I need more help
- The full technical README is in the project: [README.md](README.md)
- Post an issue on GitHub: https://github.com/vteckz/MicStream/issues

---

## Quick Reference

| Thing | Value |
|---|---|
| Pi WiFi hotspot name | `CRANKSHAFT-NG` |
| Pi WiFi password | `1234567890` |
| Pi IP on its own WiFi | `192.168.254.1` |
| First boot time | 2–3 minutes |
| Default SSH login (if needed) | `pi` / `raspberry` |

Keep this guide handy the first couple of times — once you've done it, the whole setup takes about 10 seconds every time you get in the car.

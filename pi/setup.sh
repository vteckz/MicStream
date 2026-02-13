#!/bin/bash
#
# MicStream + CrankshaftNG Setup Script
# Applies all modifications to a fresh CrankshaftNG install
#
# Usage: Flash CrankshaftNG to SD card, boot, SSH in, then run:
#   curl -sL https://raw.githubusercontent.com/vteckz/MicStream/master/pi/setup.sh | sudo bash
#
# Or clone the repo and run:
#   git clone https://github.com/vteckz/MicStream.git
#   cd MicStream/pi && sudo bash setup.sh
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_URL="https://raw.githubusercontent.com/vteckz/MicStream/master/pi"

echo "========================================"
echo " MicStream + CrankshaftNG Setup"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash setup.sh)"
    exit 1
fi

# Detect Pi model
PI_MODEL=$(cat /proc/device-tree/model 2>/dev/null || echo "Unknown")
echo "Detected: $PI_MODEL"

if echo "$PI_MODEL" | grep -qi "Pi 4"; then
    PI_VER=4
    echo "WARNING: Pi 4 support is experimental."
    echo "         The OMX video backend needs porting to GStreamer."
    echo "         See: https://github.com/vteckz/MicStream/issues/1"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi
elif echo "$PI_MODEL" | grep -qi "Pi 5"; then
    echo "ERROR: Pi 5 is not yet supported."
    echo "       See: https://github.com/vteckz/MicStream/issues/1"
    exit 1
elif echo "$PI_MODEL" | grep -qi "Pi 3"; then
    PI_VER=3
    echo "Pi 3 detected - full support."
else
    PI_VER=3
    echo "WARNING: Unknown Pi model, assuming Pi 3 compatible."
fi
echo ""

# Helper to download or copy file
install_file() {
    local src="$1"
    local dst="$2"
    local mode="${3:-644}"

    if [ -f "$SCRIPT_DIR/$src" ]; then
        cp "$SCRIPT_DIR/$src" "$dst"
    else
        curl -sL "$REPO_URL/$src" -o "$dst"
    fi
    chmod "$mode" "$dst"
    echo "  Installed: $dst"
}

# =============================================
# 1. Fix Bluetooth persistence (CRITICAL)
# =============================================
echo "[1/7] Fixing Bluetooth persistence..."

# Unmount ramfs bluetooth if mounted
if mount | grep -q '/tmp/bluetooth'; then
    umount /tmp/bluetooth 2>/dev/null || true
fi

# Comment out ramfs bluetooth mount in fstab
if grep -q '^ramfs.*\/tmp\/bluetooth' /etc/fstab; then
    sed -i 's|^ramfs\(.*\/tmp\/bluetooth\)|#ramfs\1|' /etc/fstab
    echo "  Commented out ramfs /tmp/bluetooth in /etc/fstab"
fi

# Remove symlink and create real directory
if [ -L /var/lib/bluetooth ]; then
    rm -f /var/lib/bluetooth
    echo "  Removed /var/lib/bluetooth symlink"
fi
mkdir -p /var/lib/bluetooth
chmod 700 /var/lib/bluetooth
chown root:root /var/lib/bluetooth
echo "  Created persistent /var/lib/bluetooth"

# =============================================
# 2. Install scripts
# =============================================
echo ""
echo "[2/7] Installing scripts..."

install_file "scripts/aa_remote.py" "/home/pi/aa_remote.py" "755"
install_file "scripts/udp_mic_receiver.py" "/home/pi/udp_mic_receiver.py" "755"
install_file "scripts/aa_clock_monitor.sh" "/home/pi/aa_clock_monitor.sh" "755"
install_file "scripts/bt_watchdog.sh" "/home/pi/bt_watchdog.sh" "755"
install_file "scripts/aa_autolaunch.py" "/home/pi/aa_autolaunch.py" "755"

chown pi:pi /home/pi/aa_remote.py /home/pi/udp_mic_receiver.py \
    /home/pi/aa_clock_monitor.sh /home/pi/bt_watchdog.sh /home/pi/aa_autolaunch.py

# =============================================
# 3. Install systemd services
# =============================================
echo ""
echo "[3/7] Installing systemd services..."

install_file "systemd/aa-remote.service" "/etc/systemd/system/aa-remote.service"
install_file "systemd/udp-mic-receiver.service" "/etc/systemd/system/udp-mic-receiver.service"
install_file "systemd/aa-clock-monitor.service" "/etc/systemd/system/aa-clock-monitor.service"
install_file "systemd/bt-watchdog.service" "/etc/systemd/system/bt-watchdog.service"
install_file "systemd/aa-autolaunch.service" "/etc/systemd/system/aa-autolaunch.service"

systemctl daemon-reload
systemctl enable aa-remote aa-clock-monitor udp-mic-receiver bt-watchdog 2>/dev/null
echo "  Enabled: aa-remote, aa-clock-monitor, udp-mic-receiver, bt-watchdog"

# =============================================
# 4. Configure PulseAudio (mic sink + HDMI)
# =============================================
echo ""
echo "[4/7] Configuring PulseAudio..."

PA_CONF="/etc/pulse/system.pa"
if [ -f "$PA_CONF" ]; then
    # Add android mic sink if not present
    if ! grep -q 'android_mic' "$PA_CONF"; then
        cat >> "$PA_CONF" << 'PAEOF'

# Android mic stream (UDP receiver feeds into this sink)
load-module module-null-sink sink_name=android_mic sink_properties=device.description=AndroidMicSink rate=16000 channels=1 format=s16le
load-module module-remap-source source_name=android_mic_source master=android_mic.monitor source_properties=device.description=Android-Phone-Mic
set-default-source android_mic_source
PAEOF
        echo "  Added android_mic sink to PulseAudio"
    fi

    # Set HDMI as default audio output
    if [ "$PI_VER" = "3" ]; then
        HDMI_SINK="alsa_output.platform-bcm2835_audio.digital-stereo"
    elif [ "$PI_VER" = "4" ]; then
        HDMI_SINK="alsa_output.platform-fef00700.hdmi.hdmi-stereo"
    fi

    if ! grep -q 'set-default-sink' "$PA_CONF"; then
        echo "set-default-sink $HDMI_SINK" >> "$PA_CONF"
        echo "  Set default sink to HDMI ($HDMI_SINK)"
    fi
fi

# =============================================
# 5. Apply boot config overclocks
# =============================================
echo ""
echo "[5/7] Applying boot config..."

BOOT_CONFIG="/boot/config.txt"
if [ -f "$BOOT_CONFIG" ]; then
    # Make boot partition writable
    mount -o remount,rw /boot 2>/dev/null || true

    if [ "$PI_VER" = "3" ]; then
        # Pi 3 overclock
        if ! grep -q 'arm_freq=1400' "$BOOT_CONFIG"; then
            cat >> "$BOOT_CONFIG" << 'BOOTEOF'

# MicStream overclock settings (Pi 3)
arm_freq=1400
over_voltage=2
sdram_freq=500
gpu_mem=192

# HDMI display fix
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=16
hdmi_drive=2
disable_overscan=1
config_hdmi_boost=4
BOOTEOF
            echo "  Applied Pi 3 overclock (1400MHz) and HDMI settings"
        fi
    elif [ "$PI_VER" = "4" ]; then
        if ! grep -q 'arm_freq=2000' "$BOOT_CONFIG"; then
            cat >> "$BOOT_CONFIG" << 'BOOTEOF'

# MicStream settings (Pi 4)
arm_freq=2000
over_voltage=6
gpu_mem=256

# HDMI display fix
hdmi_force_hotplug=1
hdmi_drive=2
disable_overscan=1
BOOTEOF
            echo "  Applied Pi 4 overclock (2000MHz) and HDMI settings"
        fi
    fi

    mount -o remount,ro /boot 2>/dev/null || true
fi

# =============================================
# 6. Configure WiFi hotspot
# =============================================
echo ""
echo "[6/7] Checking WiFi hotspot config..."

HOSTAPD_CONF="/etc/hostapd/hostapd.conf"
if [ -f "$HOSTAPD_CONF" ]; then
    echo "  hostapd.conf exists - SSID: $(grep '^ssid=' $HOSTAPD_CONF | cut -d= -f2)"
    echo "  Default password: $(grep '^wpa_passphrase=' $HOSTAPD_CONF | cut -d= -f2)"
    echo "  Change password in $HOSTAPD_CONF if needed"
else
    echo "  WARNING: hostapd.conf not found - WiFi AP may not work"
fi

# =============================================
# 7. Pi 4 specific adjustments
# =============================================
echo ""
echo "[7/7] Platform-specific adjustments..."

if [ "$PI_VER" = "4" ]; then
    # Pi 4 doesn't need hciattach (BT is USB, not UART)
    if systemctl is-enabled hciattach 2>/dev/null | grep -q enabled; then
        systemctl disable hciattach 2>/dev/null || true
        echo "  Disabled hciattach (not needed on Pi 4)"
    fi
    echo "  NOTE: Pi 4 video output requires OMX->GStreamer port"
    echo "        See: https://github.com/vteckz/MicStream/issues/1"
else
    echo "  Pi 3 - no additional adjustments needed"
fi

# =============================================
# Done
# =============================================
echo ""
echo "========================================"
echo " Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Pair your phone via Bluetooth:"
echo "     bluetoothctl"
echo "     > agent on"
echo "     > default-agent"
echo "     > scan on"
echo "     > pair <PHONE_MAC>"
echo "     > trust <PHONE_MAC>"
echo ""
echo "  2. On first connect, manually join the"
echo "     CRANKSHAFT-NG WiFi from your phone"
echo "     (workaround for WPA2 bug)"
echo ""
echo "  3. Install MicStream app on your phone"
echo "     (build from app/ or download APK)"
echo ""
echo "  4. Reboot: sudo reboot"
echo ""
echo "  After reboot, phone should auto-connect."
echo "========================================"

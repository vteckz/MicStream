#!/bin/bash
#
# Create a flashable SD card image from a running CrankshaftNG Pi
# Run this from your Mac/Linux machine (NOT on the Pi)
#
# Usage: bash create-image.sh <pi-ip> <output-name>
# Example: bash create-image.sh 192.168.1.113 crankshaft-micstream-pi3b
#
set -e

PI_HOST="${1:-192.168.1.113}"
PI_USER="pi"
PI_PASS="raspberry"
OUTPUT_NAME="${2:-crankshaft-micstream-pi3b}"
OUTPUT_FILE="${OUTPUT_NAME}.img.xz"

echo "========================================"
echo " CrankshaftNG Image Creator"
echo "========================================"
echo ""
echo "Pi: ${PI_USER}@${PI_HOST}"
echo "Output: ${OUTPUT_FILE}"
echo ""

# Check sshpass
if ! command -v sshpass &>/dev/null; then
    echo "ERROR: sshpass required. Install with: brew install sshpass"
    exit 1
fi

# Check Pi is reachable
echo "Checking Pi is reachable..."
if ! sshpass -p "$PI_PASS" ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${PI_USER}@${PI_HOST} 'echo OK' 2>/dev/null; then
    echo "ERROR: Cannot reach Pi at ${PI_HOST}"
    exit 1
fi

# Get SD card info
echo "Getting SD card info..."
SD_INFO=$(sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=no ${PI_USER}@${PI_HOST} \
    'lsblk -b -o NAME,SIZE /dev/mmcblk0 | head -2 | tail -1' 2>/dev/null)
SD_SIZE=$(echo "$SD_INFO" | awk '{print $2}')
SD_SIZE_GB=$(echo "scale=1; $SD_SIZE / 1073741824" | bc)
echo "SD card size: ${SD_SIZE_GB}GB"

# Get used space
USED_INFO=$(sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=no ${PI_USER}@${PI_HOST} \
    'df -B1 / | tail -1' 2>/dev/null)
echo "Disk usage: $(echo "$USED_INFO" | awk '{print $3}' | numfmt --to=iec 2>/dev/null || echo 'unknown')"

echo ""
echo "This will stream the entire SD card (${SD_SIZE_GB}GB) over SSH"
echo "and compress with xz. This may take 30-60+ minutes."
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi

echo ""
echo "Imaging... (this will take a while)"
echo "Start time: $(date)"

# Stream dd over SSH, compress locally
sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=no ${PI_USER}@${PI_HOST} \
    'sudo dd if=/dev/mmcblk0 bs=4M status=none' 2>/dev/null \
    | pv -s "$SD_SIZE" 2>/dev/null \
    | xz -T0 -3 > "$OUTPUT_FILE"

echo ""
echo "End time: $(date)"
echo "Image created: ${OUTPUT_FILE}"
echo "Size: $(ls -lh "$OUTPUT_FILE" | awk '{print $5}')"
echo ""
echo "To generate checksum:"
echo "  shasum -a 256 ${OUTPUT_FILE}"
echo ""
echo "To flash to a new SD card:"
echo "  xz -d -c ${OUTPUT_FILE} | sudo dd of=/dev/sdX bs=4M status=progress"
echo ""
echo "To upload as GitHub release:"
echo "  gh release create v1.0 ${OUTPUT_FILE} --title 'CrankshaftNG + MicStream v1.0'"

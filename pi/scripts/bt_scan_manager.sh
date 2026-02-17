#!/bin/bash
#
# BT Scan Manager - reduces BCM43455 BT/WiFi radio contention during AA streaming
#
# The BCM43455's single radio handles both WiFi and Bluetooth. When BT ISCAN+PSCAN
# are active, the radio periodically switches to BT frequencies to listen for devices,
# causing 50-80ms WiFi latency spikes that stutter AA video and audio.
#
# This script disables ISCAN+PSCAN while AA is streaming (detected by TCP port 5000),
# and re-enables them when AA disconnects so the phone can reconnect.
#

logger "bt-scan-manager: Started"

while true; do
  AA_ACTIVE=false
  if ss -tn 2>/dev/null | grep -q ':5000'; then
    AA_ACTIVE=true
  fi

  CURRENT_SCAN=$(sudo hciconfig hci0 2>/dev/null | grep 'UP')

  if $AA_ACTIVE; then
    # AA active - enforce noscan every cycle (bluetoothd may re-enable)
    if echo "$CURRENT_SCAN" | grep -qE 'PSCAN|ISCAN'; then
      sudo hciconfig hci0 noscan 2>/dev/null
    fi
  else
    # AA not active - ensure PISCAN is on for reconnection
    if ! echo "$CURRENT_SCAN" | grep -q 'PSCAN'; then
      sudo hciconfig hci0 piscan 2>/dev/null
      logger "bt-scan-manager: AA idle - enabled PISCAN"
    fi
  fi

  sleep 3
done

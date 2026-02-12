#!/bin/bash
# Bluetooth Watchdog - restarts openauto when phone disconnects
PHONE_MAC="5C:DC:49:80:85:75"
CHECK_INTERVAL=3
was_connected=false

logger -t bt-watchdog "Bluetooth watchdog started, monitoring $PHONE_MAC"

while true; do
    if hcitool con 2>/dev/null | grep -qi "$PHONE_MAC"; then
        if [ "$was_connected" = false ]; then
            logger -t bt-watchdog "Phone connected"
            was_connected=true
        fi
    else
        if [ "$was_connected" = true ]; then
            logger -t bt-watchdog "Phone disconnected - restarting openauto"
            was_connected=false
            sudo systemctl restart openauto
        fi
    fi
    sleep $CHECK_INTERVAL
done

#!/bin/bash

# Install safe-upgrade service on first boot
if [ -f /boot/safe-upgrade.service ] && [ ! -f /boot/safe-upgrade.done ]; then
    mount -o remount,rw /
    cp /boot/safe-upgrade.service /etc/systemd/system/safe-upgrade.service
    chmod +x /boot/safe-upgrade.sh
    systemctl daemon-reload
    systemctl enable safe-upgrade
    systemctl start safe-upgrade &
fi

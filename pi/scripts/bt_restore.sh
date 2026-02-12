
#!/bin/bash
BACKUP=/boot/crankshaft/bt-pairings-backup.tar

# Just restore the backup - bluetooth hasn't started yet
if [ -f "$BACKUP" ]; then
    mkdir -p /tmp/bluetooth
    tar xf "$BACKUP" -C / 2>/dev/null
    logger -t bt-persist "BT pairings restored before bluetooth start"
else
    logger -t bt-persist "No BT backup found"
fi

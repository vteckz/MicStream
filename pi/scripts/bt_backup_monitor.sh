
#!/bin/bash
BACKUP=/boot/crankshaft/bt-pairings-backup.tar
BT_DIR=/tmp/bluetooth
ADAPTER=B8:27:EB:66:87:83
while true; do
    sleep 60
    if [ -d "$BT_DIR/$ADAPTER" ]; then
        COUNT=$(ls -d "$BT_DIR/$ADAPTER"/??:??:??:??:??:?? 2>/dev/null | wc -l)
        if [ "$COUNT" -gt 0 ]; then
            tar cf "$BACKUP" -C / tmp/bluetooth 2>/dev/null
        fi
    fi
done

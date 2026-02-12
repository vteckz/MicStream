
#!/usr/bin/env python3
"""Auto-launch Spotify view when Android Auto connects.

Monitors for AA TCP connection on port 5000, then sends a touch tap
to the media button on the AA nav bar via the aa_remote UDP protocol.
"""
import socket
import struct
import subprocess
import time
import sys

TOUCH_PORT = 8001  # aa_remote.py UDP port
# AA 480p (800x480) bottom nav bar - media/music button
# In 1024x768 touch coordinate space:
# Media button is ~2nd icon from left in the bottom nav bar
MEDIA_BTN_X = 346
MEDIA_BTN_Y = 736

def send_tap(x, y):
    """Send a tap via UDP to aa_remote.py."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for cmd in [ord('D'), ord('U')]:
        buf = struct.pack('<Bhh', cmd, x, y)
        sock.sendto(buf, ('127.0.0.1', TOUCH_PORT))
        if cmd == ord('D'):
            time.sleep(0.05)
    sock.close()

def is_aa_connected():
    """Check if AA is streaming (TCP port 5000 has an established connection)."""
    try:
        out = subprocess.check_output(
            ['ss', '-tn', 'state', 'established', 'sport', '=', ':5000'],
            timeout=5
        ).decode()
        return 'ESTAB' in out or '5000' in out
    except Exception:
        return False

def main():
    print("aa_autolaunch: waiting for Android Auto connection...")
    was_connected = False
    
    while True:
        connected = is_aa_connected()
        
        if connected and not was_connected:
            # AA just connected - wait for video to fully render
            print("aa_autolaunch: AA connected, waiting 10s for UI to load...")
            time.sleep(10)
            
            # Verify still connected
            if is_aa_connected():
                print(f"aa_autolaunch: tapping media button at ({MEDIA_BTN_X}, {MEDIA_BTN_Y})")
                send_tap(MEDIA_BTN_X, MEDIA_BTN_Y)
                # If first tap didn't work, try again after a moment
                time.sleep(2)
                send_tap(MEDIA_BTN_X, MEDIA_BTN_Y)
                print("aa_autolaunch: done")
            else:
                print("aa_autolaunch: AA disconnected before tap")
        
        was_connected = connected
        time.sleep(3)

if __name__ == '__main__':
    main()

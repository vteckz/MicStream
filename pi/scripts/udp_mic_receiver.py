#!/usr/bin/env python3
"""UDP Mic Receiver - receives audio from MicStream Android app and feeds to PulseAudio."""
import socket
import subprocess
import sys
import os
import time

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
SINK = 'android_mic'

print(f'UDP mic receiver listening on port {PORT}')

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', PORT))
print(f'Listening on 0.0.0.0:{PORT}')

pacat = None

def start_pacat():
    global pacat
    env = os.environ.copy()
    env['PULSE_SERVER'] = '/var/run/pulse/native'
    try:
        pacat = subprocess.Popen(
            ['pacat', '--playback', '--device=' + SINK,
             '--rate=16000', '--channels=1', '--format=s16le',
             '--latency-msec=50'],
            stdin=subprocess.PIPE,
            env=env
        )
        print(f'pacat started (pid {pacat.pid})')
    except Exception as e:
        print(f'Failed to start pacat: {e}')
        pacat = None

start_pacat()

try:
    while True:
        data, addr = sock.recvfrom(4096)
        if data and pacat and pacat.poll() is None:
            try:
                pacat.stdin.write(data)
                pacat.stdin.flush()
            except (BrokenPipeError, OSError):
                print('pacat died, restarting in 1s...')
                time.sleep(1)
                start_pacat()
        elif pacat is None or pacat.poll() is not None:
            time.sleep(1)
            start_pacat()
except KeyboardInterrupt:
    pass
finally:
    sock.close()
    if pacat:
        pacat.terminate()

#!/usr/bin/env python3
"""Virtual touchscreen for Android Auto remote control via UDP."""
import socket
import struct
import ctypes
import os
import fcntl
import time

# uinput constants
UINPUT_MAX_NAME_SIZE = 80
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_ABSBIT = 0x40045567
UI_SET_PROPBIT = 0x4004556e
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502

# Event types
EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03
SYN_REPORT = 0x00

# Abs axes
ABS_X = 0x00
ABS_Y = 0x01
ABS_MT_SLOT = 0x2f
ABS_MT_TRACKING_ID = 0x39
ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36

# Keys
BTN_TOUCH = 0x14a
INPUT_PROP_DIRECT = 0x01

# Screen dimensions
SCREEN_W = 1024
SCREEN_H = 768

def make_uinput_user_dev(name, absinfo):
    """Create uinput_user_dev struct."""
    buf = bytearray(80 + 8 + 4 + 64*4*4)
    name_bytes = name.encode()[:79]
    buf[:len(name_bytes)] = name_bytes
    struct.pack_into('<HHHH', buf, 80, 0x06, 0x1234, 0x5678, 1)
    for axis, (amin, amax) in absinfo.items():
        struct.pack_into('<i', buf, 92 + axis * 4, amax)
        struct.pack_into('<i', buf, 92 + 64*4 + axis * 4, amin)
    return bytes(buf)

def write_event(fd, etype, ecode, evalue):
    """Write input event."""
    t = time.time()
    sec = int(t)
    usec = int((t - sec) * 1000000)
    os.write(fd, struct.pack('<llHHi', sec, usec, etype, ecode, evalue))

def setup_uinput():
    fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_SYN)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_ABS)
    fcntl.ioctl(fd, UI_SET_KEYBIT, BTN_TOUCH)
    fcntl.ioctl(fd, UI_SET_ABSBIT, ABS_X)
    fcntl.ioctl(fd, UI_SET_ABSBIT, ABS_Y)
    fcntl.ioctl(fd, UI_SET_ABSBIT, ABS_MT_SLOT)
    fcntl.ioctl(fd, UI_SET_ABSBIT, ABS_MT_TRACKING_ID)
    fcntl.ioctl(fd, UI_SET_ABSBIT, ABS_MT_POSITION_X)
    fcntl.ioctl(fd, UI_SET_ABSBIT, ABS_MT_POSITION_Y)
    fcntl.ioctl(fd, UI_SET_PROPBIT, INPUT_PROP_DIRECT)

    absinfo = {
        ABS_X: (0, SCREEN_W - 1),
        ABS_Y: (0, SCREEN_H - 1),
        ABS_MT_SLOT: (0, 9),
        ABS_MT_TRACKING_ID: (0, 65535),
        ABS_MT_POSITION_X: (0, SCREEN_W - 1),
        ABS_MT_POSITION_Y: (0, SCREEN_H - 1),
    }

    dev = make_uinput_user_dev('aa-remote-touch', absinfo)
    os.write(fd, dev)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(0.5)
    print(f'Virtual touchscreen created ({SCREEN_W}x{SCREEN_H})')
    return fd

def handle_touch(fd, cmd, x, y):
    x = max(0, min(SCREEN_W - 1, x))
    y = max(0, min(SCREEN_H - 1, y))

    if cmd == ord('D'):
        write_event(fd, EV_ABS, ABS_MT_TRACKING_ID, 1)
        write_event(fd, EV_ABS, ABS_MT_POSITION_X, x)
        write_event(fd, EV_ABS, ABS_MT_POSITION_Y, y)
        write_event(fd, EV_ABS, ABS_X, x)
        write_event(fd, EV_ABS, ABS_Y, y)
        write_event(fd, EV_KEY, BTN_TOUCH, 1)
        write_event(fd, EV_SYN, SYN_REPORT, 0)
    elif cmd == ord('M'):
        write_event(fd, EV_ABS, ABS_MT_POSITION_X, x)
        write_event(fd, EV_ABS, ABS_MT_POSITION_Y, y)
        write_event(fd, EV_ABS, ABS_X, x)
        write_event(fd, EV_ABS, ABS_Y, y)
        write_event(fd, EV_SYN, SYN_REPORT, 0)
    elif cmd == ord('U'):
        write_event(fd, EV_ABS, ABS_MT_TRACKING_ID, -1)
        write_event(fd, EV_KEY, BTN_TOUCH, 0)
        write_event(fd, EV_SYN, SYN_REPORT, 0)

def main():
    PORT = 8001
    fd = setup_uinput()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', PORT))
    print(f'Listening for touch events on UDP port {PORT}')

    try:
        while True:
            data, addr = sock.recvfrom(64)
            if len(data) >= 5:
                cmd = data[0]
                x = struct.unpack('<H', data[1:3])[0]
                y = struct.unpack('<H', data[3:5])[0]
                handle_touch(fd, cmd, x, y)
    except KeyboardInterrupt:
        pass
    finally:
        fcntl.ioctl(fd, UI_DEV_DESTROY)
        os.close(fd)
        sock.close()

if __name__ == '__main__':
    main()

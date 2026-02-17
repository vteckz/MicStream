#!/usr/bin/env python3
"""
SCO Enhancer - Custom ofono audio agent with mSBC wideband support

Replaces PulseAudio's CVSD-only ofono audio agent with one that supports
mSBC (16kHz wideband), dramatically improving phone call audio quality.

Architecture:
  PulseAudio bluetooth disabled (no module-bluetooth-discover)
  ofono handles HFP profile registration with BlueZ exclusively
  This agent registers with ofono as HandsfreeAudioAgent with mSBC+CVSD
  On call: receives SCO fd, decodes mSBC via libsbc, pipes to PulseAudio

mSBC frame format (60 bytes):
  [01] [08/38/C8/F8] [AD ...SBC data...] [FF]
   H2 header (2B)     mSBC payload (57B)   pad

Requires: libsbc1, python3-dbus, python3-gi
"""

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import ctypes
import os
import sys
import select
import subprocess
import threading
import signal
import time
import logging

# Constants
OFONO_BUS = "org.ofono"
HF_AUDIO_MANAGER_IFACE = "org.ofono.HandsfreeAudioManager"
HF_AUDIO_AGENT_IFACE = "org.ofono.HandsfreeAudioAgent"

CODEC_CVSD = 0x01
CODEC_MSBC = 0x02

AGENT_PATH = "/org/micstream/sco_agent"

# mSBC H2 sync header sequence (HFP spec 5.7.2)
H2_FIRST_BYTE = 0x01
H2_SN_TABLE = [0x08, 0x38, 0xC8, 0xF8]
H2_SN_SET = set(H2_SN_TABLE)

# Frame sizes
MSBC_FRAME_SIZE = 57   # SBC payload per frame
MSBC_H2_SIZE = 2       # H2 header
MSBC_TOTAL = 60        # Total SCO packet size

# PulseAudio devices
PA_HDMI_SINK = "alsa_output.platform-bcm2835_audio.digital-stereo"
PA_MIC_SOURCE = "android_mic_source"

# libc recv for proper SCO SEQPACKET socket I/O
# (Python's os.read() returns empty on BT SCO sockets; recv() works correctly)
_libc = ctypes.CDLL("libc.so.6", use_errno=True)
_libc.recv.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
_libc.recv.restype = ctypes.c_ssize_t

_libc_getsockopt = _libc.getsockopt
_libc_getsockopt.argtypes = [
    ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint),
]
_libc_getsockopt.restype = ctypes.c_int

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s sco-enhancer: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("sco-enhancer")

import socket as _socket

def _sd_notify(msg):
    """Send systemd notify message (Type=notify readiness signal)."""
    addr = os.getenv("NOTIFY_SOCKET")
    if not addr:
        return
    sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_DGRAM)
    try:
        if addr[0] == '@':
            addr = '\0' + addr[1:]
        sock.connect(addr)
        sock.sendall(msg.encode())
    finally:
        sock.close()


def sco_recv(fd, bufsize):
    """recv() on SCO fd via libc - works where os.read() fails on SEQPACKET."""
    buf = ctypes.create_string_buffer(bufsize)
    n = _libc.recv(fd, buf, bufsize, 0)
    if n < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return buf.raw[:n]


# ─── libsbc ctypes bindings ───

class SbcStruct(ctypes.Structure):
    """Opaque sbc_t - allocate generously"""
    _fields_ = [("_data", ctypes.c_ubyte * 512)]


_libsbc = None


def _load_libsbc():
    global _libsbc
    try:
        _libsbc = ctypes.CDLL("libsbc.so.1")
    except OSError:
        log.error("libsbc.so.1 not found - mSBC unavailable")
        return False

    _libsbc.sbc_init_msbc.argtypes = [ctypes.POINTER(SbcStruct), ctypes.c_ulong]
    _libsbc.sbc_init_msbc.restype = ctypes.c_int

    _libsbc.sbc_finish.argtypes = [ctypes.POINTER(SbcStruct)]
    _libsbc.sbc_finish.restype = None

    _libsbc.sbc_decode.argtypes = [
        ctypes.POINTER(SbcStruct),
        ctypes.c_void_p, ctypes.c_size_t,
        ctypes.c_void_p, ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    _libsbc.sbc_decode.restype = ctypes.c_ssize_t

    _libsbc.sbc_encode.argtypes = [
        ctypes.POINTER(SbcStruct),
        ctypes.c_void_p, ctypes.c_size_t,
        ctypes.c_void_p, ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_ssize_t),
    ]
    _libsbc.sbc_encode.restype = ctypes.c_ssize_t

    _libsbc.sbc_get_frame_length.argtypes = [ctypes.POINTER(SbcStruct)]
    _libsbc.sbc_get_frame_length.restype = ctypes.c_size_t

    _libsbc.sbc_get_codesize.argtypes = [ctypes.POINTER(SbcStruct)]
    _libsbc.sbc_get_codesize.restype = ctypes.c_size_t

    log.info("Loaded libsbc.so.1 with mSBC support")
    return True


# ─── Audio handler ───

class ScoAudioHandler:
    """Handles bidirectional SCO audio for one call."""

    def __init__(self, fd, codec):
        self.fd = fd
        self.codec = codec
        self.running = False
        self._pa_play = None
        self._pa_rec = None
        self._rx_thread = None
        self._tx_thread = None
        self._decoder = None
        self._encoder = None

        if codec == CODEC_MSBC:
            self.rate = 16000
            self._init_msbc()
        else:
            self.rate = 8000

        codec_name = "mSBC (16kHz)" if codec == CODEC_MSBC else "CVSD (8kHz)"
        log.info("Audio handler: %s, rate=%d, fd=%d", codec_name, self.rate, fd)

    def _init_msbc(self):
        """Initialize mSBC encoder and decoder via libsbc."""
        if not _libsbc:
            log.error("Cannot init mSBC - libsbc not loaded")
            return

        self._decoder = SbcStruct()
        self._encoder = SbcStruct()
        _libsbc.sbc_init_msbc(ctypes.byref(self._decoder), 0)
        _libsbc.sbc_init_msbc(ctypes.byref(self._encoder), 0)

        frame_len = _libsbc.sbc_get_frame_length(ctypes.byref(self._decoder))
        codesize = _libsbc.sbc_get_codesize(ctypes.byref(self._decoder))
        log.info("mSBC init: frame_length=%d, codesize=%d bytes", frame_len, codesize)
        self._msbc_codesize = codesize  # PCM bytes needed per encode
        self._tx_sn = 0

    def start(self):
        """Start audio processing."""
        self.running = True

        # Kickstart the SCO data path: some BT controllers (BCM43455) don't
        # begin routing SCO data to the host until a write is attempted.
        # The write will fail (ENOTCONN) but triggers the controller's
        # SCO data routing. This mirrors what the diagnostic version did
        # accidentally - those early write attempts activated the data path.
        for attempt in range(5):
            try:
                os.write(self.fd, b'\x00' * 60)
                log.info("SCO kickstart write succeeded on attempt %d", attempt + 1)
                break
            except OSError as e:
                if e.errno == 107:  # ENOTCONN
                    time.sleep(0.05)
                    continue
                log.info("SCO kickstart write: errno=%d %s", e.errno, e.strerror)
                break
        else:
            log.info("SCO kickstart: all writes got ENOTCONN (expected)")

        # Check socket health
        try:
            err = ctypes.c_int(0)
            errlen = ctypes.c_uint(4)
            ret = _libc_getsockopt(
                self.fd, 1, 4,  # SOL_SOCKET=1, SO_ERROR=4
                ctypes.byref(err), ctypes.byref(errlen),
            )
            if ret == 0 and err.value != 0:
                log.warning("SCO socket error before start: errno=%d %s",
                            err.value, os.strerror(err.value))
            else:
                log.info("SCO socket healthy (SO_ERROR=0)")
        except Exception as e:
            log.warning("Could not check socket state: %s", e)

        # Playback: SCO → speakers (HDMI)
        self._pa_play = subprocess.Popen(
            [
                "paplay", "--raw",
                "--rate", str(self.rate),
                "--channels", "1",
                "--format", "s16le",
                "--device", PA_HDMI_SINK,
            ],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        # Mic capture: android_mic → SCO
        self._pa_rec = subprocess.Popen(
            [
                "parec", "--raw",
                "--rate", str(self.rate),
                "--channels", "1",
                "--format", "s16le",
                "--device", PA_MIC_SOURCE,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._rx_thread.start()
        self._tx_thread.start()
        log.info("Audio streams started (speakers=%s, mic=%s)", PA_HDMI_SINK, PA_MIC_SOURCE)

    def _rx_loop(self):
        """Read from SCO socket, decode, send to speakers."""
        frames_decoded = 0
        timeout_count = 0
        max_timeouts = 3  # Retry SCO link up to 3 times on timeout
        try:
            while self.running:
                # select() waits for SCO socket to be readable (also handles
                # the brief delay between NewConnection and actual SCO link-up)
                try:
                    readable, _, _ = select.select([self.fd], [], [], 1.0)
                except (ValueError, OSError) as e:
                    log.error("RX select() failed: %s", e)
                    break
                if not readable:
                    continue

                try:
                    data = sco_recv(self.fd, 1024)
                except OSError as e:
                    if e.errno == 11:  # EAGAIN
                        continue
                    if e.errno == 110:  # ETIMEDOUT
                        timeout_count += 1
                        if timeout_count <= max_timeouts:
                            log.warning("RX recv() timed out (%d/%d), retrying...",
                                        timeout_count, max_timeouts)
                            time.sleep(0.1)
                            continue
                        log.error("RX recv() timed out %d times, giving up", timeout_count)
                        break
                    log.error("RX recv() failed: errno=%d %s", e.errno, e)
                    break

                if not data:
                    continue  # SCO may return empty before data flows

                # Reset timeout counter once data starts flowing
                timeout_count = 0

                if frames_decoded == 0:
                    log.info("RX first packet: %d bytes, hex=%s",
                             len(data), data[:8].hex())

                if self.codec == CODEC_MSBC:
                    pcm = self._decode_msbc(data)
                else:
                    pcm = data  # CVSD: raw 8kHz s16le PCM

                if pcm and self._pa_play and self._pa_play.stdin:
                    try:
                        self._pa_play.stdin.write(pcm)
                        self._pa_play.stdin.flush()
                        frames_decoded += 1
                    except BrokenPipeError:
                        break
        except Exception as e:
            log.error("RX error: %s", e)
        finally:
            log.info("RX ended (%d frames decoded)", frames_decoded)

    def _tx_loop(self):
        """Read from mic, encode, send to SCO socket."""
        frames_encoded = 0
        write_errors = 0
        try:
            if self.codec == CODEC_MSBC and self._msbc_codesize:
                chunk_size = self._msbc_codesize
            else:
                chunk_size = 48  # CVSD: ~3ms of 8kHz audio

            # Wait briefly for parec to connect to PA source
            time.sleep(0.2)

            while self.running:
                if not self._pa_rec or not self._pa_rec.stdout:
                    break

                # Check if parec process died
                if self._pa_rec.poll() is not None:
                    log.warning("TX: parec exited (code=%d), mic unavailable",
                                self._pa_rec.returncode)
                    # Send silence to keep SCO link alive
                    silence = b'\x00' * chunk_size
                    while self.running:
                        if self.codec == CODEC_MSBC:
                            sco_data = self._encode_msbc(silence)
                        else:
                            sco_data = silence
                        if sco_data:
                            try:
                                os.write(self.fd, sco_data)
                            except OSError:
                                break
                        time.sleep(0.0075)  # ~7.5ms per mSBC frame
                    break

                pcm = self._pa_rec.stdout.read(chunk_size)
                if not pcm:
                    break

                if frames_encoded == 0:
                    log.info("TX first pcm: %d bytes, hex=%s",
                             len(pcm), pcm[:16].hex())

                if self.codec == CODEC_MSBC:
                    sco_data = self._encode_msbc(pcm)
                else:
                    sco_data = pcm

                if sco_data:
                    try:
                        os.write(self.fd, sco_data)
                        frames_encoded += 1
                    except OSError as e:
                        if e.errno == 107:  # ENOTCONN - socket not ready yet
                            time.sleep(0.01)
                            continue
                        if e.errno == 110:  # ETIMEDOUT
                            time.sleep(0.01)
                            continue
                        write_errors += 1
                        if write_errors <= 3:
                            log.error("TX write() failed: errno=%d %s", e.errno, e)
                        if write_errors > 10:
                            break
        except Exception as e:
            log.error("TX error: %s", e)
        finally:
            log.info("TX ended (%d frames encoded)", frames_encoded)

    def _decode_msbc(self, data):
        """Decode mSBC H2-framed data to PCM."""
        if not _libsbc or not self._decoder:
            return None

        results = []
        i = 0
        while i < len(data) - MSBC_H2_SIZE:
            # Scan for H2 sync: 0x01 followed by sequence byte
            if data[i] == H2_FIRST_BYTE and data[i + 1] in H2_SN_SET:
                payload_start = i + MSBC_H2_SIZE
                payload_end = payload_start + MSBC_FRAME_SIZE
                if payload_end > len(data):
                    break

                payload = bytes(data[payload_start:payload_end])

                out_buf = ctypes.create_string_buffer(512)
                written = ctypes.c_size_t(0)

                consumed = _libsbc.sbc_decode(
                    ctypes.byref(self._decoder),
                    payload, len(payload),
                    out_buf, len(out_buf),
                    ctypes.byref(written),
                )

                if consumed > 0 and written.value > 0:
                    results.append(out_buf.raw[:written.value])

                # Advance past frame (H2 + payload + padding byte)
                i = payload_end + 1
            else:
                i += 1

        return b"".join(results) if results else None

    def _encode_msbc(self, pcm):
        """Encode PCM to mSBC H2 frame."""
        if not _libsbc or not self._encoder:
            return None

        sbc_buf = ctypes.create_string_buffer(MSBC_FRAME_SIZE + 10)
        written = ctypes.c_ssize_t(0)

        consumed = _libsbc.sbc_encode(
            ctypes.byref(self._encoder),
            pcm, len(pcm),
            sbc_buf, len(sbc_buf),
            ctypes.byref(written),
        )

        if consumed <= 0 or written.value <= 0:
            return None

        # Build H2 frame
        frame = bytearray(MSBC_TOTAL)
        frame[0] = H2_FIRST_BYTE
        frame[1] = H2_SN_TABLE[self._tx_sn]
        self._tx_sn = (self._tx_sn + 1) % 4

        sbc_data = sbc_buf.raw[:written.value]
        end = min(2 + len(sbc_data), MSBC_TOTAL - 1)
        frame[2:end] = sbc_data[:end - 2]
        frame[MSBC_TOTAL - 1] = 0xFF  # padding

        return bytes(frame)

    def stop(self):
        """Stop audio processing and clean up."""
        self.running = False

        for proc in (self._pa_play, self._pa_rec):
            if proc:
                try:
                    if proc.stdin:
                        proc.stdin.close()
                    proc.terminate()
                except Exception:
                    pass

        try:
            os.close(self.fd)
        except OSError:
            pass

        if self.codec == CODEC_MSBC and _libsbc:
            for codec_state in (self._decoder, self._encoder):
                if codec_state:
                    try:
                        _libsbc.sbc_finish(ctypes.byref(codec_state))
                    except Exception:
                        pass

        log.info("Audio handler stopped")


# ─── D-Bus agent ───

class HfAudioAgent(dbus.service.Object):
    """ofono HandsfreeAudioAgent with mSBC support."""

    def __init__(self, bus):
        super().__init__(bus, AGENT_PATH)
        self._handler = None

    @dbus.service.method(
        HF_AUDIO_AGENT_IFACE,
        in_signature="ohy",
        out_signature="",
    )
    def NewConnection(self, card_path, sco_fd, codec):
        codec_name = "mSBC" if codec == CODEC_MSBC else "CVSD"
        log.info("NewConnection: card=%s codec=%s", card_path, codec_name)

        if self._handler:
            self._handler.stop()

        # take() transfers fd ownership from D-Bus to us
        if hasattr(sco_fd, "take"):
            raw_fd = sco_fd.take()
        else:
            raw_fd = int(sco_fd)

        # CRITICAL: ofono uses BT_DEFER_SETUP on its SCO listening socket.
        # The kernel accepts incoming SCO into BT_CONNECT2 state (deferred).
        # We MUST call recv() to trigger sco_conn_defer_accept() in the kernel,
        # which sends HCI Accept SCO Connection to the BT controller.
        # Without this, the socket stays in BT_CONNECT2 and all I/O gets ENOTCONN.
        buf = ctypes.create_string_buffer(256)
        n = _libc.recv(raw_fd, buf, 256, 0)
        if n == 0:
            log.info("SCO deferred accept triggered, waiting for HCI connection...")
        elif n > 0:
            log.info("SCO accept: got %d bytes immediately", n)
        else:
            err = ctypes.get_errno()
            log.warning("SCO accept recv: errno=%d (%s)", err, os.strerror(err))

        # Wait for HCI Connection Complete event (typically <50ms)
        time.sleep(0.2)

        fd = raw_fd
        log.info("SCO fd=%d (codec=%s)", fd, codec_name)

        self._handler = ScoAudioHandler(fd, codec)
        self._handler.start()

    @dbus.service.method(
        HF_AUDIO_AGENT_IFACE,
        in_signature="",
        out_signature="",
    )
    def Release(self):
        log.info("Agent released by ofono")
        if self._handler:
            self._handler.stop()
            self._handler = None


# ─── Main ───

def _set_hci_voice_transparent():
    """Set HCI voice setting to Transparent (0x0063) for mSBC passthrough.
    Without this, the BT controller decodes SCO audio as CVSD instead of
    passing raw mSBC frames to the host."""
    try:
        subprocess.run(
            ["hcitool", "cmd", "0x03", "0x0026", "0x63", "0x00"],
            capture_output=True, timeout=5,
        )
        log.info("HCI voice setting: 0x0063 (Transparent)")
    except Exception as e:
        log.warning("Failed to set HCI voice: %s", e)


def main():
    if not _load_libsbc():
        log.warning("Continuing without mSBC - only CVSD available")

    _set_hci_voice_transparent()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    agent = HfAudioAgent(bus)

    manager = None
    for attempt in range(30):
        try:
            manager = dbus.Interface(
                bus.get_object(OFONO_BUS, "/"),
                HF_AUDIO_MANAGER_IFACE,
            )
            codecs = dbus.Array(
                [dbus.Byte(CODEC_CVSD), dbus.Byte(CODEC_MSBC)],
                signature="y",
            )
            manager.Register(AGENT_PATH, codecs)
            log.info("Registered with ofono (codecs: CVSD + mSBC)")
            break
        except dbus.exceptions.DBusException as e:
            err = str(e)
            if "ServiceUnknown" in err:
                log.info("Waiting for ofono... (%d/30)", attempt + 1)
                time.sleep(2)
            elif "Busy" in err or "InUse" in err:
                log.error(
                    "Another agent already registered. "
                    "Ensure module-bluetooth-discover is disabled in "
                    "/etc/pulse/system.pa"
                )
                sys.exit(1)
            else:
                log.error("Registration failed: %s", e)
                sys.exit(1)
    else:
        log.error("ofono not available after 60s")
        sys.exit(1)

    loop = GLib.MainLoop()

    def shutdown(signum, frame):
        log.info("Shutting down...")
        try:
            manager.Unregister(AGENT_PATH)
        except Exception:
            pass
        if agent._handler:
            agent._handler.stop()
        loop.quit()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info("SCO Enhancer running - waiting for calls...")

    try:
        loop.run()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()

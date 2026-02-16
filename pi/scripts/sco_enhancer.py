#!/usr/bin/env python3
"""
SCO Audio Enhancer v5 - jitter buffer only, no processing.

Just buffer the audio to absorb irregular SCO delivery timing,
then pass it straight through.
"""
import sys
import time

SAMPLE_RATE = 8000
FRAME_SIZE = 2
CHUNK_SAMPLES = 160  # 20ms
CHUNK_BYTES = CHUNK_SAMPLES * FRAME_SIZE

JITTER_MS = 300
JITTER_SAMPLES = SAMPLE_RATE * JITTER_MS // 1000


def main():
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer

    # Fill jitter buffer
    jitter_buf = bytearray()
    sys.stderr.write(f"[enhancer v5] Filling {JITTER_MS}ms jitter buffer (passthrough)...\n")
    sys.stderr.flush()

    t0 = time.time()
    while len(jitter_buf) < JITTER_SAMPLES * FRAME_SIZE:
        data = stdin.read(CHUNK_BYTES)
        if not data:
            sys.stderr.write("[enhancer v5] stdin closed during fill\n")
            return
        jitter_buf.extend(data)

    sys.stderr.write(f"[enhancer v5] Buffer filled in {time.time()-t0:.1f}s. Pure passthrough.\n")
    sys.stderr.flush()

    # Output jitter buffer as-is
    stdout.write(bytes(jitter_buf))
    stdout.flush()

    chunks = 1
    while True:
        data = stdin.read(CHUNK_BYTES)
        if not data:
            break

        try:
            stdout.write(data)
            stdout.flush()
        except BrokenPipeError:
            break

        chunks += 1
        if chunks % 1000 == 0:
            sys.stderr.write(f"[enhancer v5] {chunks} chunks passed through\n")
            sys.stderr.flush()

    sys.stderr.write(f"[enhancer v5] Done. {chunks} chunks\n")


if __name__ == '__main__':
    main()

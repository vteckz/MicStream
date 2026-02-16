#!/bin/bash
#
# Call Audio Router v4 - two-stage loopback via null-sink
#
# Usage:
#   call_audio.sh start   - Switch to HFP + route to HDMI
#   call_audio.sh stop    - Stop everything + restore A2DP
#

BT_ADDR="5C_DC_49_80_85_75"
BT_CARD="bluez_card.${BT_ADDR}"
BT_SOURCE="bluez_source.${BT_ADDR}.headset_audio_gateway"
BT_SINK="bluez_sink.${BT_ADDR}.headset_audio_gateway"
HDMI_SINK="alsa_output.platform-bcm2835_audio.digital-stereo"

export PULSE_SERVER=/run/pulse/native

kill_pipeline() {
    killall -q parec aplay python3 2>/dev/null
    sleep 0.3
    for p in $(pgrep -f "sco_enhancer|parec.*call_capture|aplay.*plughw.*8000"); do
        kill -9 $p 2>/dev/null
    done
    for mod in $(pactl list modules short 2>/dev/null | grep -E "call_capture|call_tx|headset_audio_gateway" | awk '{print $1}'); do
        pactl unload-module $mod 2>/dev/null
    done
}

start_call() {
    echo "[call] Cleaning up..."
    kill_pipeline

    echo "[call] Switching to HFP..."
    pactl set-card-profile "$BT_CARD" headset_audio_gateway
    sleep 1

    if ! pactl list sources short | grep -q "$BT_SOURCE"; then
        echo "[call] ERROR: BT source not found"
        return 1
    fi

    echo "[call] Setting up direct loopback..."

    # Direct: BT source -> HDMI sink
    pactl load-module module-loopback \
        source="$BT_SOURCE" sink="$HDMI_SINK" \
        latency_msec=200 adjust_time=3 \
        source_dont_move=true sink_dont_move=true

    # TX: silence to BT sink to keep SCO link alive
    pactl load-module module-null-sink sink_name=call_tx \
        sink_properties=device.description="CallTX" rate=8000 channels=1
    pactl load-module module-loopback \
        source=call_tx.monitor sink="$BT_SINK" \
        latency_msec=100 \
        source_dont_move=true sink_dont_move=true

    echo "[call] Direct loopback running (BT -> HDMI)"
}

stop_call() {
    echo "[call] Stopping..."
    kill_pipeline
    sleep 1
    echo "[call] Restoring A2DP..."
    pactl set-card-profile "$BT_CARD" a2dp_source
    echo "[call] Done"
}

case "$1" in
    start) start_call ;;
    stop)  stop_call ;;
    *)     echo "Usage: $0 {start|stop}" ;;
esac

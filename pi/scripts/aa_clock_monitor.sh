#!/bin/bash
# Android Auto Clock Monitor - adjusts CPU governor based on AA connection and temperature
PERF_GOV="performance"
IDLE_GOV="ondemand"
SAFE_GOV="powersave"
TEMP_WARN=75
TEMP_CRIT=80
CHECK_INTERVAL=5
GOV_PATH="/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
current_gov=""

set_governor() {
    local gov=$1
    if [ "$gov" != "$current_gov" ]; then
        echo "$gov" > $GOV_PATH
        current_gov=$gov
        local freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq)
        local temp=$(vcgencmd measure_temp | grep -oP '[0-9.]+')
        logger -t aa-clock "Governor -> $gov (freq: ${freq}kHz, temp: ${temp}C)"
    fi
}

is_aa_active() {
    ss -tn state established '( sport = :5000 )' 2>/dev/null | grep -q 5000
}

get_temp() {
    vcgencmd measure_temp | grep -oP '[0-9.]+' | cut -d. -f1
}

logger -t aa-clock "Clock monitor started"

while true; do
    temp=$(get_temp)
    if [ "$temp" -ge $TEMP_CRIT ]; then
        set_governor $SAFE_GOV
    elif is_aa_active; then
        if [ "$temp" -lt $TEMP_WARN ]; then
            set_governor $PERF_GOV
        else
            set_governor $IDLE_GOV
        fi
    else
        set_governor $IDLE_GOV
    fi
    sleep $CHECK_INTERVAL
done

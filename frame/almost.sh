#!/bin/sh
# Almost: the Frame side. Runs on the reMarkable 2 (BusyBox sh).
#
#   almost.sh arm     set the RTC wake alarm (called just before every sleep)
#   almost.sh wake    called just after every resume; if the alarm woke us,
#                     show today's Plate and go back to sleep
#   almost.sh mount   lay current.png over the stock sleep image (at boot)
#   almost.sh show    pick today's Plate, restart the notes app, sleep
#
# Test mode: put a number of seconds in $HOME_DIR/test-interval and the Frame
# wakes that often, rotating through every Plate, instead of nightly at 00:05.

set -u
HOME_DIR=/home/root/almost
PLATES=$HOME_DIR/plates
STATE=$HOME_DIR/state
CURRENT=$HOME_DIR/current.png
SLEEP_IMG=/usr/share/remarkable/suspended.png
RTC=/sys/class/rtc/rtc0
TZ_HOME=Australia/Melbourne
WAKE_AT="00:05"
CRITICAL_PERCENT=5
LOG=$HOME_DIR/almost.log

mkdir -p "$STATE"
log() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }

melbourne_date() { TZ=$TZ_HOME date -d "@$1" +%F; }

next_wake_epoch() {
    now=$(date +%s)
    if [ -s "$HOME_DIR/test-interval" ]; then
        echo $((now + $(cat "$HOME_DIR/test-interval")))
        return
    fi
    # Tomorrow's Melbourne date, then 00:05 on that date in Melbourne time.
    # Going via the date string keeps this right across daylight-saving changes.
    tomorrow=$(melbourne_date $((now + 86400)))
    TZ=$TZ_HOME date -d "$tomorrow $WAKE_AT" +%s
}

arm() {
    at=$(next_wake_epoch)
    echo 0 > $RTC/wakealarm
    echo "$at" > $RTC/wakealarm
    echo "$at" > "$STATE/alarm"
    log "armed for $(TZ=$TZ_HOME date -d "@$at" '+%F %T %Z')"
}

ensure_mount() {
    [ -f "$CURRENT" ] || return 1
    grep -q " $SLEEP_IMG " /proc/mounts || mount --bind "$CURRENT" "$SLEEP_IMG"
}

choose_plate() {
    battery=$(cat /sys/class/power_supply/max77818_battery/capacity)
    if [ "$battery" -le $CRITICAL_PERCENT ] && [ -f "$PLATES/charge-me.png" ]; then
        echo "$PLATES/charge-me.png"
        return
    fi
    if [ -s "$HOME_DIR/test-interval" ]; then
        n=$(cat "$STATE/counter" 2>/dev/null || echo 0)
        echo $((n + 1)) > "$STATE/counter"
        set -- $(ls "$PLATES"/[0-9]*.png 2>/dev/null)
        [ $# -gt 0 ] || return 1
        shift $((n % $#))
        echo "$1"
        return
    fi
    today=$(melbourne_date "$(date +%s)" | tr -d -)
    # Today's Plate, or else the latest one before today (it will carry the
    # Offline Mark, baked in by the Studio).
    best=""
    for p in "$PLATES"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].png; do
        [ -f "$p" ] || continue
        d=$(basename "$p" .png | tr -d -)
        [ "$d" -gt "$today" ] && continue
        best=$p
    done
    [ -n "$best" ] && echo "$best"
}

press_power() {
    # struct input_event: 8-byte time, u16 type, u16 code, s32 value. KEY_POWER=116.
    for v in '\001' '\0'; do
        printf "\0\0\0\0\0\0\0\0\001\0\164\0${v}\0\0\0" > /dev/input/event0
        printf '\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0' > /dev/input/event0
        sleep 0.2
    done
}

show() {
    plate=$(choose_plate) || plate=""
    if [ -n "$plate" ]; then
        cp "$plate" "$CURRENT.tmp" && cat "$CURRENT.tmp" > "$CURRENT" && rm -f "$CURRENT.tmp"
        log "showing $(basename "$plate")"
    else
        log "no Plate for today; keeping the current one"
    fi
    ensure_mount
    # The notes app only reads the sleep image at startup.
    systemctl restart xochitl
    sleep 20
    press_power
}

wake() {
    alarm=$(cat "$STATE/alarm" 2>/dev/null || echo 0)
    now=$(date +%s)
    if [ "$now" -ge $((alarm - 5)) ]; then
        log "woken by alarm"
        # Leave the sleep hook promptly; do the work as its own service.
        systemctl --no-block start almost-show.service
    else
        log "woken by hand; staying awake"
    fi
}

case "${1:-}" in
    arm) arm ;;
    wake) wake ;;
    mount) ensure_mount ;;
    show) show ;;
    *) echo "usage: $0 arm|wake|mount|show" >&2; exit 2 ;;
esac

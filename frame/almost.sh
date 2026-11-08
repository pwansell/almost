#!/bin/sh
# Almost: the Frame side. Runs on the reMarkable 2 (BusyBox sh).
#
#   almost.sh arm     set the RTC wake alarm (called just before every sleep)
#   almost.sh wake    called just after every resume; if the alarm woke us,
#                     show today's Plate and go back to sleep
#   almost.sh mount   lay current.png over the stock sleep image (at boot)
#   almost.sh show    fetch new Plates, pick today's, restart the notes app, sleep
#   almost.sh refresh the same without fetching (charge checks, unplugging)
#   almost.sh fetch   just fetch new Plates from the Studio
#   almost.sh sleep   press the power key now (sleep, showing the Plate)
#   almost.sh resleep go back to sleep unless a computer or SSH session is
#                     connected (then check again later); used after any wake
#                     that wasn't the alarm
#
# Charging: while on a charger the Frame also wakes every 30 minutes until the
# battery is full, then shows the day's Charged copy (the Charged Mark) until
# it's unplugged.
#
# The Studio's address lives in $HOME_DIR/frame.conf as
#   STUDIO_URL=https://<worker>/frame/<FRAME_TOKEN>
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
RETRY_AT="06:00"
RESLEEP_AFTER=120   # seconds awake after a non-alarm wake (button, cable)
CHARGE_CHECK=1800   # seconds between battery checks while charging
BATTERY=/sys/class/power_supply/max77818_battery
CHARGER=/sys/class/power_supply/max77818-charger
STUDIO_URL=""
[ -f "$HOME_DIR/frame.conf" ] && . "$HOME_DIR/frame.conf"

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
    today=$(melbourne_date "$now")
    # If tonight's fetch failed, try once more at 06:00 before giving up.
    if [ -f "$STATE/fetch-failed" ]; then
        retry=$(TZ=$TZ_HOME date -d "$today $RETRY_AT" +%s)
        if [ "$now" -lt "$retry" ]; then
            rm -f "$STATE/fetch-failed"
            echo "$retry"
            return
        fi
    fi
    tomorrow=$(melbourne_date $((now + 86400)))
    TZ=$TZ_HOME date -d "$tomorrow $WAKE_AT" +%s
}

download() {  # url dest
    wget -q -T 20 -O "$2" "$1" 2>/dev/null || curl -fsS -m 20 -o "$2" "$1" 2>/dev/null
}

fetch() {
    [ -n "$STUDIO_URL" ] || { log "no STUDIO_URL; skipping fetch"; return 0; }
    mkdir -p "$PLATES"
    battery=$(cat /sys/class/power_supply/max77818_battery/capacity)
    list=$STATE/manifest.txt
    # Wi-Fi can take minutes to come back after waking: the first joins often
    # fail, and each failure makes wpa_supplicant back off for longer. Wait up
    # to 5 minutes, and every minute tell it to skip the backoff and try again.
    tries=0
    until ip=$(wifi_ip) && download "$STUDIO_URL/manifest.txt?battery=$battery&ip=$ip" "$list.tmp"; do
        tries=$((tries + 1))
        if [ $((tries % 6)) = 0 ] && [ -z "$(wifi_ip)" ] && command -v wpa_cli >/dev/null; then
            wpa_cli -i wlan0 bssid_ignore clear >/dev/null 2>&1 ||
                wpa_cli -i wlan0 blacklist clear >/dev/null 2>&1  # older name
            wpa_cli -i wlan0 enable_network all >/dev/null 2>&1
            wpa_cli -i wlan0 reassociate >/dev/null 2>&1
            log "fetch: no Wi-Fi yet; asked it to try again"
        fi
        if [ $tries -ge 30 ]; then
            log "fetch failed: Studio unreachable after 5 minutes"
            touch "$STATE/fetch-failed"
            return 1
        fi
        sleep 10
    done
    mv "$list.tmp" "$list"
    got=0
    while read -r sha file; do
        case "$file" in *[!A-Za-z0-9.-]*|"") continue ;; esac
        [ -f "$PLATES/$file" ] && [ "$(sha256sum "$PLATES/$file" | cut -d' ' -f1)" = "$sha" ] && continue
        if download "$STUDIO_URL/$file" "$PLATES/$file.tmp" &&
           [ "$(sha256sum "$PLATES/$file.tmp" | cut -d' ' -f1)" = "$sha" ]; then
            mv "$PLATES/$file.tmp" "$PLATES/$file"
            got=$((got + 1))
        else
            rm -f "$PLATES/$file.tmp"
            log "fetch: bad download for $file"
            touch "$STATE/fetch-failed"
        fi
    done < "$list"
    # Drop Plates the Studio no longer lists (past days).
    for p in "$PLATES"/*.png; do
        [ -f "$p" ] || continue
        grep -q "  $(basename "$p")\$" "$list" || rm -f "$p"
    done
    [ -f "$STATE/fetch-failed" ] || log "fetched $got new Plate(s)"
}

on_charger() { [ "$(cat $CHARGER/online 2>/dev/null)" = 1 ]; }

battery_full() {
    [ "$(cat $BATTERY/status 2>/dev/null)" = Full ] || [ "$(cat $BATTERY/capacity)" -ge 100 ]
}

showing() { cat "$STATE/showing" 2>/dev/null; }

arm() {
    had_failed_fetch=no
    [ -f "$STATE/fetch-failed" ] && had_failed_fetch=yes
    at=$(next_wake_epoch)
    kind=nightly
    # Charging and not yet showing the Charged Mark: check back in 30 minutes,
    # unless the next nightly wake (or the 06:00 retry) comes sooner.
    if [ ! -s "$HOME_DIR/test-interval" ] && [ $had_failed_fetch = no ] && on_charger; then
        case "$(showing)" in
            *-charged.png) ;;
            *) check=$(($(date +%s) + CHARGE_CHECK))
               [ "$check" -lt "$at" ] && { at=$check; kind=charge; } ;;
        esac
    fi
    echo "$kind" > "$STATE/alarm-kind"
    echo 0 > $RTC/wakealarm
    echo "$at" > $RTC/wakealarm
    echo "$at" > "$STATE/alarm"
    log "armed for $(TZ=$TZ_HOME date -d "@$at" '+%F %T %Z') ($kind)"
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
        set -- $(ls "$PLATES"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].png 2>/dev/null)
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
    [ -n "$best" ] || return 1
    # Full on the charger: the same day's copy with the Charged Mark.
    if on_charger && battery_full && [ -f "${best%.png}-charged.png" ]; then
        best="${best%.png}-charged.png"
    fi
    echo "$best"
}

press_power() {
    # struct input_event: 8-byte time, u16 type, u16 code, s32 value. KEY_POWER=116.
    for v in '\001' '\0'; do
        printf "\0\0\0\0\0\0\0\0\001\0\164\0${v}\0\0\0" > /dev/input/event0
        printf '\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0' > /dev/input/event0
        sleep 0.2
    done
}

show() {  # show [nofetch]
    # The notes app suspends the tablet within seconds of an unattended wake,
    # which froze the first nightly fetch mid-download. Keep it stopped until
    # the new Plate is in place; the restart below brings it back.
    systemctl stop xochitl
    if [ "${1:-}" != nofetch ]; then
        rm -f "$STATE/fetch-failed"
        fetch || true
    fi
    plate=$(choose_plate) || plate=""
    if [ -n "$plate" ]; then
        cp "$plate" "$CURRENT.tmp" && cat "$CURRENT.tmp" > "$CURRENT" && rm -f "$CURRENT.tmp"
        basename "$plate" > "$STATE/showing"
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

wifi_ip() {  # the tablet's Wi-Fi address, so we can SSH in when it's mounted
    ip -4 addr show wlan0 2>/dev/null | awk '/inet /{split($2, a, "/"); print a[1]; exit}'
    return 0
}

ssh_session_open() {  # an established connection on port 22 (hex 0016)
    awk '$2 ~ /:0016$/ && $4 == "01" {found=1} END {exit !found}' \
        /proc/net/tcp /proc/net/tcp6 2>/dev/null
}

computer_connected() {
    # A computer on the USB cable "configures" the tablet as a device; a plain
    # charger never does, so charging in the frame still sleeps on the Plate.
    grep -qx configured /sys/class/udc/*/state 2>/dev/null
}

schedule_resleep() {
    # Each request gets its own unit; only the newest one acts (see resleep).
    id=$(date +%s)$$
    echo "$id" > "$STATE/resleep"
    systemd-run --quiet --unit="almost-resleep-$id" --on-active=$RESLEEP_AFTER \
        /home/root/almost/almost.sh resleep "$id"
}

resleep() {
    [ "${1:-}" = "$(cat "$STATE/resleep" 2>/dev/null)" ] || return 0
    # A computer on USB, or someone SSHed in over Wi-Fi: stay awake and look
    # again later; once they're done it drifts back to sleep.
    if computer_connected || ssh_session_open; then
        schedule_resleep
        return
    fi
    # Plugged in full, or unplugged with the Charged Mark up: change Plates.
    if [ ! -s "$HOME_DIR/test-interval" ] && want=$(choose_plate) &&
       [ "$(basename "$want")" != "$(showing)" ]; then
        show nofetch
        return
    fi
    log "back to sleep"
    press_power
}

wake() {
    alarm=$(cat "$STATE/alarm" 2>/dev/null || echo 0)
    now=$(date +%s)
    if [ "$now" -ge $((alarm - 5)) ]; then
        kind=$(cat "$STATE/alarm-kind" 2>/dev/null || echo nightly)
        log "woken by alarm ($kind)"
        # Leave the sleep hook promptly; do the work as its own service.
        if [ "$kind" = charge ]; then
            systemd-run --quiet --unit="almost-refresh-$now" /home/root/almost/almost.sh refresh
        else
            systemctl --no-block start almost-show.service
        fi
    else
        # The button, or plugging/unplugging the cable. Stay up briefly (long
        # enough to SSH in over USB), then sleep showing the Plate again.
        log "woken by hand or cable; sleeping again in ${RESLEEP_AFTER}s unless a computer or SSH is connected"
        schedule_resleep
    fi
}

case "${1:-}" in
    arm) arm ;;
    wake) wake ;;
    mount) ensure_mount ;;
    show) show ;;
    refresh) show nofetch ;;
    fetch) fetch ;;
    resleep) resleep "${2:-}" ;;
    sleep) press_power ;;
    *) echo "usage: $0 arm|wake|mount|show|refresh|fetch|resleep|sleep" >&2; exit 2 ;;
esac

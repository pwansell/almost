#!/bin/sh
# Install the Frame side onto a reMarkable 2 over SSH.
#   frame/install.sh [host]        default host 10.11.99.1 (USB)
# Needs the SSH key ~/.ssh/id_ed25519_almost on the tablet.
set -eu
HOST=${1:-10.11.99.1}
KEY=~/.ssh/id_ed25519_almost
DIR=$(cd "$(dirname "$0")" && pwd)
SSH="ssh -i $KEY -o BatchMode=yes root@$HOST"

$SSH 'mkdir -p /home/root/almost/plates /home/root/almost/backup'
scp -q -i "$KEY" -o BatchMode=yes "$DIR/almost.sh" root@"$HOST":/home/root/almost/almost.sh
scp -q -i "$KEY" -o BatchMode=yes "$DIR/system-sleep-almost" root@"$HOST":/lib/systemd/system-sleep/almost
scp -q -i "$KEY" -o BatchMode=yes "$DIR/almost-show.service" "$DIR/almost-mount.service" root@"$HOST":/etc/systemd/system/
$SSH '
set -e
chmod +x /home/root/almost/almost.sh /lib/systemd/system-sleep/almost
[ -f /home/root/almost/backup/suspended.png ] || cp /usr/share/remarkable/suspended.png /home/root/almost/backup/
# Replace any earlier overlay with one backed by current.png.
while grep -q " /usr/share/remarkable/suspended.png " /proc/mounts; do umount /usr/share/remarkable/suspended.png; done
[ -f /home/root/almost/current.png ] || cp /usr/share/remarkable/suspended.png /home/root/almost/current.png
systemctl daemon-reload
systemctl enable almost-mount.service
# restart, not start: the oneshot stays "active" after the unmount above,
# so start would do nothing and leave the stock sleep image showing. Its
# "boot" step also restarts the notes app so it reads the new image.
systemctl restart almost-mount.service
grep -q " /usr/share/remarkable/suspended.png " /proc/mounts
echo installed
'

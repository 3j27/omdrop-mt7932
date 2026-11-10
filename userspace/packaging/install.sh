#!/bin/bash
# Install the omdrop userspace package (run as root).
set -e
HERE=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
SRC=$(cd "$HERE/.." && pwd)
LIB=/usr/local/lib/omdrop

install -d "$LIB" "$LIB/elements" /etc/omdrop /etc/systemd/system /etc/systemd/user /usr/share/applications
install -m755 "$SRC/omdrop-recv" "$SRC/omdrop-daemon" "$SRC/omdrop-bringup.sh" \
    "$SRC/omdrop-adv.py" "$SRC/omdrop-peerbody.py" "$SRC/omdrop-sync.py" \
    "$SRC/omdrop-send" "$LIB/"
install -m644 "$SRC"/elements/*.bin "$LIB/elements/"
install -m755 "$SRC/omdrop" /usr/local/bin/omdrop
[ -f /etc/omdrop/config ] || install -m644 "$HERE/config.example" /etc/omdrop/config
install -m644 "$HERE/omdrop-awdl.service" /etc/systemd/system/
install -m644 "$HERE/omdrop-receive.service" /etc/systemd/user/
install -m644 "$HERE/omdrop.desktop" /usr/share/applications/

systemctl daemon-reload
systemctl enable --now omdrop-awdl

if [ -n "${SUDO_USER:-}" ]; then
    uid=$(id -u "$SUDO_USER")
    sudo -u "$SUDO_USER" XDG_RUNTIME_DIR=/run/user/$uid systemctl --user daemon-reload || true
    sudo -u "$SUDO_USER" XDG_RUNTIME_DIR=/run/user/$uid systemctl --user enable --now omdrop-receive || true
fi
update-desktop-database /usr/share/applications 2>/dev/null || true

echo "omdrop installed. Edit /etc/omdrop/config, then: omdrop status"

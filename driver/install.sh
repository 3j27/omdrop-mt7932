#!/bin/bash
# Install the built mt7932 module as an updates/ override.
set -e
TREE=${1:?usage: install.sh /path/to/linux}
KO="$TREE/drivers/net/wireless/mediatek/mt7932/mt7932-fullmac.ko"
REL=$(uname -r)
[[ $EUID == 0 ]] || { echo "run as root" >&2; exit 1; }
[[ -f "$KO" ]] || { echo "missing $KO; run build.sh first" >&2; exit 1; }
install -Dm644 "$KO" "/usr/lib/modules/$REL/updates/mt7932-fullmac.ko"
depmod -a "$REL"
if command -v mkinitcpio >/dev/null; then
    mkinitcpio -P
fi
if command -v limine-mkinitcpio >/dev/null; then
    limine-mkinitcpio linux-aurora || true
fi
echo "installed for $REL; reboot to activate"
echo "rollback: rm /usr/lib/modules/$REL/updates/mt7932-fullmac.ko && depmod -a && mkinitcpio -P && reboot"

#!/bin/bash
# Install the omdrop relay on the Studio (run as root).
set -e
HERE=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
LIB=/usr/local/libexec/omdrop
ULA=${OMDROP_ULA:?set OMDROP_ULA to the advertised IPv6}
LL=${OMDROP_LL:-}

: "${OMDROP_TARGET_IP:?set OMDROP_TARGET_IP to the Neo LAN address}"
install -d "$LIB"
install -m755 "$HERE/airdrop-relay.py" "$LIB/airdrop-relay.py"
install -m755 "$HERE/relay-start.sh" "$LIB/relay-start.sh"
sed -e "s/__TARGET_IP__/$OMDROP_TARGET_IP/" -e "s/__ULA__/$ULA/" -e "s/__LL__/$LL/" "$HERE/com.omdrop.relay.plist" \
    > /Library/LaunchDaemons/com.omdrop.relay.plist
chmod 644 /Library/LaunchDaemons/com.omdrop.relay.plist

# The advertised address must be local to the Mac's network stack.
if ! ifconfig lo0 | grep -q "${ULA%/*}"; then
    ifconfig lo0 inet6 "$ULA/128"
fi
# Best effort: awdl0 only exists once AWDL has started.
if [ -n "$LL" ] && ifconfig awdl0 >/dev/null 2>&1 && ! ifconfig awdl0 | grep -q "${LL%/*}"; then
    ifconfig awdl0 inet6 "$LL/64"
fi

launchctl bootout system /Library/LaunchDaemons/com.omdrop.relay.plist 2>/dev/null || true
launchctl bootstrap system /Library/LaunchDaemons/com.omdrop.relay.plist 2>/dev/null || \
    launchctl load -w /Library/LaunchDaemons/com.omdrop.relay.plist
echo "omdrop relay installed; log: /var/log/omdrop-relay.log"

#!/bin/bash
# launchd entry point: make the advertised address local, then relay.
set -u
ULA=${OMDROP_ULA:?set OMDROP_ULA}
LL=${OMDROP_LL:-}

if ! ifconfig lo0 | grep -q "${ULA%/*}"; then
    ifconfig lo0 inet6 "$ULA/128"
fi
if [ -n "$LL" ] && ifconfig awdl0 >/dev/null 2>&1 && ! ifconfig awdl0 | grep -q "${LL%/*}"; then
    ifconfig awdl0 inet6 "$LL/64" 2>/dev/null || true
fi
exec /usr/bin/python3 /usr/local/libexec/omdrop/airdrop-relay.py

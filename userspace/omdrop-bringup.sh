#!/bin/bash
# One full AWDL bring-up.  $1 is the peer's AWDL MAC (optional).
set -u
LIB=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
PEER=${1:-}
C=(python3 /usr/lib/omdrop-mtk/mtk_awdl_cmd.py -i wlan0)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

"${C[@]}" disable 2>/dev/null
sleep 1
"${C[@]}" destroy 2>/dev/null
for i in $(seq 20); do [ -e /sys/class/net/awdl0 ] || break; sleep 0.25; done
"${C[@]}" create
for i in $(seq 20); do [ -e /sys/class/net/awdl0/address ] && break; sleep 0.25; done
ip link set awdl0 up
sleep 1
"${C[@]}" disable

for f in seq16-153 psf110 el-psf afm-1; do
    "${C[@]}" raw 0xf7 @"$LIB/elements/$f.bin" --no-wait
done
for t in 14 15; do
    "${C[@]}" raw 0xf7 @"$LIB/elements/channel-$t.bin" --no-wait
done
"${C[@]}" bssid 00:25:00:ff:94:73

"${C[@]}" enable

if [ -n "$PEER" ]; then
    python3 "$LIB/omdrop-sync.py" "$PEER" > "$TMP/sync.bin"
    "${C[@]}" peer-add "$PEER"
fi

"${C[@]}" channels
"${C[@]}" bssid 00:25:00:ff:94:73
for t in 14 15; do
    "${C[@]}" raw 0xf7 @"$LIB/elements/channel-$t.bin" --no-wait
done
[ -n "$PEER" ] && "${C[@]}" raw 0xf7 @"$TMP/sync.bin" --no-wait

if [ -n "$PEER" ]; then
    INFO=$(dmesg | grep -a "AWDL_PEER_ADDED" | tail -1)
    ST=$(echo "$INFO" | sed -n 's/.*station=\([0-9]*\).*/\1/p')
    WT=$(echo "$INFO" | sed -n 's/.*wtbl=\([0-9]*\).*/\1/p')
    if [ -n "$ST" ]; then
        for st in 1 2; do
            BODY=$(python3 "$LIB/omdrop-peerbody.py" "$ST" "$WT" "$PEER")
            "${C[@]}" raw 0x13 "$BODY" --runtime 1 --no-wait
            sleep 1
        done
        echo "peer=$PEER station=$ST wtbl=$WT"
    fi
fi

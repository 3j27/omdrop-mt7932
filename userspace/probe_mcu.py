#!/usr/bin/env python3
"""Enumerate firmware MCU command ids through the driver's raw vendor command.

The mt7932 driver speaks the MediaTek MCU protocol the mt76 connac drivers
document: commands carry a command id, a SET/QUERY flag and a sequence, and
the firmware answers with an event. This tool sends one command id at a time
and prints whatever the firmware answers, so the ids with real handlers can be
told from the ones this firmware ignores.

    probe_mcu.py --uni 0x01 0x80        # unified ids, query
    probe_mcu.py --legacy 0x00 0xff --set --body 00000000

Exit: 0 if at least one command answered.
"""

import argparse
import struct
import sys

import mtk_awdl_cmd as m


def send(nl, idx, cid, uni, ext, set_, wait, body):
    blob = struct.pack("=HBBBBH", cid & 0xffff, 1 if uni else 0, ext & 0xff,
                       1 if set_ else 0, 1 if wait else 0, len(body)) + body
    reply = nl.vendor(idx, m.MT7932_VNDR_CMDS_RAW, blob)
    attrs = m._parse_attrs(reply)
    return attrs.get(m.MT7932_NLATTR_DATA, b'')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('-i', '--iface', default='wlan0')
    ap.add_argument('first', type=lambda x: int(x, 0))
    ap.add_argument('last', type=lambda x: int(x, 0))
    ap.add_argument('--uni', action='store_true', help='unified descriptor')
    ap.add_argument('--ext', type=lambda x: int(x, 0), default=0)
    ap.add_argument('--set', action='store_true', help='SET instead of QUERY')
    ap.add_argument('--body', default='00000000', help='hex body')
    ap.add_argument('--timeout-ok', action='store_true',
                    help='keep going after a timeout')
    args = ap.parse_args()

    body = bytes.fromhex(args.body.replace(':', '')) if args.body else b''
    nl = m.Netlink(timeout=1.0)
    idx = m.ifindex(args.iface)
    answered = 0

    for cid in range(args.first, args.last + 1):
        try:
            data = send(nl, idx, cid, args.uni, args.ext, args.set, True, body)
        except RuntimeError:
            print('0x%02x timeout' % cid)
            if args.timeout_ok:
                continue
            break
        except OSError as e:
            print('0x%02x error %d (%s)' % (cid, e.errno, e.strerror))
            continue
        answered += 1
        print('0x%02x %s' % (cid, data.hex() if data else '(empty reply)'))
    return 0 if answered else 1


if __name__ == '__main__':
    raise SystemExit(main())

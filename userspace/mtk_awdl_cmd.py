#!/usr/bin/env python3
"""Drive the MT7932 firmware's AWDL from userspace through nl80211 vendor
commands, the MediaTek counterpart of brcm_iovar.py.

Transport: NL80211_CMD_VENDOR with vendor_id MEDIATEK_OUI (0x000ce7).
The driver ABI is in drivers/net/wireless/mediatek/mt7932/vendor.h:

    subcmd 1 (MT7932_VNDR_CMDS_AWDL):     u32 op, 0 = create, 1 = destroy
                                          the awdl0 interface.  Asynchronous:
                                          create returns as soon as the
                                          firmware has been asked; awdl0
                                          appears when the firmware reports
                                          the AWDL BSS present.
    subcmd 2 (MT7932_VNDR_CMDS_AWDL_CMD): struct { le32 op; u8 body[] } with
                                          op 1..9 mapping one-to-one onto
                                          the firmware's CID 0x7e body
                                          selectors (see awdl.h):
      1 enable   body = {2 GHz channel, 5 GHz channel, density}
      2 disable  body = {}
      3 service  body = {le16 length, bytes}      (advertised in MIFs)
      4 template body = {le16 length, bytes}      (PSF sync template)
      5 action   body = {le16 length, bytes}      (one action frame)
      6 peer add body = mac[6]
      7 peer rm  body = mac[6]
      8 state    body = {selector 0..4}; answered with the firmware event
                 body in MT7932_NLATTR_LEN (be16) + MT7932_NLATTR_DATA
      9 election body = {le32 metric, s8 rssi threshold}

Like brcm_iovar.py this needs CAP_NET_ADMIN and no kernel patch.
"""

import argparse
import errno
import os
import socket
import struct
import sys

NETLINK_GENERIC = 16
NLMSG_ERROR, NLMSG_DONE = 2, 3
NLM_F_REQUEST, NLM_F_ACK = 0x01, 0x04
GENL_ID_CTRL = 16
CTRL_CMD_GETFAMILY = 3
CTRL_ATTR_FAMILY_ID, CTRL_ATTR_FAMILY_NAME = 1, 2

NL80211_CMD_VENDOR = 103
NL80211_ATTR_IFINDEX = 3
NL80211_ATTR_VENDOR_ID = 195
NL80211_ATTR_VENDOR_SUBCMD = 196
NL80211_ATTR_VENDOR_DATA = 197

MEDIATEK_OUI = 0x000CE7
MT7932_VNDR_CMDS_AWDL = 1
MT7932_VNDR_CMDS_AWDL_CMD = 2
MT7932_VNDR_CMDS_RAW = 3
MT7932_NLATTR_LEN, MT7932_NLATTR_DATA = 1, 2

AWDL_CREATE, AWDL_DESTROY = 0, 1
OP_ENABLE, OP_DISABLE, OP_SERVICE, OP_TEMPLATE, OP_ACTION = 1, 2, 3, 4, 5
OP_PEER_ADD, OP_PEER_REMOVE, OP_STATE, OP_ELECTION = 6, 7, 8, 9
OP_NAMES = {'enable': OP_ENABLE, 'disable': OP_DISABLE,
            'service': OP_SERVICE, 'template': OP_TEMPLATE,
            'action': OP_ACTION, 'peer-add': OP_PEER_ADD,
            'peer-remove': OP_PEER_REMOVE, 'state': OP_STATE,
            'election': OP_ELECTION}


def _attr(atype, payload):
    alen = 4 + len(payload)
    return struct.pack("=HH", alen, atype) + payload + b"\0" * (-alen % 4)


def _parse_attrs(buf):
    out, off = {}, 0
    while off + 4 <= len(buf):
        alen, atype = struct.unpack_from("=HH", buf, off)
        if alen < 4:
            break
        out[atype & 0x3FFF] = buf[off + 4: off + alen]
        off += (alen + 3) & ~3
    return out


class Netlink:
    def __init__(self, timeout=8.0):
        self.sock = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW,
                                  NETLINK_GENERIC)
        self.sock.bind((0, 0))
        self.sock.settimeout(timeout)
        self.seq = 0
        self.family_id = self._resolve_family(b"nl80211")

    def _next_seq(self):
        self.seq += 1
        return self.seq

    def _resolve_family(self, name):
        attrs = _attr(CTRL_ATTR_FAMILY_NAME, name + b"\0")
        seq = self._send(GENL_ID_CTRL, CTRL_CMD_GETFAMILY, 1, attrs)
        chunks, err = self._collect(seq)
        if err:
            raise OSError(-err, os.strerror(-err))
        for chunk in chunks:
            attrs = _parse_attrs(chunk)
            if CTRL_ATTR_FAMILY_ID in attrs:
                return struct.unpack("=H", attrs[CTRL_ATTR_FAMILY_ID][:2])[0]
        raise RuntimeError("nl80211 family not found")

    def _send(self, family_id, cmd, version, attrs):
        seq = self._next_seq()
        body = struct.pack("=BBH", cmd, version, 0) + attrs
        hdr = struct.pack("=IHHII", 16 + len(body), family_id,
                          NLM_F_REQUEST | NLM_F_ACK, seq, 0)
        self.sock.send(hdr + body)
        return seq

    def _collect(self, seq):
        """Collect multipart answer chunks until the ACK/error for `seq`.

        Only a message carrying `seq` ever ends this loop. A stale ACK left
        in the receive buffer by an earlier request must not be read as the
        answer to this one, which is exactly how brcm_iovar.py lost the
        difference between an absent vendor command and a successful one.
        """
        chunks = []
        while True:
            try:
                buf = self.sock.recv(65536)
            except socket.timeout:
                raise RuntimeError("netlink timeout")
            off = 0
            while off + 16 <= len(buf):
                mlen, mtype, _flags, mseq, _pid = struct.unpack_from("=IHHII", buf, off)
                if mlen < 16 or off + mlen > len(buf):
                    break
                if mseq == seq:
                    if mtype == NLMSG_ERROR:
                        return chunks, struct.unpack_from("=i", buf, off + 16)[0]
                    if mtype == NLMSG_DONE:
                        return chunks, 0
                    chunks.append(buf[off + 20: off + mlen])
                off += (mlen + 3) & ~3

    def vendor(self, ifindex, subcmd, data):
        attrs = _attr(NL80211_ATTR_IFINDEX, struct.pack("=I", ifindex)) + \
            _attr(NL80211_ATTR_VENDOR_ID, struct.pack("=I", MEDIATEK_OUI)) + \
            _attr(NL80211_ATTR_VENDOR_SUBCMD, struct.pack("=I", subcmd))
        if data:
            attrs += _attr(NL80211_ATTR_VENDOR_DATA, data)
        seq = self._send(self.family_id, NL80211_CMD_VENDOR, 0, attrs)
        chunks, err = self._collect(seq)
        if err:
            raise OSError(-err, os.strerror(-err))
        return b"".join(chunks)


def ifindex(name):
    idx = socket.if_nametoindex(name)
    return idx


def parse_bytes(spec):
    """A body from hex digits, colon hex, or @file."""
    if spec.startswith('@'):
        with open(spec[1:], 'rb') as f:
            return f.read()
    spec = spec.replace(':', '').replace(' ', '')
    if len(spec) % 2:
        raise ValueError('odd number of hex digits')
    return bytes.fromhex(spec)


def parse_mac(spec):
    parts = spec.split(':')
    if len(parts) != 6:
        raise ValueError('not a MAC')
    return bytes(int(p, 16) for p in parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('-i', '--iface', default='wlan0',
                    help='the station interface owning the wiphy (default wlan0)')
    ap.add_argument('-q', '--quiet', action='store_true')
    sub = ap.add_subparsers(dest='cmd', required=True)

    sub.add_parser('create', help='create awdl0 (asynchronous)')
    sub.add_parser('destroy', help='remove awdl0 (refused while the session is enabled)')
    p = sub.add_parser('enable', help='enable the firmware AWDL session')
    p.add_argument('master_chan', type=int, help='2 GHz master channel')
    p.add_argument('peer_chan', type=int, help='5 GHz peer channel')
    p.add_argument('density', type=int, nargs='?', default=1,
                   help='0 idle, 1 active (default), 2 mirror')
    sub.add_parser('disable', help='disable the firmware AWDL session')
    for name in ('service', 'template', 'action'):
        p = sub.add_parser(name, help='length-prefixed %s body (hex or @file)' % name)
        p.add_argument('body')
    for name in ('peer-add', 'peer-remove'):
        p = sub.add_parser(name, help='%s one peer' % name)
        p.add_argument('mac')
    p = sub.add_parser('state', help='firmware state readback')
    p.add_argument('selector', type=int, choices=range(5))
    p.add_argument('-l', '--raw', help='write the reply body to this file')
    p = sub.add_parser('election', help='election configuration')
    p.add_argument('metric', type=lambda x: int(x, 0))
    p.add_argument('rssi', type=int)
    p = sub.add_parser('raw', help='one firmware command (bring-up probes)')
    p.add_argument('cid', type=lambda x: int(x, 0),
                   help='command id: low byte (original layout) or 16-bit (unified)')
    p.add_argument('body', nargs='?', default='',
                   help='body as hex, or @file')
    p.add_argument('--uni', action='store_true', help='unified descriptor')
    p.add_argument('--ext', type=lambda x: int(x, 0), default=0,
                   help='extension command id (original layout)')
    p.add_argument('--query', action='store_true', help='QUERY instead of SET')
    p.add_argument('--no-wait', action='store_true', help='do not wait for the reply')
    p.add_argument('-l', '--raw', dest='out', help='write the reply body to this file')

    args = ap.parse_args()
    nl = Netlink()
    idx = ifindex(args.iface)

    try:
        if args.cmd == 'create':
            nl.vendor(idx, MT7932_VNDR_CMDS_AWDL, struct.pack("=I", AWDL_CREATE))
            if not args.quiet:
                print('created: awdl0 will appear when the firmware reports it present')
        elif args.cmd == 'destroy':
            nl.vendor(idx, MT7932_VNDR_CMDS_AWDL, struct.pack("=I", AWDL_DESTROY))
            if not args.quiet:
                print('destroyed: awdl0 goes when the firmware reports the BSS absent')
        elif args.cmd == 'enable':
            body = struct.pack("=BBB", args.master_chan, args.peer_chan, args.density)
            nl.vendor(idx, MT7932_VNDR_CMDS_AWDL_CMD,
                      struct.pack("=I", OP_ENABLE) + body)
            if not args.quiet:
                print('enabled: master=%d peer=%d density=%d' %
                      (args.master_chan, args.peer_chan, args.density))
        elif args.cmd == 'disable':
            nl.vendor(idx, MT7932_VNDR_CMDS_AWDL_CMD, struct.pack("=I", OP_DISABLE))
            if not args.quiet:
                print('disabled')
        elif args.cmd in ('service', 'template', 'action'):
            body = parse_bytes(args.body)
            op = {'service': OP_SERVICE, 'template': OP_TEMPLATE, 'action': OP_ACTION}[args.cmd]
            nl.vendor(idx, MT7932_VNDR_CMDS_AWDL_CMD,
                      struct.pack("=IH", op, len(body)) + body)
            if not args.quiet:
                print('%s: %d bytes' % (args.cmd, len(body)))
        elif args.cmd in ('peer-add', 'peer-remove'):
            op = OP_PEER_ADD if args.cmd == 'peer-add' else OP_PEER_REMOVE
            nl.vendor(idx, MT7932_VNDR_CMDS_AWDL_CMD,
                      struct.pack("=I", op) + parse_mac(args.mac))
            if not args.quiet:
                print('%s: %s' % (args.cmd, args.mac))
        elif args.cmd == 'state':
            reply = nl.vendor(idx, MT7932_VNDR_CMDS_AWDL_CMD,
                              struct.pack("=IB", OP_STATE, args.selector))
            attrs = _parse_attrs(reply)
            data = attrs.get(MT7932_NLATTR_DATA, b'')
            declared = struct.unpack("=H", attrs[MT7932_NLATTR_LEN][:2])[0] \
                if MT7932_NLATTR_LEN in attrs else -1
            if args.raw:
                with open(args.raw, 'wb') as f:
                    f.write(data)
                if not args.quiet:
                    print('state %d: %d bytes (declared %d) -> %s' %
                          (args.selector, len(data), declared, args.raw))
            else:
                print(data.hex())
                if declared != len(data) and not args.quiet:
                    print('declared %d' % declared, file=sys.stderr)
        elif args.cmd == 'election':
            nl.vendor(idx, MT7932_VNDR_CMDS_AWDL_CMD,
                      struct.pack("=I", OP_ELECTION) +
                      struct.pack("<i", args.metric) +
                      struct.pack("=b", args.rssi))
            if not args.quiet:
                print('election: metric=%d rssi=%d' % (args.metric, args.rssi))
        elif args.cmd == 'raw':
            body = parse_bytes(args.body) if args.body else b''
            blob = struct.pack("=HBBBBH", args.cid & 0xffff,
                               1 if args.uni else 0, args.ext & 0xff,
                               0 if args.query else 1,
                               0 if args.no_wait else 1, len(body)) + body
            reply = nl.vendor(idx, MT7932_VNDR_CMDS_RAW, blob)
            attrs = _parse_attrs(reply)
            data = attrs.get(MT7932_NLATTR_DATA, b'')
            if args.out:
                with open(args.out, 'wb') as f:
                    f.write(data)
                if not args.quiet:
                    print('%s: %d bytes -> %s' % (args.cmd, len(data), args.out))
            elif data or not args.quiet:
                print(data.hex())
    except OSError as e:
        print('%s: %s' % (args.cmd, e.strerror), file=sys.stderr)
        return -e.errno if e.errno else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

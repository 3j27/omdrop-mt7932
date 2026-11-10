# omdrop-mt7932

AirDrop on the built-in MediaTek **MT7932** in a MacBook Neo (J700) running
Linux.

`omdrop-mtk` is the vendor-wide MediaTek toolkit; this repository is the
chip-specific port, hence **omdrop-mt7932**.  The installed product is
still just `omdrop`.

## Status

Working:

- AWDL session on the built-in MT7932: PSF TX, peer presence on macOS/iOS,
  `_airdrop._tcp` advertisement, and the Mac listing the machine as
  `omarchy-awdl`.
- Receiving files into `~/Downloads/AirDrop/<timestamp>/` with automatic
  DVZip/gzip + CPIO extraction.
- Sending files to a receiver with the AirDrop `/Discover` → `/Ask` →
  `/Upload` flow.
- Persistent services: `omdrop-awdl` (root), `omdrop-receive` (user), and
  a launchd relay on the Mac.

Known limitation:

- The MT7932 firmware still drops inbound AWDL **unicast** before the host.
  The Mac discovers us and opens a TCP/TLS connection, but the frame never
  reaches Linux.  A second machine on the LAN (the "Studio" Mac) therefore
  runs a small TCP relay: the advertised address is made local to the Mac,
  and the relay forwards the stream to the Neo over Ethernet.  Native
  receive without the relay needs the firmware data-path/key solved, or a
  USB adapter with monitor mode + injection (owly).

## Architecture

```
  Mac (Studio) AirDrop UI
        │  TCP/TLS to <relay-owned-ipv6>:8771  (address local on the Mac)
        ▼
  com.omdrop.relay (launchd)  ── ethernet ──►  Neo:8771
                                                   │
                                          omdrop-recv (TLS)
                                                   │
                                        ~/Downloads/AirDrop/<ts>/

  Neo: omdrop-awdl ── MT7932 AWDL ──► PSF/MIF + _airdrop._tcp
```

## Driver

The kernel driver is in the `aurora-silicon/linux` fork:

- **Unsquashed feature branch (40 commits):**
  <https://github.com/3j27/linux/tree/mt7932/awdl-airdrop>
- Tip commit: `0a4211a5dce3` — “mt7932: bring up the AWDL BSS the way
  Apple's driver does”.
- Squashed single-commit alternative:
  <https://github.com/3j27/linux/tree/mt7932/awdl-airdrop-squashed>

The driver changes live in
`drivers/net/wireless/mediatek/mt7932/` and add:

- the firmware's second BSS (AWDL) activation in Apple's order, with its
  own-MAC index (`body[0x3b]`, printed by the firmware as `OX`),
- the sync-master element 9 (without it the firmware loses every TX grant
  and asserts in its health monitor),
- native/translated AWDL RX routing to `awdl0` and decapsulation,
- the packet filter (`CID 0x0a`) and MCU register access (`CID 0xc0`)
  diagnostics,
- the channel sequence, TX queues, peer station record, and vendor
  commands used by the userspace package.

Build and install it against the running kernel (the J700 tree uses LLVM
and an `updates/` override; adapt the paths to your distribution):

```sh
git clone https://github.com/3j27/linux
cd linux
git checkout mt7932/awdl-airdrop

make -C /usr/lib/modules/$(uname -r)/build \
     M=$PWD/drivers/net/wireless/mediatek/mt7932 modules

sudo install -Dm644 \
  drivers/net/wireless/mediatek/mt7932/mt7932-fullmac.ko \
  /usr/lib/modules/$(uname -r)/updates/mt7932-fullmac.ko
sudo depmod -a
sudo mkinitcpio -P            # or your initramfs generator
# reboot
```

On the J700/Omarchy image the helper under `driver/` can be used instead;
it builds with the pinned LLVM, installs the `updates/` override, and
keeps a rollback script.

## Userspace install (Neo)

```sh
cd userspace
sudo ./packaging/install.sh
```

This installs:

- `/usr/local/bin/omdrop`
- `/usr/local/lib/omdrop/` (daemon, receiver, sender, advertiser, elements)
- `/etc/omdrop/config`
- `omdrop-awdl.service` (root, enabled)
- `omdrop-receive.service` (user, enabled)
- `/usr/share/applications/omdrop.desktop` → launcher entry **AirDrop
  (omdrop)**

Edit `/etc/omdrop/config`:

```sh
STUDIO=<studio-host>          # SSH target; its awdl0 MAC is read per session
STUDIO_USER=<ssh-user>
PEER=                         # optional fixed peer MAC
ADVERTISE_HOST=omarchy-awdl.local
ADVERTISE_IPV4=<neo-lan-ip>
ADVERTISE_AAAA=<relay-owned-ipv6>
```

Then:

```sh
sudo systemctl restart omdrop-awdl
systemctl --user restart omdrop-receive
```

## Relay install (Mac)

The Mac needs the advertised IPv6 address on `lo0` and a TCP relay to the
Neo.  From the `userspace/studio` directory on the Mac:

```sh
sudo OMDROP_TARGET_IP=<neo-lan-ip> ./install-studio.sh
```

It installs `com.omdrop.relay` as a launchd daemon (auto-start at boot),
adds the relay-owned IPv6 to `lo0`, and forwards `:8771` to
`<neo-lan-ip>:8771`.  Log: `/var/log/omdrop-relay.log`.

## Use

- Launcher: **AirDrop (omdrop)** opens the receive folder.
- `omdrop status` — interface, daemon, receiver, folder.
- `omdrop folder` — open `~/Downloads/AirDrop`.
- `omdrop receive` — run the receiver in the foreground.
- `omdrop send HOST PORT FILE` — send a file.
- `omdrop up|down|restart` — control the AWDL daemon.

Received files are extracted under `~/Downloads/AirDrop/<timestamp>/`.
Receiver log: `~/.local/state/omdrop/receive.log`.

## Troubleshooting

- **Mac does not list us:** check `omdrop status`, then
  `sudo journalctl -u omdrop-awdl`.  The daemon must have a peer WTBL
  (`/sys/module/mt7932_fullmac/parameters/awdl_probe_wtbl` non-zero) and
  the Mac's AWDL address must match `ifconfig awdl0` on the Mac.
- **Listed but transfer fails:** check `/var/log/omdrop-relay.log` on the
  Mac and `~/.local/state/omdrop/receive.log` on the Neo.  The relay must
  reach `<neo-lan-ip>:8771`.
- **Neo IP changed:** update `ADVERTISE_IPV4` and
  `OMDROP_TARGET_IP`/the installed plist.
- **Mac AWDL address changed:** the daemon re-reads it every 12 seconds;
  no action needed when `STUDIO` is configured.
- **No ADB/SSH access to the Mac:** use a fixed `PEER=<mac>` instead of
  `STUDIO`.

## Layout

```
userspace/
  omdrop                  CLI
  omdrop-daemon           root daemon: bring-up + advertisement
  omdrop-bringup.sh       one firmware bring-up
  omdrop-adv.py           _airdrop._tcp advertiser
  omdrop-recv             TLS receiver + extraction
  omdrop-send             sender
  elements/               firmware elements
  packaging/              install script, units, desktop entry, config
  studio/                 Mac relay installer and launchd daemon
driver/                   helper notes/scripts for the kernel module
```

## Related

- owly / omdrop-owl — userspace AWDL for USB adapters with monitor mode.
- omdrop-mtk — vendor-wide MediaTek userspace toolkit (`awdl-up`,
  `mtk_awdl_cmd.py`, …).
- AppleSunriseWLAN DEXT — the reference for the firmware command ABI.

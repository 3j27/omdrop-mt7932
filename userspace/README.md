# omdrop for the built-in MT7932

Receive and send files over Apple AirDrop using the MacBook's built-in
MT7932.  The firmware can advertise and transmit, but it drops inbound
AWDL unicast before the host, so a second machine on the LAN runs a small
TCP relay for the Mac's validation/transfer connection.

## Layout

```
userspace/
  omdrop                  CLI (status/up/down/receive/send/folder)
  omdrop-daemon           root daemon: AWDL bring-up + advertisement
  omdrop-bringup.sh       one firmware bring-up
  omdrop-adv.py           mDNS _airdrop._tcp advertiser
  omdrop-recv             TLS receiver, extracts to ~/Downloads/AirDrop
  omdrop-send             one-shot sender (/Discover, /Ask, /Upload)
  omdrop-sync.py          element 9 (sync master)
  omdrop-peerbody.py      CID 0x13 peer body
  elements/               firmware bring-up elements
  packaging/
    install.sh            install on the Linux machine
    omdrop-awdl.service   system service (bring-up + advertisement)
    omdrop-receive.service user service (receiver)
    omdrop.desktop        launcher entry
    config.example        /etc/omdrop/config
  studio/
    install-studio.sh     install the relay on the Mac
    airdrop-relay.py      TCP relay
    com.omdrop.relay.plist launchd daemon
```

## Install

On the Linux machine (root):

```
sudo userspace/packaging/install.sh
```

Edit `/etc/omdrop/config`: `STUDIO` is the Mac (SSH, and the user whose
keys are used), `ADVERTISE_IPV4` is this machine on the LAN,
`ADVERTISE_AAAA` is the address the Mac connects to and the relay owns.

On the Mac (root):

```
sudo userspace/studio/install-studio.sh
```

It adds the advertised IPv6 address to `lo0` and installs
`com.omdrop.relay` as a launchd daemon forwarding `:8771` to
`ADVERTISE_IPV4:8771`.

## Use

- Launcher: **AirDrop (omdrop)** opens the receive folder.
- `omdrop status` — interface, daemon, receiver, folder.
- `omdrop folder` — open `~/Downloads/AirDrop`.
- `omdrop receive` — run the receiver in the foreground.
- `omdrop send HOST PORT FILE` — send a file to a receiver.
- `omdrop up|down|restart` — control the AWDL daemon.

Received files are extracted under `~/Downloads/AirDrop/<timestamp>/`.

## Files

- Advertised service: `_airdrop._tcp`, instance from the AWDL MAC,
  `flags=0x3fb`.
- Receiver TLS: self-signed cert generated in `~/.local/state/omdrop/`.
- Receiver log: `~/.local/state/omdrop/receive.log`.
- Relay log on the Mac: `/var/log/omdrop-relay.log`.

## Limitation

The MT7932 firmware still drops inbound AWDL unicast, so the Mac's direct
connection cannot reach this host.  The Studio/Mac relay is required for
receiving until the firmware data path is solved or a USB adapter with
monitor/injection is used.  Sending from this machine to the Mac works
through the same relay.

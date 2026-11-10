# Driver

The kernel driver is not duplicated here.  It lives in the
`aurora-silicon/linux` fork:

- Unsquashed branch: <https://github.com/3j27/linux/tree/mt7932/awdl-airdrop>
- Squashed alternative: <https://github.com/3j27/linux/tree/mt7932/awdl-airdrop-squashed>

## J700 / Omarchy reference

The tested machine is a MacBook Neo (J700) running `7.2.11-15-1-ARCH`
with Clang/LLVM 18 and a Limine UKI.  The driver is installed as an
`updates/` override and activated by a reboot.

```sh
git clone https://github.com/3j27/linux
cd linux
git checkout mt7932/awdl-airdrop

# build against the running kernel
./../omdrop-mt7932/driver/build.sh "$PWD"

# install and refresh the boot image
sudo ./../omdrop-mt7932/driver/install.sh "$PWD"
sudo reboot
```

`build.sh` and `install.sh` are generic helpers; the pinned-LLVM building
and the snapper/Limine steps are from the J700 image and may need adapting
on other distributions.

## What the branch changes

- AWDL BSS activation in Apple's order, with the own-MAC index
  (`body[0x3b]`, logged by the firmware as `OX`).
- Sync-master element 9 on session start and peer add (prevents the
  firmware health-monitor assert).
- Native and translated AWDL RX routing to `awdl0`, with decapsulation
  before `eth_type_trans`.
- Packet filter (`CID 0x0a`) and MCU register access (`CID 0xc0`)
  diagnostics.
- Channel sequence, TX queues, peer station records, vendor commands.

The firmware still drops inbound AWDL unicast before the host; see the
top-level README for the relay workaround.

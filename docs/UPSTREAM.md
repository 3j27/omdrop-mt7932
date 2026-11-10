# Where this stands relative to upstream

`mt7932/awdl-airdrop` is based on `068dfce19780` (2026-11-07).  The branch
has 40 commits and is what the userspace package in this repository
targets; it builds against `7.2.11-15-1-ARCH` and is the only version that
has been exercised end to end with AirDrop.

## Upstream moved, and grew a second AWDL implementation

`aurora-silicon/linux` `integration/aurora` is now 3361 commits past that
base and carries its own MT7932 AWDL support:

| PR | State | What it does |
| --- | --- | --- |
| #1346 | merged | experimental AWDL interface: second firmware BSS, peer/WTBL ownership, RX routing, Ethernet framing, KUnit tests |
| #1469 | merged | isolate AWDL activation from the managed station |
| #1939 | merged | `CONFIG_MT7932_AWDL=y` in the shared config fragment |
| #2064 | merged | keep the option **off** again for 7.3.0-41, as in every release so far |
| #2054 | open (draft) | keep udev from renaming `awdl0` to `wld0` |
| #2065 | open | what has to happen before the option can be enabled by default |

Upstream's implementation is a different design from ours: it registers
`awdl0` through cfg80211 as a station-typed wdev, drives BSS 1 with
`mt_request()` records, and takes peers through `add_station`.  Its data
path stays closed until a full host policy, schedule and templates are
supplied (`sync_enabled` and `slot_open`), so it is an interface and a
test harness, not a working AirDrop endpoint.  No hardware run of the
AirDrop flow has been reported there.

Our implementation drives the firmware through vendor commands from
userspace (`mtk_awdl_cmd.py`), with `awdl_probe_wtbl` naming the peer so
multicast data frames leave the firmware at all, and it carries the
empirical bring-up order (channel-setter elements `0x0e`/`0x0f` before
`enable`, sync-master element 9, own-MAC index `body[0x3b]`) that made the
Mac list and reach us.

## Why a rebase is not mechanical

1. **Two implementations of the same feature.**  Both branches add
   `awdl.c`, `awdl.h` and `awdl-test.c`; ours is 1849 lines, upstream's is
   1055, and the glue differs (`mt_awdl_add_vif`/vendor commands versus
   `mt_awdl_register`/station ops wired into `startup.c`).
2. **The glue moved.**  Upstream now creates `awdl0`, activates it on
   interface up, and dispatches events through `mt_awdl_event()`; our
   call sites are in different places in `mt7932.c`, `frontend.c`,
   `data.c`, `link.c` and `lifecycle.c`.
3. **The base is a different kernel.**  `integration/aurora` is 7.3.0 and
   uses in-tree `apple_piodma_radio_set_stop()`/`_recover()` symbols that
   the installed `7.2.11-15` headers do not have, so the module cannot be
   built against the running kernel's build tree.  Rebuilding it needs a
   full 7.3 kernel and a reboot.

A trial merge (our tip onto `integration/aurora`, preferring our side on
overlap) applies without textual conflicts but does not compile: the
merged tree calls `mt_awdl_event()` from upstream's glue while carrying
our `awdl.h`, and upstream's newer `mt7932.c` needs the 7.3 PCIe-DMA
symbols.

## The merge branch (`mt7932/awdl-airdrop-7.3`)

That is what the real merge fixes.  `mt7932/awdl-airdrop-7.3` merges
`origin/integration/aurora` (`0abc2f385e54`) into this branch and keeps
our implementation, adapting upstream's glue instead:

- `awdl.c`, `awdl.h`, `awdl-test.c`: ours.
- `startup.c`: keeps `interface_modes` STATION|ADHOC; drops
  `mt_awdl_wiphy_setup()`, `mt_awdl_register()` and the station ops.
- `frontend.c`: drops upstream's BSS-1 route and the `frame.bss` gate on
  translated frames; this tree demultiplexes BSS-1 in `data.c`.
- `mt7932.c`: keeps the hand-rolled `awdl_netdev` teardown; no 0xf7
  event dispatch.
- `link.c`, `lifecycle.c`: no upstream awdl-carrier handling.
- `mt7932.h`: no by-value `struct mt7932_awdl`.
- `Kconfig`/`Makefile`: our AWDL option and test object, upstream's
  `wow.o`.

It compiles and links against a prepared 7.3.0 tree, with
`CONFIG_MT7932_AWDL=y` (including the KUnit test object) and with the
option off, with no compiler warnings.  Because the merge base is now
7.3.0, the module reports `vermagic: 7.3.0-ARCH+` and cannot be loaded on
the running `7.2.11-15` kernel.  No hardware run has been done on the
merge; `mt7932/awdl-airdrop` remains the branch to install on 7.2.11.

## Options

- **Keep `mt7932/awdl-airdrop` as the working one.**  It is the only
  hardware-verified AWDL/AirDrop path; nothing upstream replaces it today.
- **Ship `mt7932/awdl-airdrop-7.3` once the machine runs 7.3.**  It is
  merged, conflict-resolved and compiles, but has not been run on
  hardware.
- **Port our bring-up into upstream's framework.**  The reasonable
  upstreamable shape: upstream keeps the netdev/wiphy/peer plumbing, and
  the vendor-command bring-up, the own-MAC index, the sync-master
  element, the channel-setter order and the TX-descriptor peer rule move
  into `awdl.c` as the `mt_request()` implementation.  That is a real
  port, and it needs a 7.3 kernel to test.
- **Rebase after upgrading the machine to 7.3.**  Only then can the
  result be built and booted; expect to resolve the glue by hand.

## Related work

- **owly 0.4.3** (t4t5/owly) keeps a tested hardware matrix.  Monitor
  mode plus raw injection works on, among others, MediaTek MT7925
  (shared mode, Wi-Fi stays connected), MT7612U and RTL8812BU
  (exclusive), RTL8821AU; MT7927 and Intel AC 3168 are recorded as
  failing.  MT7932 is not in the matrix: the built-in radio exposes no
  monitor mode, which is why the owly path needs a USB card.
- **brcmfmac AWDL** (in the same tree) is the reference for how macOS
  expects AWDL to look on the wire, and the source of much of the framing
  both MT7932 implementations reuse.
- The AirDrop protocol details used here (Discover/Ask/Upload, DVZip
  archives, `ReceiverModelName`) are specified in owly's
  `docs/SPEC.md`.

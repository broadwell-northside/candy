# Candy server kit: one master USB that installs the whole GPU server

For Ak's server (EPYC 9275F, ASRock Rack TURIND8-2L2T, 256 GB, 2 × RTX PRO 6000 Blackwell Max-Q). One 1–2 TB USB SSD
carries the Ubuntu 24.04.5 LTS Server installer, every package and wheel it needs at pinned versions, ComfyUI and
llama.cpp at pinned commits, and the models from the lead's lock, all SHA256-checked. Boot it once: the server installs
itself unattended, copies everything onto its NVMe, and turns itself off. Unplug the USB and switch the server on;
first boot sets up the rest with no internet needed. Anything that is not on the USB is fetched on first boot from
the same pinned sources, resumably.

Rebuilt from Grok Bot's kit (its blank-NVMe disk guard, ISO checksum check, key-only SSH and loopback-only app ports are
kept). Only Ak runs the steps below that write a disk or change the Mac; every one of them is a dry run unless you add
`--write`/`--apply`.

## Steps (on the Mac, from the repo folder)

1. **Hardware**: work through [HARDWARE-CHECKLIST.md](HARDWARE-CHECKLIST.md).
2. **SSH key**: in 1Password create an SSH key item (it holds the private key; Touch ID unlocks it). Save its *public*
   key as `~/.candy-server-kit/epyc-studio.pub`. The kit never creates or reads a private key.
3. **Answers**: `python3 server-kit/mac/configure.py` (four questions, writes `server-kit/config/install.json`).
4. **Build the installer files**: `python3 server-kit/builder.py` downloads the official ISO once (about 4 GB, into
   `server-kit/build/`), checks it against Ubuntu's SHA256SUMS and the pin, and writes the installer files.
5. **Pick the USB**: `python3 server-kit/usb/list_candidates.py --plug-in` asks you to unplug the new SSD, then plug it
   in, and shows only the one disk that appeared, with its serial and UUID. It is read-only and keeps no record of your
   drives.
6. **Write it**: `python3 server-kit/usb/write_master_usb.py --serial S --volume-uuid U` (a dry run), then the same
   with `--write`, in Terminal. It asks you to type `ERASE <serial>`.
7. **Fill it**: `python3 server-kit/usb/stage_store.py --serial S --volume-uuid <TURINDATA UUID>` (a dry run with
   sizes), then add `--apply`. This downloads the lead's lock (waves 1–3, about 390 GB today) plus about 6 GB of
   software (665 .deb files as resolved on 2026-11-06, wheels and sources) straight onto the USB, and it is
   resumable. The Civitai LoRAs need `CIVITAI_API_TOKEN` and the gated Hugging Face file needs `HF_TOKEN` in the
   environment for this one run. Each is sent only to its own site, never on to a download server, and never stored.
   `--with-heavy` adds wave 4 (about 620 GB more: use the 2 TB SSD).
8. **Install**: the USB goes in the server; boot it once (HARDWARE-CHECKLIST.md). When the server turns itself off,
   unplug the USB and switch the server on.
9. **First login**: `python3 server-kit/mac/candy_link.py setup --apply` once, then `Open-Remote-Desktop.command`.
   The first time, it asks you over SSH for the server account's password (full `sudo` asks for it) and a
   remote-desktop password. Keep both in 1Password.
10. **Connect** any time: double-click
    `mac/Connect-EPYC-Studio.command` (dashboard and apps) or `mac/Open-Remote-Desktop.command`. Tailscale, if you
    want it: `mac/tailscale_mac.sh` and `mac/tailscale_server.sh` (both keep DNS untouched with `--accept-dns=false`).

Later changes to the installer without re-downloading the models: `write_master_usb.py ... --update-boot`.

## Safety rails

- **Disks on the Mac**: the writer picks the target only by serial + a volume UUID you confirm. It refuses every
  internal disk, disk image and non-USB disk, every APFS or Time Machine volume, any filesystem it cannot inspect, and
  any disk holding files (a non-empty Trash counts) unless it carries this kit's own marker. It re-reads the disk's
  identity right before erasing, reads every file back from the USB (not from memory), and writes only from a real
  Terminal, never from an AI session. No size rule, no sudo. A deny-list (`make_denylist.py`) is optional and only
  adds refusals: you said no to an inventory of your drives, and the writer does not depend on one.
- **Disks on the server**: the installer only uses a blank internal NVMe (Grok Bot's guard), never a USB or removable
  disk, and never the master USB (PCIe hot-plug flags are ignored: the BIOS's PCIE Hotplug setting sets them). A disk that is not blank stops the install; nothing is erased.
- **sudo on the server**: no blanket password-less sudo. Without a password the admin can run only the kit's own
  helpers (`turin-health`, `turin-burnin`, `turin-llm-profile`, ...) and the exact Tailscale join/leave commands;
  everything else asks for the account password you set at first login.
- **Network**: SSH is key-only, for the admin user only, from private and link-local addresses or Tailscale. Every service
  (dashboard 8099, Easy Studio 7860, ComfyUI 8188/8189, Director 8000, desktop 5900) listens on 127.0.0.1 and is
  reached through the SSH tunnel. No tokens or keys on the USB or the server.
- **GPUs**: the lead's `app/placement.json` decides the cards (the USB carries that file, no copy is kept here). The
  Director runs on GPU 0 in hybrid mode (MoE experts in RAM) beside the image lane, so the video lane keeps GPU 1; a
  Director profile above 70 GB takes GPU 1 whole and pauses ComfyUI GPU 1 while it is loaded.
- **Pins** (`config/kit.json`, fetched 2026-11-06): Ubuntu 24.04.5 ISO by SHA256; Ubuntu archive snapshot
  `20261105T000000Z`; HWE kernel 7.0.0-42; Ubuntu's headless NVIDIA 580.178.04 driver without DKMS, with Canonical-signed
  prebuilt modules (staging refuses if the module was built from another driver or for another kernel); CUDA toolkit 12.8.2; Tailscale 1.104.5; ComfyUI v0.43.0 (the app's contract); llama.cpp commit;
  Strata from the lead's lock (built on first boot if it can be; optional). No Docker. The Easy Studio bundle is a
  `git archive` of one commit (recorded), never the working folder.
- **Models**: the kit reads the lead's `config/server_model_lock.json` as opaque rows (id, URL, path, size, SHA256)
  and keeps no copy of its own.

What only the real machines can prove is listed in [HARDWARE_PENDING.md](HARDWARE_PENDING.md). Tests:
`python3 server-kit/tests/run_tests.py` (offline; the list of what they mock is at its top).

## Where this differs from the lead's S1 design (plan notes, 2026-11-06), decided here
- Stick layout: the ISO's files copied onto FAT32 (the lead's design B) as the primary, because it needs no
  iso-scan/loopback step; the remastered ISO (`builder.py --iso-out`) is plan B for BMC virtual media. Both await the
  VM/real-board proof (HARDWARE_PENDING HP-03, HP-16).
- The installer copies the store onto the NVMe and powers off, so the USB is out before first boot (no boot-order
  trap); the lead's design kept the stick in and mounted it at first boot.
- apt: the vendors' own signed InRelease/Packages files plus the needed .deb files (apt checks every signature on the
  server), not a Packages index rendered from the lock.
- Server packages that are not on the ISO (avahi and others) install on first boot, so `packages: []` in the
  autoinstall (avahi is not in the 24.04.5 ISO's pool).
- Kept from the lead's design: Canonical-signed prebuilt NVIDIA modules, sudo allowlist + first-login password,
  read-back past the page cache, Time Machine refusal, terminal-only writes, 50 GB free-space floor, host-key
  fingerprints on the console, ComfyUI pinned to the app's 0.43 contract, `git archive` app bundle.

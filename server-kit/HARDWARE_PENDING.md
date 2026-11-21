# hardware_pending: what only the real machines can prove

Nothing in this kit has run on the real server, the real master USB or Ak's data drives. The tests in
`tests/run_tests.py` mock every disk, network and hardware tool (the list is at the top of that file). These stay
**hardware_pending**, not passed, until they have run for real:

| ID | What | How it gets proven |
| --- | --- | --- |
| HP-01 | The writer's disk identity on macOS 27 with a real USB SSD (serial from the IORegistry, volume UUIDs, `tmutil`) | Ak runs `list_candidates.py --plug-in`: the new SSD shows a serial and a UUID |
| HP-02 | `diskutil partitionDisk ... MBR FAT32 TURINBOOT 12G ExFAT TURINDATA R` on the real USB SSD, and the read-back | Ak runs `write_master_usb.py --write` |
| HP-03 | UEFI boot of the Ubuntu files copied onto FAT32 (no dd), and GRUB finding `boot/grub/grub.cfg` | First boot on the server. Plan B: `builder.py --iso-out` and BMC virtual media, or a small dd'd stick, with the master USB still attached for the store |
| HP-04 | The installer mounting exFAT TURINDATA read-only (exfat.ko is in the ISO's HWE 7.0 module package) and `store_import.py` copying and checking the store | First install; result in `/var/lib/turin/store-import.json` |
| HP-05 | `disk_guard.py` choosing the blank NVMe from real `lsblk`/`udevadm`/`wipefs`/`blkid` output | First install |
| HP-06 | Subiquity accepting `apt: fallback: offline-install` with the snapshot mirror, offline and online | First install |
| HP-07 | Offline apt from the partial mirror (665 debs, 5.1 GB as resolved on 2026-11-06), and the online fallback | First boot; `/var/log/turin/provision.log` says which source was used |
| HP-08 | The headless NVIDIA 580 driver (no DKMS) with Canonical-signed modules on HWE 7.0.0-42 driving both Blackwell cards | First boot GPU check, `turin-health` |
| HP-09 | CUDA 12.8 nvcc building llama.cpp for sm_120; torch cu128 seeing both GPUs | First boot `setup_ai.py` |
| HP-10 | Wheels resolved on the Mac (`pip --platform manylinux…`) installing offline on Ubuntu 24.04 | First boot |
| HP-11 | RAM in A1/C1/G1/I1, PCIe x16 Gen5 links, NIC speeds, NVMe health, BMC fan/pump RPM | `sudo turin-health` |
| HP-12 | Cooling under full load (pump at 100 %, GPU ≤ 87 °C, CPU ≤ 95 °C) | `sudo turin-burnin --minutes 20` |
| HP-13 | SSH tunnels, remote desktop and Tailscale from the Mac | Ak runs the `mac/` scripts with `--apply` |
| HP-14 | The Easy Studio, ComfyUI and Director services healthy on 127.0.0.1 | Dashboard at http://127.0.0.1:8099 through the tunnel |
| HP-15 | Strata (lead's lock `runtimes`, commit c3b3f50) building with CUDA 12.8 for sm_120 on first boot | `/var/log/turin/provision.log` says `runtime strata: ready` or why not |
| HP-16 | A full autoinstall in a VM (UEFI/OVMF): a blank disk installs; a non-blank disk and a missing guard both stop before partitioning | Not run: an x86 VM on this Mac is emulated (TCG) and takes hours; needs a Linux box or the real server |
| HP-17 | The sudo allowlist and the first-login password on the real server (`visudo` accepted the file on the Mac) | Ak's first `turin-first-login` |
| HP-18 | The Director in hybrid mode on GPU 0 (`-ot exps=CPU`, experts in RAM) beside the image lane, and a >70 GB profile pausing ComfyUI GPU 1; app/placement.json numbers are estimates (`measured: false`) | `nvidia-smi` per card while a Director answer and an image render run together; `sudo turin-llm-profile <big id>` then `systemctl is-active turin-comfy1` |

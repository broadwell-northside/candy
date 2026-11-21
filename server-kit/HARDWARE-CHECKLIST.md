# Before the first boot: hardware checklist

For the EPYC 9275F on an ASRock Rack TURIND8-2L2T with 2 × RTX PRO 6000 Blackwell Max-Q (300 W each) and 256 GB DDR5.
Checked against the board manual (`TURIND8-2L2T.pdf` from download.asrock.com, the copy in Grok Bot's kit; page and
section numbers below are the manual's). Tick each one, then set `hardware_checklist_confirmed: true` in
`server-kit/config/install.json`. The builder refuses to build without it.

**Memory**
- [ ] Four identical 64 GB DDR5 RDIMMs in **DDR5_A1, DDR5_C1, DDR5_G1, DDR5_I1**. That is the manual's 4-DIMM row
  (section 2.4, "Recommended Memory Configurations"). Not H1. DDR5 RDIMM only (specification table).

**GPUs and power**
- [ ] Each GPU in an **x16** slot: PCIE2, PCIE4, PCIE5 or PCIE6. PCIE1 and PCIE3 are x8 (sections 1.7 and 2.5). Leave room
  for each card's own airflow.
- [ ] Each GPU has its own 12V-2x6 (16-pin) cable from the PSU, fully seated, no adapters or splitters.
- [ ] Board power: the 24-pin ATX adapter on ATXPWR1 (4-pin), all three 8-pin ATX12V and the 6-pin ATX12V
  (specification table, "Power Connector"; section 2.9). The 6-pin GFX_12V1 is only needed with four graphics cards (section 2.6).
- [ ] The PSU covers about 600 W of GPUs, 320–400 W of CPU and the rest (1600 W class recommended).

**Cooling** (the kit cannot check this for you)
- [ ] The CPU water-cooler pump is on one of the 6-pin FAN1–FAN8 headers with the right adapter. The pinout is pin 1
  GND, 2 +12 V, 3 tach, 4 PWM, 5 tach 2, 6 not connected, with a maximum of 5 A / 60 W per header (section 2.6, "System Fan
  Connectors"). Never shift a standard plug by a pin.
- [ ] In the BMC web page, that header is set to a constant **100 %**, and you can see its RPM there. ASRock's BMC guide
  calls this Settings → FAN Settings; names vary by firmware. The BIOS H/W Monitor (section 3.3.9) also shows fan speeds.
  Check it again after a reboot.

**Disks and cables**
- [ ] One **blank** NVMe SSD (1 TB or more, 2 TB recommended for the models) in M2_1 or M2_2. If both slots hold an NVMe,
  answer "serial" in the wizard and type the serial of the one to use. A disk that is not blank is never erased.
- [ ] A host network cable in one of the **Intel** ports (X710 10 GbE or i210 1 GbE) to the same switch or router as
  the Mac. The dedicated BMC port alone gives Linux no network.
- [ ] Optional: a cable in the BMC (IPMI) port, with a unique BMC password and never exposed to the internet.
- [ ] The master USB in a rear USB 3.2 Gen1 port (rear I/O). No other USB drives attached to the server.

**BIOS** (F2 or Del during start-up, section 3)
- [ ] UEFI boot, CSM disabled (section 3.7.1).
- [ ] Above 4G Decoding and Re-Size BAR Support enabled (section 3.3.10, PCI Subsystem Settings). Leave x16 bifurcation as it is.
- [ ] "PCIE Hotplug" (it also covers M2_1/M2_2) can stay as it is; the installer no longer depends on it. Disabled is fine.
- [ ] Secure Boot can stay as shipped (section 3.6: the default is Disabled). The kit's NVIDIA driver uses
  Canonical-signed modules, so it also works with Secure Boot on.
- [ ] Boot the master USB once, from the one-time boot menu or the Boot screen (section 3.7). The NVMe stays first
  in the boot order.

**When it finishes**
- [ ] The installer turns the server **off** by itself. Unplug the master USB, then switch the server on. First boot
  sets up everything from the copy the installer made, with no USB and no internet needed. Watch it from the Mac
  with `Connect-EPYC-Studio.command`.
- [ ] Afterwards: `ssh epyc-studio sudo turin-health` (real readings), then `ssh -t epyc-studio sudo turin-burnin --minutes 20`.

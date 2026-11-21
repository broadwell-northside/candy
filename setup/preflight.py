"""Hardware checks before Easy Studio is installed.

Run this on the desktop, from the Easy Studio folder. The graphics card is not
confirmed until the install hold ends, so the GPU name and VRAM are recorded
and do not pass or fail the script. A missing GPU still fails.

    python setup/preflight.py

Exit 0 means every automatic check passed. The power-supply line is always MANUAL:
read the label and put the wattage in the step report. Exit 1 means stop and report.
Nothing is downloaded or changed.

    python setup/preflight.py --self-test
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys

NEED_DISK_GB = 200
NEED_RAM_GB = 64
MIN_RAM_GB = 32
MIN_DRIVER = (570, 0)
MIN_CUDA = (12, 8)


def _ver(text):
    parts = re.findall(r"\d+", text or "")
    if not parts:
        return (0, 0)
    nums = [int(x) for x in parts[:2]]
    return (nums[0], nums[1] if len(nums) > 1 else 0)


def evaluate(info):
    """info keys: gpu_name, driver, cuda, vram_mib, ram_gb, disk_free_gb, os_name.
    Returns a list of dicts: name, status (PASS/FAIL/MANUAL), detail."""
    rows = []
    name = info.get("gpu_name") or ""
    if not name:
        rows.append({"name": "GPU", "status": "FAIL", "detail": "nvidia-smi did not show a GPU."})
    else:
        rows.append({"name": "GPU", "status": "INFO",
                     "detail": f"{name}. Recorded only. The desktop card is unconfirmed until the install hold ends."})
    vram = int(info.get("vram_mib") or 0)
    if vram:
        rows.append({"name": "VRAM", "status": "INFO",
                     "detail": f"{vram} MiB recorded. Not a pass or fail until the card is confirmed."})
    else:
        rows.append({"name": "VRAM", "status": "INFO", "detail": "VRAM was not reported."})
    driver = _ver(info.get("driver"))
    if driver >= MIN_DRIVER:
        rows.append({"name": "Driver", "status": "PASS", "detail": info.get("driver") or ""})
    else:
        rows.append({"name": "Driver", "status": "FAIL",
                     "detail": f"{info.get('driver') or 'missing'} is older than 570. Install the current NVIDIA driver and reboot."})
    cuda = _ver(info.get("cuda"))
    if cuda >= MIN_CUDA:
        rows.append({"name": "CUDA", "status": "PASS", "detail": info.get("cuda") or ""})
    else:
        rows.append({"name": "CUDA", "status": "FAIL",
                     "detail": f"{info.get('cuda') or 'missing'} is older than 12.8. Update the driver before PyTorch."})
    ram = float(info.get("ram_gb") or 0)
    if ram >= NEED_RAM_GB:
        rows.append({"name": "RAM", "status": "PASS", "detail": f"{ram:.0f} GB"})
    elif ram >= MIN_RAM_GB:
        rows.append({"name": "RAM", "status": "FAIL",
                     "detail": f"{ram:.0f} GB. Wanted 64 GB or more. Stop and ask the owner before continuing."})
    else:
        rows.append({"name": "RAM", "status": "FAIL", "detail": f"{ram:.0f} GB is below 32 GB. Stop."})
    disk = float(info.get("disk_free_gb") or 0)
    if disk >= NEED_DISK_GB:
        rows.append({"name": "Disk", "status": "PASS", "detail": f"{disk:.0f} GB free (need {NEED_DISK_GB} GB)"})
    else:
        rows.append({"name": "Disk", "status": "FAIL",
                     "detail": f"{disk:.0f} GB free. Need {NEED_DISK_GB} GB on this drive. Stop."})
    rows.append({"name": "PSU", "status": "MANUAL",
                 "detail": "This script cannot see the power supply. Read the label and write the wattage in the step report, or write 'could not read'. Do not assume a 96 GB card."})
    rows.append({"name": "OS", "status": "INFO", "detail": info.get("os_name") or platform.platform()})
    return rows


def _live():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"],
            text=True, timeout=30).strip().splitlines()[0]
        name, driver, vram = [x.strip() for x in out.split(",")]
    except Exception as e:
        name, driver, vram = "", "", "0"
        print(f"nvidia-smi failed: {e}")
    cuda = ""
    try:
        smi = subprocess.check_output(["nvidia-smi"], text=True, timeout=30)
        m = re.search(r"CUDA Version:\s*([0-9.]+)", smi)
        cuda = m.group(1) if m else ""
    except Exception:
        pass
    mem = 0.0
    if sys.platform.startswith("linux"):
        try:
            for line in open("/proc/meminfo", encoding="utf-8"):
                if line.startswith("MemTotal:"):
                    mem = int(line.split()[1]) / (1024 ** 2)
                    break
        except OSError:
            mem = 0.0
    elif sys.platform == "win32":
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            mem = stat.ullTotalPhys / (1024 ** 3)
    free = shutil.disk_usage(os.getcwd()).free / (1024 ** 3)
    return {"gpu_name": name, "driver": driver, "cuda": cuda, "vram_mib": int(float(vram or 0)),
            "ram_gb": mem, "disk_free_gb": free, "os_name": platform.platform()}


def _print(rows):
    for row in rows:
        print(f"{row['status']:6}  {row['name']}: {row['detail']}")


def self_test():
    good = evaluate({"gpu_name": "NVIDIA RTX PRO 6000", "driver": "580.88", "cuda": "13.0",
                     "vram_mib": 98304, "ram_gb": 128, "disk_free_gb": 400, "os_name": "test"})
    assert all(r["status"] == "PASS" for r in good if r["name"] not in ("PSU", "OS", "GPU", "VRAM"))
    assert any(r["name"] == "GPU" and r["status"] == "INFO" and "6000" in r["detail"] for r in good)
    assert any(r["name"] == "VRAM" and r["status"] == "INFO" and "98304" in r["detail"] for r in good)
    assert any(r["name"] == "PSU" and r["status"] == "MANUAL" for r in good)
    missing = evaluate({"gpu_name": "", "driver": "580.88", "cuda": "13.0",
                        "vram_mib": 0, "ram_gb": 128, "disk_free_gb": 400, "os_name": "test"})
    assert any(r["name"] == "GPU" and r["status"] == "FAIL" for r in missing)
    bad = evaluate({"gpu_name": "NVIDIA GeForce RTX 4090", "driver": "550.00", "cuda": "12.4",
                    "vram_mib": 24576, "ram_gb": 16, "disk_free_gb": 40, "os_name": "test"})
    failed = {r["name"] for r in bad if r["status"] == "FAIL"}
    assert {"Driver", "CUDA", "RAM", "Disk"} <= failed
    assert any(r["name"] == "GPU" and r["status"] == "INFO" for r in bad)
    assert any(r["name"] == "VRAM" and r["status"] == "INFO" for r in bad)
    low = evaluate({"gpu_name": "NVIDIA RTX PRO 6000", "driver": "570.00", "cuda": "12.8",
                    "vram_mib": 48000, "ram_gb": 48, "disk_free_gb": 180, "os_name": "test"})
    assert any(r["name"] == "VRAM" and r["status"] == "INFO" and "48000" in r["detail"] for r in low)
    assert any(r["name"] == "RAM" and r["status"] == "FAIL" for r in low)
    print("preflight self-test passed")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Check the desktop before installing Easy Studio.")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    rows = evaluate(_live())
    if args.json:
        print(json.dumps(rows, indent=1))
    else:
        _print(rows)
    return 1 if any(r["status"] == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())

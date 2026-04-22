from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HardwareProbe:
    ram_gb: int
    cpu_count: int
    free_disk_gb: int


def probe_hardware(path: Path | None = None) -> HardwareProbe:
    probe_path = (path or Path.cwd()).resolve()
    free_disk = os.statvfs(probe_path)
    return HardwareProbe(
        ram_gb=_probe_ram_gb(),
        cpu_count=os.cpu_count() or 1,
        free_disk_gb=max(0, int((free_disk.f_bavail * free_disk.f_frsize) / (1024**3))),
    )


def _probe_ram_gb() -> int:
    try:
        import psutil  # type: ignore[import-not-found]

        total = int(psutil.virtual_memory().total)
    except Exception:
        if hasattr(os, "sysconf"):
            pages = int(os.sysconf("SC_PHYS_PAGES"))
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            total = pages * page_size
        else:
            total = 8 * 1024**3
    return max(1, int(total / (1024**3)))

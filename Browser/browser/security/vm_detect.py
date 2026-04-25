"""Best-effort virtual-machine / VDI detection for the secure kiosk.

Runs **once** at startup. Each individual check is wrapped so a single
failing probe (missing WMI, restricted permissions, …) doesn't disable
the whole detector. We intentionally over-report: a candidate sitting on
a hypervisor host is exactly what the proctor wants to see.

The detector returns a list of "indicators" - short uppercase strings -
plus an overall ``is_vm`` boolean. Callers can decide what to do with
that signal (we currently emit a ``VM_DETECTED`` telemetry event and
flip a top-bar pill).
"""

from __future__ import annotations

import ctypes
import os
import platform
import socket
import subprocess
from dataclasses import dataclass, field
from typing import Iterable

# Substrings we look for in BIOS / motherboard / system manufacturer.
# Lower-cased on the matching side. The list is non-exhaustive but
# covers the common public hypervisors.
_VM_BIOS_HINTS = (
    "vmware",
    "virtualbox",
    "vbox",
    "qemu",
    "kvm",
    "xen",
    "parallels",
    "hyper-v",
    "hyperv",
    "innotek",
    "microsoft corporation virtual",  # Hyper-V VM "System Manufacturer"
    "bochs",
    "amazon ec2",
    "google compute",
)

# Driver / device files that strongly imply a guest OS. We just check
# existence under System32\drivers - opening them could fail spuriously.
_VM_DRIVERS = (
    "vmci.sys",
    "vmmouse.sys",
    "vmusbmouse.sys",
    "vmhgfs.sys",
    "vmrawdsk.sys",
    "vboxguest.sys",
    "vboxsf.sys",
    "vboxvideo.sys",
    "prleth.sys",
    "prlfs.sys",
    "vpcbus.sys",
    "vpc-s3.sys",
    "vpcuhub.sys",
)

_VM_HOSTNAME_HINTS = ("vm-", "vbox", "vagrant", "ubuntu-virtualbox")


@dataclass
class VMDetectionResult:
    is_vm: bool
    indicators: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_payload(self) -> dict:
        return {
            "is_vm": self.is_vm,
            "indicators": self.indicators,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Individual probes
# ---------------------------------------------------------------------------
def _check_cpuid_hypervisor_bit() -> bool:
    """Read CPUID leaf 1, ECX bit 31 (the "hypervisor present" bit).

    Implemented in pure Python via ctypes shellcode would be brittle.
    We approximate by parsing ``wmic cpu`` output (Windows-only) which
    is good enough for proctoring - the bit is set whenever a hypervisor
    is hosting the VM.
    """
    try:
        out = subprocess.run(
            ["wmic", "cpu", "get", "VirtualizationFirmwareEnabled,Manufacturer"],
            capture_output=True,
            text=True,
            timeout=2.0,
        ).stdout.lower()
        # Hypervisor manufacturers we have seen reported by wmic.
        return any(
            tok in out
            for tok in ("vmware", "virtualbox", "kvm", "xen", "hyper-v", "qemu")
        )
    except Exception:
        return False


def _check_bios_strings() -> tuple[bool, dict]:
    """Pull SystemManufacturer / BIOSVersion / BaseBoardManufacturer via wmic."""
    fields = (
        "csproduct get Vendor,Name,UUID",
        "bios get Manufacturer,SMBIOSBIOSVersion,Version",
        "baseboard get Manufacturer,Product",
    )
    blob_parts: list[str] = []
    details: dict = {}
    for fld in fields:
        try:
            out = subprocess.run(
                ["wmic"] + fld.split(),
                capture_output=True,
                text=True,
                timeout=2.0,
            ).stdout
            details[fld] = out.strip()[:400]
            blob_parts.append(out.lower())
        except Exception:
            continue

    blob = "\n".join(blob_parts)
    hits = [hint for hint in _VM_BIOS_HINTS if hint in blob]
    return bool(hits), {"bios_hits": hits, **details}


def _check_drivers_present() -> list[str]:
    """Existence check on common guest-additions drivers."""
    sys32_drivers = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers"
    )
    found: list[str] = []
    try:
        if not os.path.isdir(sys32_drivers):
            return found
        for drv in _VM_DRIVERS:
            try:
                if os.path.isfile(os.path.join(sys32_drivers, drv)):
                    found.append(drv)
            except Exception:
                continue
    except Exception:
        pass
    return found


def _check_hostname() -> list[str]:
    try:
        host = socket.gethostname().lower()
    except Exception:
        return []
    return [hint for hint in _VM_HOSTNAME_HINTS if hint in host]


def _check_screen_zero_dpi() -> bool:
    """Parallels / headless VMs sometimes report 0x0 logical DPI on the primary monitor."""
    try:
        user32 = ctypes.windll.user32
        dpi = user32.GetDpiForSystem()
        if dpi == 0:
            return True
    except Exception:
        pass
    return False


def _check_total_physical_memory_low() -> tuple[bool, int]:
    """Cheap soft-signal: < 2 GiB RAM is unusual on real exam hardware."""
    try:

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_mib = int(stat.ullTotalPhys // (1024 * 1024))
            return total_mib > 0 and total_mib < 2048, total_mib
    except Exception:
        pass
    return False, 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def detect_vm() -> VMDetectionResult:
    indicators: list[str] = []
    details: dict = {"platform": platform.platform()}

    if platform.system() != "Windows":
        # Proctoring is Windows-only in production; on macOS dev we
        # short-circuit with no indicators so events stay quiet.
        return VMDetectionResult(is_vm=False, indicators=[], details=details)

    try:
        if _check_cpuid_hypervisor_bit():
            indicators.append("CPUID_HYPERVISOR_BIT")
    except Exception:
        pass

    try:
        bios_hit, bios_details = _check_bios_strings()
        details.update(bios_details)
        if bios_hit:
            indicators.append("BIOS_STRING_MATCH")
    except Exception:
        pass

    try:
        drivers = _check_drivers_present()
        if drivers:
            indicators.append("VM_DRIVER_PRESENT")
            details["drivers"] = drivers
    except Exception:
        pass

    try:
        hostname_hits = _check_hostname()
        if hostname_hits:
            indicators.append("HOSTNAME_VM_PATTERN")
            details["hostname_hits"] = hostname_hits
    except Exception:
        pass

    try:
        if _check_screen_zero_dpi():
            indicators.append("ZERO_DPI")
    except Exception:
        pass

    try:
        low_mem, total_mib = _check_total_physical_memory_low()
        details["total_memory_mib"] = total_mib
        if low_mem:
            indicators.append("LOW_PHYSICAL_MEMORY")
    except Exception:
        pass

    is_vm = bool(indicators)
    return VMDetectionResult(is_vm=is_vm, indicators=indicators, details=details)


def emit_detection(bus_emit) -> VMDetectionResult:
    """Convenience helper: run detect_vm and emit a VM_DETECTED event.

    ``bus_emit`` is a callable matching ``EventBus.emit`` so this module
    keeps zero hard dependencies on the telemetry package (importable
    from unit tests).
    """
    result = detect_vm()
    if result.is_vm:
        try:
            bus_emit(
                "vm_detected",
                payload=result.to_payload(),
                severity="critical",
            )
        except Exception:
            pass
    return result

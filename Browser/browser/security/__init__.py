"""Security helpers (VM detection, suspicious-process scanner)."""

from .suspicious_procs import scan_once
from .vm_detect import VMDetectionResult, detect_vm

__all__ = ["VMDetectionResult", "detect_vm", "scan_once"]

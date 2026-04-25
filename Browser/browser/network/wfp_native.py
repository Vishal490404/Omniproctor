"""Native Windows Filtering Platform (WFP) bindings + exam-mode session.

This module talks directly to ``fwpuclnt.dll`` the same way simplewall does
(see ``simplewall/src/wfp.c``). Filters are installed in our own provider and
sublayer at weight ``0xFFFF`` so they preempt the default Windows Firewall
sublayer; permit rules use ``FWPM_CONDITION_ALE_APP_ID`` to allow specific
executables, and a low-weight catch-all BLOCK is the fallthrough.

Why this exists when ``WfpFirewallController`` already uses NetSecurity:
    The PowerShell/NetSecurity backend only sets ``DefaultOutboundAction``
    and adds rules to the *default* sublayer. Existing explicit Allow rules
    (Edge, Microsoft Update, Defender, OneDrive, ...) sit in that same
    sublayer and beat the default action because they are more specific.
    To truly block everything except the secure browser we must own a
    higher-weight sublayer and put a BLOCK filter at the bottom of it.

Safety:
    * All filters/sublayer/provider are tagged with our Provider GUID so a
      single ``WfpExamSession.recover_stale()`` call wipes anything left
      behind by a crashed previous run.
    * Filters are added without ``FWPM_FILTER_FLAG_PERSISTENT`` so a reboot
      always clears them as a final backstop.
    * Activation runs in a single ``FwpmTransactionBegin0`` /
      ``FwpmTransactionCommit0`` envelope so a partial failure leaves the
      machine network-intact.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import uuid
from ctypes import (
    POINTER,
    Structure,
    Union,
    byref,
    c_byte,
    c_int,
    c_ubyte,
    c_uint8,
    c_uint16,
    c_uint32,
    c_uint64,
    c_void_p,
    c_wchar_p,
    sizeof,
)
from ctypes.wintypes import BYTE, DWORD, HANDLE, LPCWSTR, LPWSTR, ULONG, USHORT, WORD
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GUID type + well-known WFP GUIDs
# ---------------------------------------------------------------------------


class GUID(Structure):
    _fields_ = [
        ("Data1", DWORD),
        ("Data2", WORD),
        ("Data3", WORD),
        ("Data4", BYTE * 8),
    ]

    @classmethod
    def from_string(cls, value: str) -> "GUID":
        u = uuid.UUID(value)
        g = cls()
        g.Data1 = u.fields[0]
        g.Data2 = u.fields[1]
        g.Data3 = u.fields[2]
        rest = u.bytes[8:]
        for i, b in enumerate(rest):
            g.Data4[i] = b
        return g

    def __str__(self) -> str:
        rest = bytes(self.Data4)
        u = uuid.UUID(
            fields=(
                self.Data1,
                self.Data2,
                self.Data3,
                rest[0],
                rest[1],
                int.from_bytes(rest[2:8], "big"),
            )
        )
        return str(u)


# Well-known WFP layer / condition GUIDs (from fwpmu.h).
FWPM_LAYER_ALE_AUTH_CONNECT_V4 = GUID.from_string("c38d57d1-05a7-4c33-904f-7fbceee60e82")
FWPM_LAYER_ALE_AUTH_CONNECT_V6 = GUID.from_string("4a72393b-319f-44bc-84c3-ba54dcb3b6b4")
FWPM_LAYER_ALE_AUTH_RECV_ACCEPT_V4 = GUID.from_string("e1cd9fe7-f4b5-4273-96c0-592e487b8650")
FWPM_LAYER_ALE_AUTH_RECV_ACCEPT_V6 = GUID.from_string("a3b42c97-9f04-4672-b87e-cee9c483257f")

FWPM_CONDITION_ALE_APP_ID = GUID.from_string("d78e1e87-8644-4ea5-9437-d809ecefc971")
FWPM_CONDITION_FLAGS = GUID.from_string("632ce23b-5167-435c-86d7-e903684aa80c")
FWPM_CONDITION_IP_PROTOCOL = GUID.from_string("3971ef2b-623e-4f9a-8cb1-6e79b806b9a7")
FWPM_CONDITION_IP_REMOTE_PORT = GUID.from_string("c35a604d-d22b-4e1a-91b4-68f674ee674b")
FWPM_CONDITION_IP_LOCAL_PORT = GUID.from_string("0c1ba1af-5765-453f-af22-a8f791ac775b")

# Stable identifiers for the OmniProctor provider + sublayer. These never
# change so recover_stale() can always find what we previously installed.
GUID_OMNIPROCTOR_PROVIDER = GUID.from_string("a9e2b3c4-7d50-4f1f-9b2a-9e3a8c0fba01")
GUID_OMNIPROCTOR_SUBLAYER = GUID.from_string("a9e2b3c4-7d50-4f1f-9b2a-9e3a8c0fba02")

# Sublayer weight: max value, beats the default Windows Firewall sublayer.
SUBLAYER_WEIGHT = 0xFFFF

# Filter weights (matching simplewall conventions in wfp.h).
FW_WEIGHT_HIGHEST_IMPORTANT = 0x0F
FW_WEIGHT_HIGHEST = 0x0E
FW_WEIGHT_LOWEST = 0x08

# FWP enums and constants
FWP_ACTION_BLOCK = 0x00001001
FWP_ACTION_PERMIT = 0x00001002

FWP_MATCH_EQUAL = 0
FWP_MATCH_FLAGS_ALL_SET = 6

# FWP_DATA_TYPE enum values (from fwptypes.h). Off-by-one here will cause
# the kernel to return FWP_E_TYPE_MISMATCH (0x80320027) on FwpmFilterAdd0,
# because the runtime checks conditionValue.type against the field's
# declared dataType. Do not "guess" these values.
FWP_EMPTY = 0
FWP_UINT8 = 1
FWP_UINT16 = 2
FWP_UINT32 = 3
FWP_UINT64 = 4
FWP_INT8 = 5
FWP_INT16 = 6
FWP_INT32 = 7
FWP_INT64 = 8
FWP_FLOAT = 9
FWP_DOUBLE = 10
FWP_BYTE_ARRAY16_TYPE = 11
FWP_BYTE_BLOB_TYPE = 12
FWP_SID = 13
FWP_SECURITY_DESCRIPTOR_TYPE = 14
FWP_TOKEN_INFORMATION_TYPE = 15
FWP_TOKEN_ACCESS_INFORMATION_TYPE = 16
FWP_UNICODE_STRING_TYPE = 17
FWP_BYTE_ARRAY6_TYPE = 18

FWP_CONDITION_FLAG_IS_LOOPBACK = 0x00000001

IPPROTO_TCP = 6
IPPROTO_UDP = 17

RPC_C_AUTHN_WINNT = 10

ERROR_SUCCESS = 0
# FWP error codes (FWP_E_BASE = 0x80320000, see fwptypes.h)
FWP_E_CALLOUT_NOT_FOUND = 0x80320001
FWP_E_FILTER_NOT_FOUND = 0x80320003
FWP_E_PROVIDER_NOT_FOUND = 0x80320005
FWP_E_SUBLAYER_NOT_FOUND = 0x80320007
FWP_E_NOT_FOUND = 0x80320008
FWP_E_ALREADY_EXISTS = 0x80320009


# ---------------------------------------------------------------------------
# WFP structs (subset we use). Field order matters; do not rearrange.
# ---------------------------------------------------------------------------


class FWP_BYTE_BLOB(Structure):
    _fields_ = [
        ("size", c_uint32),
        ("data", POINTER(c_ubyte)),
    ]


class FWP_VALUE0_VALUE(Union):
    _fields_ = [
        ("uint8", c_uint8),
        ("uint16", c_uint16),
        ("uint32", c_uint32),
        ("uint64", POINTER(c_uint64)),
        ("byteBlob", POINTER(FWP_BYTE_BLOB)),
        ("sd", c_void_p),
        ("tokenInformation", c_void_p),
        ("tokenAccessInformation", POINTER(FWP_BYTE_BLOB)),
        ("unicodeString", LPWSTR),
        ("byteArray6", c_void_p),
    ]


class FWP_VALUE0(Structure):
    _fields_ = [
        ("type", c_uint32),
        ("value", FWP_VALUE0_VALUE),
    ]


class FWP_CONDITION_VALUE0(Structure):
    _fields_ = FWP_VALUE0._fields_


class FWPM_FILTER_CONDITION0(Structure):
    _fields_ = [
        ("fieldKey", GUID),
        ("matchType", c_uint32),
        ("conditionValue", FWP_CONDITION_VALUE0),
    ]


class FWPM_DISPLAY_DATA0(Structure):
    _fields_ = [
        ("name", LPWSTR),
        ("description", LPWSTR),
    ]


class FWPM_ACTION0(Structure):
    _fields_ = [
        ("type", c_uint32),
        ("filterType", GUID),
    ]


class FWPM_FILTER0_CONTEXT(Union):
    _fields_ = [
        ("rawContext", c_uint64),
        ("providerContextKey", GUID),
    ]


class FWPM_FILTER0(Structure):
    _fields_ = [
        ("filterKey", GUID),
        ("displayData", FWPM_DISPLAY_DATA0),
        ("flags", c_uint32),
        ("providerKey", POINTER(GUID)),
        ("providerData", FWP_BYTE_BLOB),
        ("layerKey", GUID),
        ("subLayerKey", GUID),
        ("weight", FWP_VALUE0),
        ("numFilterConditions", c_uint32),
        ("filterCondition", POINTER(FWPM_FILTER_CONDITION0)),
        ("action", FWPM_ACTION0),
        ("context", FWPM_FILTER0_CONTEXT),
        ("reserved", POINTER(GUID)),
        ("filterId", c_uint64),
        ("effectiveWeight", FWP_VALUE0),
    ]


class FWPM_PROVIDER0(Structure):
    _fields_ = [
        ("providerKey", GUID),
        ("displayData", FWPM_DISPLAY_DATA0),
        ("flags", c_uint32),
        ("providerData", FWP_BYTE_BLOB),
        ("serviceName", LPWSTR),
    ]


class FWPM_SUBLAYER0(Structure):
    _fields_ = [
        ("subLayerKey", GUID),
        ("displayData", FWPM_DISPLAY_DATA0),
        ("flags", c_uint32),
        ("providerKey", POINTER(GUID)),
        ("providerData", FWP_BYTE_BLOB),
        ("weight", c_uint16),
    ]


# ---------------------------------------------------------------------------
# fwpuclnt.dll bindings
# ---------------------------------------------------------------------------


def _load_fwpuclnt() -> ctypes.WinDLL:
    if sys.platform != "win32":
        raise RuntimeError("WFP native backend is only available on Windows")
    return ctypes.WinDLL("fwpuclnt.dll", use_last_error=True)


_fwpu = _load_fwpuclnt() if sys.platform == "win32" else None


def _bind(name: str, restype, argtypes):
    if _fwpu is None:
        return None
    fn = getattr(_fwpu, name)
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


FwpmEngineOpen0 = _bind(
    "FwpmEngineOpen0",
    DWORD,
    [LPCWSTR, DWORD, c_void_p, c_void_p, POINTER(HANDLE)],
)
FwpmEngineClose0 = _bind("FwpmEngineClose0", DWORD, [HANDLE])

FwpmTransactionBegin0 = _bind("FwpmTransactionBegin0", DWORD, [HANDLE, DWORD])
FwpmTransactionCommit0 = _bind("FwpmTransactionCommit0", DWORD, [HANDLE])
FwpmTransactionAbort0 = _bind("FwpmTransactionAbort0", DWORD, [HANDLE])

FwpmProviderAdd0 = _bind(
    "FwpmProviderAdd0", DWORD, [HANDLE, POINTER(FWPM_PROVIDER0), c_void_p]
)
FwpmProviderDeleteByKey0 = _bind(
    "FwpmProviderDeleteByKey0", DWORD, [HANDLE, POINTER(GUID)]
)

FwpmSubLayerAdd0 = _bind(
    "FwpmSubLayerAdd0", DWORD, [HANDLE, POINTER(FWPM_SUBLAYER0), c_void_p]
)
FwpmSubLayerDeleteByKey0 = _bind(
    "FwpmSubLayerDeleteByKey0", DWORD, [HANDLE, POINTER(GUID)]
)

FwpmFilterAdd0 = _bind(
    "FwpmFilterAdd0",
    DWORD,
    [HANDLE, POINTER(FWPM_FILTER0), c_void_p, POINTER(c_uint64)],
)
FwpmFilterDeleteByKey0 = _bind(
    "FwpmFilterDeleteByKey0", DWORD, [HANDLE, POINTER(GUID)]
)

FwpmGetAppIdFromFileName0 = _bind(
    "FwpmGetAppIdFromFileName0",
    DWORD,
    [LPCWSTR, POINTER(POINTER(FWP_BYTE_BLOB))],
)
FwpmFreeMemory0 = _bind("FwpmFreeMemory0", None, [POINTER(c_void_p)])


# Filter enumeration (used by recover_stale to wipe by provider GUID).
FwpmFilterCreateEnumHandle0 = _bind(
    "FwpmFilterCreateEnumHandle0",
    DWORD,
    [HANDLE, c_void_p, POINTER(HANDLE)],
)
FwpmFilterEnum0 = _bind(
    "FwpmFilterEnum0",
    DWORD,
    [HANDLE, HANDLE, c_uint32, POINTER(POINTER(POINTER(FWPM_FILTER0))), POINTER(c_uint32)],
)
FwpmFilterDestroyEnumHandle0 = _bind(
    "FwpmFilterDestroyEnumHandle0", DWORD, [HANDLE, HANDLE]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check(code: int, op: str) -> None:
    if code != ERROR_SUCCESS:
        raise OSError(code, f"WFP call {op} failed (0x{code:08X})")


def _make_uint8_value(v: int) -> FWP_VALUE0:
    val = FWP_VALUE0()
    val.type = FWP_UINT8
    val.value.uint8 = v
    return val


def _make_uint16_value(v: int) -> FWP_VALUE0:
    val = FWP_VALUE0()
    val.type = FWP_UINT16
    val.value.uint16 = v
    return val


def _make_uint32_value(v: int) -> FWP_VALUE0:
    val = FWP_VALUE0()
    val.type = FWP_UINT32
    val.value.uint32 = v
    return val


def _canonicalize_win32_path(file_path: str) -> str:
    """Convert a possibly-mixed-slash path into the form WFP expects.

    Steps:
        1. ``os.path.abspath`` to anchor relative paths.
        2. ``os.path.normpath`` to convert forward slashes to backslashes
           and collapse ``.`` / ``..`` segments. ``FwpmGetAppIdFromFileName0``
           takes a "fully-qualified Win32 path" and Win32 path parsing
           splits on backslash only — a mixed-slash path produces an app-ID
           blob that never matches the kernel-resolved NT device path of
           the running process.
        3. ``GetLongPathNameW`` on Windows to flatten any 8.3 short-name
           components (e.g. ``DESKTO~1``) into the long form WFP normalizes to.
    """
    p = os.path.abspath(file_path)
    p = os.path.normpath(p)
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            GetLongPathNameW = kernel32.GetLongPathNameW
            GetLongPathNameW.argtypes = [LPCWSTR, LPWSTR, c_uint32]
            GetLongPathNameW.restype = c_uint32
            buf = ctypes.create_unicode_buffer(32768)
            rc = GetLongPathNameW(p, buf, 32768)
            if rc and rc < 32768:
                p = buf.value
        except Exception:
            pass
    return p


def _resolve_app_id(engine: HANDLE, file_path: str) -> POINTER(FWP_BYTE_BLOB):
    """Return a heap-allocated FWP_BYTE_BLOB describing the executable.

    Caller is responsible for freeing with ``FwpmFreeMemory0``.
    """
    if FwpmGetAppIdFromFileName0 is None:
        raise RuntimeError("fwpuclnt.dll is not available")
    canonical = _canonicalize_win32_path(file_path)
    blob_ptr = POINTER(FWP_BYTE_BLOB)()
    code = FwpmGetAppIdFromFileName0(canonical, byref(blob_ptr))
    _check(code, f"FwpmGetAppIdFromFileName0({canonical})")
    blob_size = blob_ptr.contents.size if blob_ptr else 0
    logger.info(
        "Resolved app-ID for %s -> blob size=%d bytes (%d UTF-16 chars including NUL)",
        canonical,
        blob_size,
        blob_size // 2,
    )
    return blob_ptr


# ---------------------------------------------------------------------------
# WfpExamSession
# ---------------------------------------------------------------------------


class WfpExamSession:
    """Owns the provider, sublayer, and filter set for one exam session."""

    PROVIDER_NAME = "OmniProctor Exam Filter"
    SUBLAYER_NAME = "OmniProctor Exam Sublayer"

    def __init__(self, allow_app_paths: Iterable[str]):
        if sys.platform != "win32":
            raise RuntimeError("WFP native backend is only available on Windows")
        self._engine: HANDLE = HANDLE()
        self._engine_open = False
        self._installed_filter_keys: list[GUID] = []
        self._sublayer_added = False
        self._provider_added = False
        self._allow_app_paths = [
            _canonicalize_win32_path(p)
            for p in allow_app_paths
            if p and os.path.exists(p)
        ]
        self._app_id_blobs: list[POINTER(FWP_BYTE_BLOB)] = []

    # -- engine lifecycle ---------------------------------------------------

    def _open_engine(self) -> None:
        if self._engine_open:
            return
        if FwpmEngineOpen0 is None:
            raise RuntimeError("fwpuclnt.dll bindings unavailable")
        code = FwpmEngineOpen0(None, RPC_C_AUTHN_WINNT, None, None, byref(self._engine))
        _check(code, "FwpmEngineOpen0")
        self._engine_open = True

    def _close_engine(self) -> None:
        if not self._engine_open:
            return
        try:
            FwpmEngineClose0(self._engine)
        except Exception:
            pass
        self._engine_open = False

    def _free_app_id_blobs(self) -> None:
        for blob_ptr in self._app_id_blobs:
            try:
                p = c_void_p(ctypes.addressof(blob_ptr.contents))
                FwpmFreeMemory0(byref(p))
            except Exception:
                pass
        self._app_id_blobs.clear()

    # -- provider / sublayer ------------------------------------------------

    def _ensure_provider_and_sublayer(self) -> None:
        provider = FWPM_PROVIDER0()
        provider.providerKey = GUID_OMNIPROCTOR_PROVIDER
        provider.displayData.name = self.PROVIDER_NAME
        provider.displayData.description = "App-level network lockdown for exams"
        provider.flags = 0
        code = FwpmProviderAdd0(self._engine, byref(provider), None)
        if code in (ERROR_SUCCESS, FWP_E_ALREADY_EXISTS):
            self._provider_added = True
        else:
            _check(code, "FwpmProviderAdd0")

        provider_key = GUID_OMNIPROCTOR_PROVIDER
        sublayer = FWPM_SUBLAYER0()
        sublayer.subLayerKey = GUID_OMNIPROCTOR_SUBLAYER
        sublayer.displayData.name = self.SUBLAYER_NAME
        sublayer.displayData.description = "OmniProctor high-priority exam sublayer"
        sublayer.flags = 0
        sublayer.providerKey = ctypes.pointer(provider_key)
        sublayer.weight = SUBLAYER_WEIGHT
        code = FwpmSubLayerAdd0(self._engine, byref(sublayer), None)
        if code in (ERROR_SUCCESS, FWP_E_ALREADY_EXISTS):
            self._sublayer_added = True
        else:
            _check(code, "FwpmSubLayerAdd0")

    # -- filter primitives --------------------------------------------------

    def _add_filter(
        self,
        layer: GUID,
        action: int,
        weight: int,
        name: str,
        conditions: Optional[list[FWPM_FILTER_CONDITION0]] = None,
    ) -> None:
        flt = FWPM_FILTER0()
        flt.filterKey = GUID.from_string(str(uuid.uuid4()))
        flt.displayData.name = name
        flt.displayData.description = name
        flt.flags = 0
        provider_key = GUID_OMNIPROCTOR_PROVIDER
        flt.providerKey = ctypes.pointer(provider_key)
        flt.layerKey = layer
        flt.subLayerKey = GUID_OMNIPROCTOR_SUBLAYER
        flt.weight = _make_uint8_value(weight)
        flt.action.type = action

        cond_count = len(conditions) if conditions else 0
        if cond_count:
            arr = (FWPM_FILTER_CONDITION0 * cond_count)(*conditions)
            flt.numFilterConditions = cond_count
            flt.filterCondition = ctypes.cast(arr, POINTER(FWPM_FILTER_CONDITION0))
            # Keep the array alive past this function so the kernel copy
            # completes even if Python GC runs during FwpmFilterAdd0.
            flt._py_conditions = arr
        else:
            flt.numFilterConditions = 0
            flt.filterCondition = ctypes.cast(None, POINTER(FWPM_FILTER_CONDITION0))

        filter_id = c_uint64(0)
        code = FwpmFilterAdd0(self._engine, byref(flt), None, byref(filter_id))
        _check(code, f"FwpmFilterAdd0({name})")
        self._installed_filter_keys.append(flt.filterKey)

    # -- condition builders -------------------------------------------------

    def _cond_app_id(self, blob_ptr: POINTER(FWP_BYTE_BLOB)) -> FWPM_FILTER_CONDITION0:
        cond = FWPM_FILTER_CONDITION0()
        cond.fieldKey = FWPM_CONDITION_ALE_APP_ID
        cond.matchType = FWP_MATCH_EQUAL
        cond.conditionValue.type = FWP_BYTE_BLOB_TYPE
        cond.conditionValue.value.byteBlob = blob_ptr
        return cond

    def _cond_loopback(self) -> FWPM_FILTER_CONDITION0:
        cond = FWPM_FILTER_CONDITION0()
        cond.fieldKey = FWPM_CONDITION_FLAGS
        cond.matchType = FWP_MATCH_FLAGS_ALL_SET
        cond.conditionValue.type = FWP_UINT32
        cond.conditionValue.value.uint32 = FWP_CONDITION_FLAG_IS_LOOPBACK
        return cond

    def _cond_protocol(self, proto: int) -> FWPM_FILTER_CONDITION0:
        cond = FWPM_FILTER_CONDITION0()
        cond.fieldKey = FWPM_CONDITION_IP_PROTOCOL
        cond.matchType = FWP_MATCH_EQUAL
        cond.conditionValue.type = FWP_UINT8
        cond.conditionValue.value.uint8 = proto
        return cond

    def _cond_remote_port(self, port: int) -> FWPM_FILTER_CONDITION0:
        cond = FWPM_FILTER_CONDITION0()
        cond.fieldKey = FWPM_CONDITION_IP_REMOTE_PORT
        cond.matchType = FWP_MATCH_EQUAL
        cond.conditionValue.type = FWP_UINT16
        cond.conditionValue.value.uint16 = port
        return cond

    def _cond_local_port(self, port: int) -> FWPM_FILTER_CONDITION0:
        cond = FWPM_FILTER_CONDITION0()
        cond.fieldKey = FWPM_CONDITION_IP_LOCAL_PORT
        cond.matchType = FWP_MATCH_EQUAL
        cond.conditionValue.type = FWP_UINT16
        cond.conditionValue.value.uint16 = port
        return cond

    # -- high-level filter set ---------------------------------------------

    def _install_filter_set(self) -> None:
        outbound_layers = (
            ("v4_out", FWPM_LAYER_ALE_AUTH_CONNECT_V4),
            ("v6_out", FWPM_LAYER_ALE_AUTH_CONNECT_V6),
        )
        inbound_layers = (
            ("v4_in", FWPM_LAYER_ALE_AUTH_RECV_ACCEPT_V4),
            ("v6_in", FWPM_LAYER_ALE_AUTH_RECV_ACCEPT_V6),
        )

        for label, layer in outbound_layers + inbound_layers:
            for path in self._allow_app_paths:
                blob_ptr = _resolve_app_id(self._engine, path)
                self._app_id_blobs.append(blob_ptr)
                self._add_filter(
                    layer=layer,
                    action=FWP_ACTION_PERMIT,
                    weight=FW_WEIGHT_HIGHEST_IMPORTANT,
                    name=f"OmniProctor_Allow_App_{os.path.basename(path)}_{label}",
                    conditions=[self._cond_app_id(blob_ptr)],
                )

            self._add_filter(
                layer=layer,
                action=FWP_ACTION_PERMIT,
                weight=FW_WEIGHT_HIGHEST,
                name=f"OmniProctor_Allow_Loopback_{label}",
                conditions=[self._cond_loopback()],
            )

        # DNS + DHCP (outbound only — the system needs to *initiate* these).
        for label, layer in outbound_layers:
            self._add_filter(
                layer=layer,
                action=FWP_ACTION_PERMIT,
                weight=FW_WEIGHT_HIGHEST,
                name=f"OmniProctor_Allow_DNS_UDP_{label}",
                conditions=[self._cond_protocol(IPPROTO_UDP), self._cond_remote_port(53)],
            )
            self._add_filter(
                layer=layer,
                action=FWP_ACTION_PERMIT,
                weight=FW_WEIGHT_HIGHEST,
                name=f"OmniProctor_Allow_DNS_TCP_{label}",
                conditions=[self._cond_protocol(IPPROTO_TCP), self._cond_remote_port(53)],
            )
            self._add_filter(
                layer=layer,
                action=FWP_ACTION_PERMIT,
                weight=FW_WEIGHT_HIGHEST,
                name=f"OmniProctor_Allow_DHCP_{label}",
                conditions=[self._cond_protocol(IPPROTO_UDP), self._cond_remote_port(67)],
            )

        # Catch-all BLOCK at lowest weight in our sublayer so the kernel
        # treats unmatched traffic as denied. Because our sublayer weight
        # is 0xFFFF, this beats any allow rule sitting in the default
        # Windows Firewall sublayer.
        for label, layer in outbound_layers + inbound_layers:
            self._add_filter(
                layer=layer,
                action=FWP_ACTION_BLOCK,
                weight=FW_WEIGHT_LOWEST,
                name=f"OmniProctor_Block_All_{label}",
                conditions=None,
            )

    # -- public API ---------------------------------------------------------

    def install(self) -> None:
        """Install the full exam-mode filter set atomically."""
        self._open_engine()

        # Always wipe stale state first so a previous crashed run can never
        # leave us in a half-installed condition.
        self._wipe_provider_state(open_engine=False)

        code = FwpmTransactionBegin0(self._engine, 0)
        _check(code, "FwpmTransactionBegin0")
        try:
            self._ensure_provider_and_sublayer()
            self._install_filter_set()
            code = FwpmTransactionCommit0(self._engine)
            _check(code, "FwpmTransactionCommit0")
            logger.info(
                "WFP exam session installed: %d filters, %d allowed apps",
                len(self._installed_filter_keys),
                len(self._allow_app_paths),
            )
        except Exception:
            try:
                FwpmTransactionAbort0(self._engine)
            except Exception:
                pass
            self._installed_filter_keys.clear()
            self._provider_added = False
            self._sublayer_added = False
            self._free_app_id_blobs()
            raise

    def uninstall(self) -> None:
        """Remove every filter, sublayer, and provider this session installed."""
        if not self._engine_open:
            self._open_engine()

        code = FwpmTransactionBegin0(self._engine, 0)
        try:
            _check(code, "FwpmTransactionBegin0")
            for key in self._installed_filter_keys:
                rc = FwpmFilterDeleteByKey0(self._engine, byref(key))
                if rc not in (ERROR_SUCCESS, FWP_E_FILTER_NOT_FOUND):
                    logger.warning("FwpmFilterDeleteByKey0 returned 0x%08X", rc)
            if self._sublayer_added:
                key = GUID_OMNIPROCTOR_SUBLAYER
                rc = FwpmSubLayerDeleteByKey0(self._engine, byref(key))
                if rc not in (ERROR_SUCCESS, FWP_E_SUBLAYER_NOT_FOUND):
                    logger.warning("FwpmSubLayerDeleteByKey0 returned 0x%08X", rc)
            if self._provider_added:
                key = GUID_OMNIPROCTOR_PROVIDER
                rc = FwpmProviderDeleteByKey0(self._engine, byref(key))
                if rc not in (ERROR_SUCCESS, FWP_E_PROVIDER_NOT_FOUND):
                    logger.warning("FwpmProviderDeleteByKey0 returned 0x%08X", rc)
            FwpmTransactionCommit0(self._engine)
        except Exception as exc:
            logger.error("WFP uninstall transaction failed, aborting: %s", exc)
            try:
                FwpmTransactionAbort0(self._engine)
            except Exception:
                pass

        self._installed_filter_keys.clear()
        self._provider_added = False
        self._sublayer_added = False
        self._free_app_id_blobs()
        self._close_engine()

    # -- recovery -----------------------------------------------------------

    def _wipe_provider_state(self, open_engine: bool = True) -> int:
        """Delete every filter/sublayer/provider tagged with our GUIDs.

        Returns the number of filters removed. Safe to call multiple times.
        """
        if open_engine:
            self._open_engine()

        if FwpmFilterCreateEnumHandle0 is None:
            return 0

        enum_handle = HANDLE()
        code = FwpmFilterCreateEnumHandle0(self._engine, None, byref(enum_handle))
        if code != ERROR_SUCCESS:
            logger.debug("FwpmFilterCreateEnumHandle0 failed 0x%08X", code)
            return 0

        removed = 0
        try:
            entries_returned = c_uint32(0)
            entries_ptr = POINTER(POINTER(FWPM_FILTER0))()
            code = FwpmFilterEnum0(
                self._engine,
                enum_handle,
                4096,
                byref(entries_ptr),
                byref(entries_returned),
            )
            if code != ERROR_SUCCESS:
                return 0

            for i in range(entries_returned.value):
                f = entries_ptr[i].contents
                if not f.providerKey:
                    continue
                pk = f.providerKey.contents
                if (
                    pk.Data1 == GUID_OMNIPROCTOR_PROVIDER.Data1
                    and pk.Data2 == GUID_OMNIPROCTOR_PROVIDER.Data2
                    and pk.Data3 == GUID_OMNIPROCTOR_PROVIDER.Data3
                    and bytes(pk.Data4) == bytes(GUID_OMNIPROCTOR_PROVIDER.Data4)
                ):
                    rc = FwpmFilterDeleteByKey0(self._engine, byref(f.filterKey))
                    if rc == ERROR_SUCCESS:
                        removed += 1

            # Free buffer returned by FwpmFilterEnum0.
            try:
                p = c_void_p(ctypes.addressof(entries_ptr.contents))
                FwpmFreeMemory0(byref(p))
            except Exception:
                pass
        finally:
            FwpmFilterDestroyEnumHandle0(self._engine, enum_handle)

        sublayer_key = GUID_OMNIPROCTOR_SUBLAYER
        rc = FwpmSubLayerDeleteByKey0(self._engine, byref(sublayer_key))
        if rc == ERROR_SUCCESS:
            logger.info("Removed stale OmniProctor sublayer")

        provider_key = GUID_OMNIPROCTOR_PROVIDER
        rc = FwpmProviderDeleteByKey0(self._engine, byref(provider_key))
        if rc == ERROR_SUCCESS:
            logger.info("Removed stale OmniProctor provider")

        if removed:
            logger.info("Removed %d stale OmniProctor WFP filters", removed)
        return removed


def recover_stale() -> int:
    """Module-level helper: wipe everything ever installed by this module.

    Returns the count of filters removed. Used by ``--firewall-recover`` and
    by the emergency cleanup path. Safe to call when nothing is installed.
    """
    if sys.platform != "win32":
        return 0
    session = WfpExamSession(allow_app_paths=[])
    try:
        return session._wipe_provider_state()
    finally:
        session._close_engine()


def is_supported() -> bool:
    """Whether this Python process can actually drive the WFP backend."""
    if sys.platform != "win32":
        return False
    return _fwpu is not None and FwpmEngineOpen0 is not None

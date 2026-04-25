import abc
import ctypes
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum

try:
    from . import wfp_native
except ImportError:
    try:
        import wfp_native  # type: ignore
    except ImportError:
        wfp_native = None  # type: ignore

logger = logging.getLogger(__name__)

RULE_PREFIX = "OmniProctor_Exam"
RULE_BROWSER_ALLOW = f"{RULE_PREFIX}_AllowBrowser"
RULE_DNS_ALLOW = f"{RULE_PREFIX}_AllowDNS"
FIREWALL_RULE_NAMES = (RULE_BROWSER_ALLOW, RULE_DNS_ALLOW)
FIREWALL_BACKEND_ENV = "OMNIPROCTOR_FIREWALL_BACKEND"
ALLOW_NETSH_FALLBACK_ENV = "OMNIPROCTOR_FIREWALL_ALLOW_NETSH_FALLBACK"
EXTRA_ALLOW_PATHS_ENV = "OMNIPROCTOR_FIREWALL_EXTRA_ALLOW_PATHS"


class FirewallState(str, Enum):
    INACTIVE = "inactive"
    ACTIVATING = "activating"
    ACTIVE = "active"
    ROLLBACK = "rollback"


@dataclass
class FirewallProfileSnapshot:
    profile: str
    inbound_action: str
    outbound_action: str


class AdminRightsError(Exception):
    pass


class FirewallConfigurationError(Exception):
    pass


def _check_admin_rights() -> None:
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin = False
    if not is_admin:
        raise AdminRightsError("Administrator privileges are required for firewall operations")


def _create_no_window_flag() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


class FirewallControllerBase(abc.ABC):
    def __init__(self, browser_executable_path: str):
        if not browser_executable_path:
            raise ValueError("browser_executable_path must be provided")
        self.browser_exe = browser_executable_path
        self._state = FirewallState.INACTIVE
        _check_admin_rights()

    @property
    def state(self) -> FirewallState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state == FirewallState.ACTIVE

    @abc.abstractmethod
    def enter_exam_mode(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def exit_exam_mode(self) -> bool:
        raise NotImplementedError


class WfpFirewallController(FirewallControllerBase):
    """WFP-backed firewall controller using NetSecurity PowerShell cmdlets.

    This keeps policy/rule ownership contained to OmniProctor and performs
    deterministic rollback when activation fails mid-flight.
    """

    def __init__(self, browser_executable_path: str):
        super().__init__(browser_executable_path)
        self._snapshot: dict[str, FirewallProfileSnapshot] = {}
        self._created_rules: set[str] = set()

    @staticmethod
    def _run_powershell(script: str, timeout: int = 25) -> subprocess.CompletedProcess:
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]
        logger.debug("Running powershell command")
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_create_no_window_flag(),
        )

    @staticmethod
    def _run_netsh(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["netsh"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_create_no_window_flag(),
        )

    def _ensure_powershell_ready(self) -> None:
        result = self._run_powershell("$PSVersionTable.PSVersion.Major")
        if result.returncode != 0:
            raise FirewallConfigurationError(
                f"PowerShell unavailable: {result.stderr.strip() or result.stdout.strip()}"
            )
        try:
            major = int((result.stdout or "0").strip().splitlines()[-1])
        except Exception as exc:
            raise FirewallConfigurationError("Unable to detect PowerShell version") from exc
        if major < 5:
            raise FirewallConfigurationError(
                "PowerShell 5+ is required for NetSecurity firewall commands"
            )

    def _snapshot_profiles(self) -> bool:
        script = (
            "Get-NetFirewallProfile -Profile Domain,Private,Public | "
            "Select-Object Name,DefaultInboundAction,DefaultOutboundAction | "
            "ConvertTo-Json -Compress"
        )
        result = self._run_powershell(script)
        if result.returncode != 0 or not result.stdout.strip():
            logger.error("Failed to snapshot firewall profile state: %s", result.stderr.strip())
            return False
        try:
            payload = json.loads(result.stdout.strip())
            profiles = payload if isinstance(payload, list) else [payload]
            snapshot: dict[str, FirewallProfileSnapshot] = {}
            for item in profiles:
                profile_name = str(item.get("Name", "")).lower()
                snapshot[profile_name] = FirewallProfileSnapshot(
                    profile=profile_name,
                    inbound_action=str(item.get("DefaultInboundAction", "Block")),
                    outbound_action=str(item.get("DefaultOutboundAction", "Allow")),
                )
            if len(snapshot) < 3:
                logger.warning("Firewall snapshot incomplete; continuing with captured profiles only")
            self._snapshot = snapshot
            return True
        except Exception as exc:
            logger.error("Could not parse firewall profile snapshot: %s", exc)
            return False

    def _set_outbound_block(self) -> bool:
        script = (
            "Set-NetFirewallProfile -Profile Domain,Private,Public "
            "-DefaultOutboundAction Block"
        )
        result = self._run_powershell(script)
        if result.returncode == 0:
            logger.info("Set DefaultOutboundAction=Block for Domain/Private/Public profiles")
            return True
        logger.error("Failed to set outbound block policy: %s", result.stderr.strip())
        return False

    def _restore_profile_actions(self) -> bool:
        if not self._snapshot:
            logger.warning("No firewall profile snapshot available; using allowoutbound fallback")
            success = True
            for profile in ("domainprofile", "privateprofile", "publicprofile"):
                result = self._run_netsh(
                    ["advfirewall", "set", profile, "firewallpolicy", "blockinbound,allowoutbound"]
                )
                success = success and result.returncode == 0
            return success

        success = True
        for profile in self._snapshot.values():
            script = (
                f"Set-NetFirewallProfile -Profile {profile.profile} "
                f"-DefaultInboundAction {profile.inbound_action} "
                f"-DefaultOutboundAction {profile.outbound_action}"
            )
            result = self._run_powershell(script)
            if result.returncode != 0:
                success = False
                logger.error(
                    "Failed to restore firewall profile %s: %s",
                    profile.profile,
                    result.stderr.strip(),
                )
        return success

    def _delete_rule(self, rule_name: str) -> None:
        script = (
            f"Get-NetFirewallRule -DisplayName '{rule_name}' -ErrorAction SilentlyContinue | "
            "Remove-NetFirewallRule -ErrorAction SilentlyContinue"
        )
        try:
            self._run_powershell(script)
        except Exception:
            pass
        self._created_rules.discard(rule_name)

    def _create_allow_browser_rule(self) -> bool:
        self._delete_rule(RULE_BROWSER_ALLOW)
        escaped_program = self.browser_exe.replace("'", "''")
        script = (
            f"New-NetFirewallRule -DisplayName '{RULE_BROWSER_ALLOW}' "
            f"-Direction Outbound -Action Allow -Program '{escaped_program}' "
            "-Profile Any -Enabled True"
        )
        result = self._run_powershell(script)
        if result.returncode == 0:
            self._created_rules.add(RULE_BROWSER_ALLOW)
            logger.info("Created allow rule for browser executable: %s", self.browser_exe)
            return True
        logger.error("Failed to create browser allow rule: %s", result.stderr.strip())
        return False

    def _create_allow_dns_rule(self) -> bool:
        self._delete_rule(RULE_DNS_ALLOW)
        script = (
            f"New-NetFirewallRule -DisplayName '{RULE_DNS_ALLOW}' "
            "-Direction Outbound -Action Allow -Protocol UDP -RemotePort 53 "
            "-Profile Any -Enabled True"
        )
        result = self._run_powershell(script)
        if result.returncode == 0:
            self._created_rules.add(RULE_DNS_ALLOW)
            logger.info("Created allow DNS rule for UDP/53")
            return True
        logger.error("Failed to create DNS allow rule: %s", result.stderr.strip())
        return False

    def _cleanup_rules(self) -> None:
        for rule_name in FIREWALL_RULE_NAMES:
            self._delete_rule(rule_name)
        logger.info("Firewall rules removed")

    def _rollback_activation(self) -> bool:
        self._state = FirewallState.ROLLBACK
        logger.warning("Rolling back firewall activation changes")
        cleanup_ok = True
        try:
            self._cleanup_rules()
        except Exception as exc:
            cleanup_ok = False
            logger.error("Failed to cleanup rules during rollback: %s", exc)
        restore_ok = self._restore_profile_actions()
        self._state = FirewallState.INACTIVE
        return cleanup_ok and restore_ok

    def enter_exam_mode(self) -> bool:
        if self._state == FirewallState.ACTIVE:
            logger.info("Firewall exam mode already active")
            return True

        logger.info("=== ENTERING EXAM MODE (WFP backend) ===")
        self._state = FirewallState.ACTIVATING

        try:
            self._ensure_powershell_ready()
            if not self._snapshot_profiles():
                raise FirewallConfigurationError("Unable to capture firewall baseline")
            if not self._create_allow_browser_rule():
                raise FirewallConfigurationError("Unable to create browser allow rule")
            if not self._create_allow_dns_rule():
                raise FirewallConfigurationError("Unable to create DNS allow rule")
            if not self._set_outbound_block():
                raise FirewallConfigurationError("Unable to enforce outbound blocking")
        except Exception as exc:
            logger.error("Failed to activate firewall exam mode: %s", exc)
            self._rollback_activation()
            return False

        self._state = FirewallState.ACTIVE
        logger.info("=== EXAM MODE ACTIVE (WFP backend) ===")
        return True

    def exit_exam_mode(self) -> bool:
        if self._state == FirewallState.INACTIVE:
            logger.info("Firewall exam mode already inactive")
            return True

        logger.info("=== EXITING EXAM MODE (WFP backend) ===")
        self._state = FirewallState.ROLLBACK
        try:
            self._cleanup_rules()
            restored = self._restore_profile_actions()
            self._state = FirewallState.INACTIVE
            logger.info("=== EXAM MODE EXITED (WFP backend) ===")
            return restored
        except Exception as exc:
            logger.error("Error exiting WFP exam mode: %s", exc)
            self._state = FirewallState.INACTIVE
            return False


class NetshFirewallController(FirewallControllerBase):
    """Compatibility fallback backend."""

    @staticmethod
    def _run_netsh(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
        cmd = ["netsh"] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_create_no_window_flag(),
        )

    def _set_outbound_policy(self, policy: str) -> bool:
        success = True
        for profile in ("domainprofile", "privateprofile", "publicprofile"):
            result = self._run_netsh(
                ["advfirewall", "set", profile, "firewallpolicy", f"blockinbound,{policy}"]
            )
            if result.returncode != 0:
                success = False
        return success

    def _delete_rule(self, name: str) -> None:
        self._run_netsh(["advfirewall", "firewall", "delete", "rule", f"name={name}"])

    def _cleanup_rules(self) -> None:
        for name in FIREWALL_RULE_NAMES:
            self._delete_rule(name)

    def _add_browser_allow_rule(self) -> bool:
        self._delete_rule(RULE_BROWSER_ALLOW)
        result = self._run_netsh(
            [
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={RULE_BROWSER_ALLOW}",
                "dir=out",
                "action=allow",
                f"program={self.browser_exe}",
                "enable=yes",
                "profile=any",
            ]
        )
        return result.returncode == 0

    def _add_dns_allow_rule(self) -> bool:
        self._delete_rule(RULE_DNS_ALLOW)
        result = self._run_netsh(
            [
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={RULE_DNS_ALLOW}",
                "dir=out",
                "action=allow",
                "protocol=udp",
                "remoteport=53",
                "enable=yes",
                "profile=any",
            ]
        )
        return result.returncode == 0

    def enter_exam_mode(self) -> bool:
        logger.info("=== ENTERING EXAM MODE (netsh fallback) ===")
        self._state = FirewallState.ACTIVATING
        try:
            if not self._add_browser_allow_rule():
                raise FirewallConfigurationError("Failed to add browser allow rule")
            if not self._add_dns_allow_rule():
                raise FirewallConfigurationError("Failed to add DNS allow rule")
            if not self._set_outbound_policy("blockoutbound"):
                raise FirewallConfigurationError("Failed to set outbound block policy")
        except Exception as exc:
            logger.error("netsh fallback activation failed: %s", exc)
            self._cleanup_rules()
            self._set_outbound_policy("allowoutbound")
            self._state = FirewallState.INACTIVE
            return False
        self._state = FirewallState.ACTIVE
        return True

    def exit_exam_mode(self) -> bool:
        logger.info("=== EXITING EXAM MODE (netsh fallback) ===")
        try:
            self._cleanup_rules()
            self._set_outbound_policy("allowoutbound")
            self._state = FirewallState.INACTIVE
            return True
        except Exception:
            self._state = FirewallState.INACTIVE
            return False


class WfpNativeFirewallController(FirewallControllerBase):
    """App-level WFP backend that talks to fwpuclnt.dll directly.

    Modeled on ``simplewall``: installs filters in our own provider/sublayer
    at weight 0xFFFF so they preempt any pre-existing Windows Firewall allow
    rule in the default sublayer. This is the only backend that actually
    blocks other apps' traffic when, for example, Microsoft Edge or Defender
    has already added explicit allow rules for itself.
    """

    def __init__(self, browser_executable_path: str):
        super().__init__(browser_executable_path)
        if wfp_native is None or not wfp_native.is_supported():
            raise FirewallConfigurationError(
                "wfp_native bindings are not available on this platform"
            )
        self._session: "wfp_native.WfpExamSession | None" = None
        self.last_error: str | None = None

    def _build_allow_paths(self) -> list[str]:
        paths: list[str] = []
        if self.browser_exe:
            paths.append(self.browser_exe)

        # When the kiosk runs from source (dev mode) the actual TCP traffic
        # comes from the python.exe interpreter, not from a packaged .exe.
        # Add the current interpreter as well so dev sessions stay usable.
        try:
            exe = os.path.abspath(sys.executable)
        except Exception:
            exe = ""
        if exe and exe.lower() != os.path.abspath(self.browser_exe).lower():
            paths.append(exe)

        extras = os.getenv(EXTRA_ALLOW_PATHS_ENV, "")
        if extras:
            for raw in extras.split(os.pathsep):
                raw = raw.strip().strip('"')
                if raw:
                    paths.append(raw)

        seen: set[str] = set()
        deduped: list[str] = []
        for p in paths:
            key = os.path.abspath(p).lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(p)
        return deduped

    def enter_exam_mode(self) -> bool:
        import traceback as _tb
        if self._state == FirewallState.ACTIVE:
            return True
        logger.info("=== ENTERING EXAM MODE (wfp_native backend) ===")
        self._state = FirewallState.ACTIVATING
        self.last_error = None
        try:
            allow_paths = self._build_allow_paths()
            logger.info("WFP allow-list: %s", allow_paths)
            print(f"[wfp_native] Allow list: {allow_paths}")
            if not allow_paths:
                raise FirewallConfigurationError(
                    "No executable paths to whitelist; refusing to lock down network"
                )
            self._session = wfp_native.WfpExamSession(allow_app_paths=allow_paths)
            self._session.install()
        except Exception as exc:
            tb = _tb.format_exc()
            self.last_error = f"{type(exc).__name__}: {exc}"
            # Surface to the operator console regardless of logging config.
            print("[wfp_native] activation FAILED:", self.last_error, file=sys.stderr)
            print(tb, file=sys.stderr)
            logger.error("wfp_native activation failed: %s\n%s", self.last_error, tb)
            try:
                if self._session:
                    self._session.uninstall()
            except Exception:
                pass
            try:
                wfp_native.recover_stale()
            except Exception:
                pass
            self._session = None
            self._state = FirewallState.INACTIVE
            return False
        self._state = FirewallState.ACTIVE
        logger.info("=== EXAM MODE ACTIVE (wfp_native backend) ===")
        return True

    def exit_exam_mode(self) -> bool:
        if self._state == FirewallState.INACTIVE:
            return True
        logger.info("=== EXITING EXAM MODE (wfp_native backend) ===")
        self._state = FirewallState.ROLLBACK
        ok = True
        try:
            if self._session:
                self._session.uninstall()
        except Exception as exc:
            logger.error("wfp_native uninstall failed, will recover_stale: %s", exc)
            ok = False
        try:
            wfp_native.recover_stale()
        except Exception:
            pass
        self._session = None
        self._state = FirewallState.INACTIVE
        logger.info("=== EXAM MODE EXITED (wfp_native backend) ===")
        return ok


class NativeFirewallController:
    """Facade that picks the strongest available backend.

    Backend selection order (override via OMNIPROCTOR_FIREWALL_BACKEND):
        wfp_native -> wfp -> netsh

    ``wfp_native`` is preferred because it is the only backend that can
    actually block other applications' traffic when those applications
    have pre-existing Windows Firewall allow rules.
    """

    def __init__(self, browser_executable_path: str):
        self.browser_exe = browser_executable_path
        self._backend = self._build_backend(browser_executable_path)

    def _build_backend(self, browser_executable_path: str) -> FirewallControllerBase:
        preferred = os.getenv(FIREWALL_BACKEND_ENV, "wfp_native").strip().lower()
        allow_netsh_fallback = os.getenv(ALLOW_NETSH_FALLBACK_ENV, "1").strip() not in {"0", "false", "False"}

        if preferred not in {"wfp_native", "wfp", "netsh"}:
            raise FirewallConfigurationError(
                f"Unsupported backend '{preferred}'. Use 'wfp_native', 'wfp', or 'netsh'."
            )

        if preferred == "netsh":
            logger.info("Using netsh backend (explicit)")
            return NetshFirewallController(browser_executable_path)

        if preferred == "wfp":
            logger.info("Using NetSecurity WFP backend (explicit)")
            return WfpFirewallController(browser_executable_path)

        try:
            logger.info("Using wfp_native backend (default, app-level blocking)")
            return WfpNativeFirewallController(browser_executable_path)
        except Exception as exc:
            logger.warning("wfp_native backend unavailable, trying NetSecurity WFP: %s", exc)
            try:
                return WfpFirewallController(browser_executable_path)
            except Exception as exc2:
                if not allow_netsh_fallback:
                    raise
                logger.warning("NetSecurity WFP also unavailable, falling back to netsh: %s", exc2)
                return NetshFirewallController(browser_executable_path)

    def enter_exam_mode(self) -> bool:
        return self._backend.enter_exam_mode()

    def exit_exam_mode(self) -> bool:
        return self._backend.exit_exam_mode()

    @property
    def is_active(self) -> bool:
        return self._backend.is_active

    @property
    def state(self) -> FirewallState:
        return self._backend.state


def emergency_firewall_cleanup() -> None:
    """Best-effort cleanup for crash/atexit paths.

    Wipes any wfp_native filters tagged with our provider GUID and falls back
    to a conservative profile unlock + NetSecurity-rule cleanup. Safe to call
    when nothing is installed.
    """
    if wfp_native is not None:
        try:
            removed = wfp_native.recover_stale()
            if removed:
                logger.warning(
                    "Emergency cleanup removed %d orphaned wfp_native filters", removed
                )
        except Exception as exc:
            logger.error("wfp_native recover_stale failed during emergency cleanup: %s", exc)

    no_window = _create_no_window_flag()
    for profile in ("domainprofile", "privateprofile", "publicprofile"):
        try:
            subprocess.run(
                ["netsh", "advfirewall", "set", profile, "firewallpolicy", "blockinbound,allowoutbound"],
                capture_output=True,
                timeout=10,
                creationflags=no_window,
            )
        except Exception:
            pass
    for rule_name in FIREWALL_RULE_NAMES:
        try:
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
                capture_output=True,
                timeout=10,
                creationflags=no_window,
            )
        except Exception:
            pass

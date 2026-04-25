import atexit
import ctypes
from ctypes import wintypes
import keyboard
import signal
import winreg

# ---------------------------------------------------------------------------
# Win32 broadcast helper: tell Explorer + every top-level window that we
# changed a registry value so the live UI reloads instead of waiting for a
# logoff. Without this, ``ShowTaskViewButton`` and ``AllowEdgeSwipe`` look
# like they "didn't restore" because Explorer caches the policy in-process.
# ---------------------------------------------------------------------------
HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002


def _broadcast_setting_change(area: str = "Policy") -> None:
    """Best-effort SendMessageTimeout(WM_SETTINGCHANGE) so Explorer reloads.

    Explorer caches several registry-backed values per-area and only
    reloads when it sees a matching ``WM_SETTINGCHANGE`` broadcast. We
    fire a small set of well-known area names so a single restore call
    refreshes the taskbar (TraySettings), policies (Policy), explorer
    shell (Environment), and ``ImmersiveColorSet`` for good measure.
    """
    try:
        user32 = ctypes.windll.user32
        result = wintypes.DWORD(0)
        labels = {area, "Policy", "TraySettings", "Environment", "ImmersiveColorSet"}
        for label in labels:
            user32.SendMessageTimeoutW(
                HWND_BROADCAST,
                WM_SETTINGCHANGE,
                0,
                ctypes.c_wchar_p(label),
                SMTO_ABORTIFHUNG,
                200,
                ctypes.byref(result),
            )
    except Exception as exc:
        print(f"  WM_SETTINGCHANGE broadcast failed: {exc}")


def _refresh_explorer_taskbar() -> None:
    """Force Explorer to re-read its per-user shell settings.

    Used as a belt-and-braces companion to ``WM_SETTINGCHANGE`` for the
    Task View button: SHChangeNotify with SHCNE_ASSOCCHANGED makes
    Explorer drop its cached shell-config snapshot.
    """
    SHCNE_ASSOCCHANGED = 0x08000000
    SHCNF_IDLIST = 0x0000
    try:
        ctypes.windll.shell32.SHChangeNotify(
            SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None
        )
    except Exception as exc:
        print(f"  SHChangeNotify failed: {exc}")


class KioskModeKeyBlocker:
    def __init__(self):
        self.blocked = False
        self.browser_window = None
        self.running = False
        self.active_hotkeys = []
        self._gestures_suppressed = False
        self.system_lockdown = True

    def setup_keyboard_hooks(self):
        if not self.blocked:
            return

        try:
            self.remove_keyboard_hooks()

            for i in range(1, 13):  # F1-F12
                hotkey_ref = keyboard.add_hotkey(
                    f'f{i}', lambda: None, suppress=True)
                if hotkey_ref:
                    self.active_hotkeys.append(hotkey_ref)
                    print(f"BLOCKED: F{i}")

            key_combinations = [
                # System navigation and window management
                ('block_alt_tab', 'alt+tab', 'Alt+Tab (Switch Windows)'),
                ('block_alt_esc', 'alt+esc', 'Alt+Esc (Cycle Windows)'),
                ('block_alt_f4', 'alt+f4', 'Alt+F4 (Close Window)'),
                ('block_ctrl_shift_esc', 'ctrl+shift+esc',
                 'Ctrl+Shift+Esc (Task Manager)'),
                ('block_ctrl_esc', 'ctrl+esc', 'Ctrl+Esc (Start Menu)'),
                ('block_ctrl_alt_t', 'ctrl+alt+t',
                 'Ctrl+Alt+T (Task Manager Alt)'),
                ('block_shift_f10', 'shift+f10', 'Shift+F10 (Context Menu)'),
                ('block_alt_enter', 'alt+enter', 'Alt+Enter (Properties)'),
                ('block_ctrl_alt_tab', 'ctrl+alt+tab', 'Ctrl+Alt+Tab'),

                # Browser tab and window management
                ('block_ctrl_n', 'ctrl+n', 'Ctrl+N (New Window)'),
                ('block_ctrl_t', 'ctrl+t', 'Ctrl+T (New Tab)'),
                ('block_ctrl_w', 'ctrl+w', 'Ctrl+W (Close Tab)'),
                ('block_ctrl_shift_t', 'ctrl+shift+t',
                 'Ctrl+Shift+T (Restore Tab)'),
                ('block_ctrl_shift_n', 'ctrl+shift+n', 'Ctrl+Shift+N (Incognito)'),

                # Browser navigation
                ('block_ctrl_r', 'ctrl+r', 'Ctrl+R (Refresh)'),
                ('block_ctrl_f5', 'ctrl+f5', 'Ctrl+F5 (Hard Refresh)'),
                ('block_ctrl_shift_r', 'ctrl+shift+r',
                 'Ctrl+Shift+R (Hard Refresh)'),
                ('block_ctrl_l', 'ctrl+l', 'Ctrl+L (Location Bar)'),
                ('block_ctrl_k', 'ctrl+k', 'Ctrl+K (Search Bar)'),
                ('block_ctrl_e', 'ctrl+e', 'Ctrl+E (Search Bar)'),
                ('block_alt_d', 'alt+d', 'Alt+D (Address Bar)'),
                ('block_alt_home', 'alt+home', 'Alt+Home (Home Page)'),
                ('block_alt_left', 'alt+left', 'Alt+Left (Back)'),
                ('block_alt_right', 'alt+right', 'Alt+Right (Forward)'),

                # Browser tools and developer features
                ('block_ctrl_h', 'ctrl+h', 'Ctrl+H (History)'),
                ('block_ctrl_j', 'ctrl+j', 'Ctrl+J (Downloads)'),
                ('block_ctrl_d', 'ctrl+d', 'Ctrl+D (Bookmark)'),
                ('block_ctrl_u', 'ctrl+u', 'Ctrl+U (View Source)'),
                ('block_ctrl_shift_i', 'ctrl+shift+i', 'Ctrl+Shift+I (DevTools)'),
                ('block_ctrl_shift_j', 'ctrl+shift+j', 'Ctrl+Shift+J (Console)'),
                ('block_ctrl_shift_c', 'ctrl+shift+c', 'Ctrl+Shift+C (Inspect)'),
                ('block_ctrl_shift_del', 'ctrl+shift+del',
                 'Ctrl+Shift+Del (Clear Data)'),
                ('block_ctrl_shift_o', 'ctrl+shift+o', 'Ctrl+Shift+O (Bookmarks)'),
                ('block_ctrl_shift_b', 'ctrl+shift+b',
                 'Ctrl+Shift+B (Bookmark Bar)'),

                # File operations and search
                ('block_ctrl_o', 'ctrl+o', 'Ctrl+O (Open File)'),
                ('block_ctrl_s', 'ctrl+s', 'Ctrl+S (Save)'),
                ('block_ctrl_p', 'ctrl+p', 'Ctrl+P (Print)'),
                ('block_ctrl_f', 'ctrl+f', 'Ctrl+F (Find)'),
                ('block_ctrl_g', 'ctrl+g', 'Ctrl+G (Find Next)'),
                ('block_ctrl_shift_g', 'ctrl+shift+g',
                 'Ctrl+Shift+G (Find Previous)'),
                ('block_escape', 'esc', 'Escape'),
                ('block_printscreen', 'print screen', 'Print Screen'),
                ('block_win_l', 'win+l', 'Win+L (Lock Screen)'),
                ('block_win_d', 'win+d', 'Win+D (Show Desktop)'),
                ('block_win_m', 'win+m', 'Win+M (Minimize All)'),
                ('block_win_r', 'win+r', 'Win+R (Run Dialog)'),
                ('block_win_x', 'win+x', 'Win+X (Power User Menu)'),
                ('block_win_i', 'win+i', 'Win+I (Settings)'),
                ('block_win_u', 'win+u', 'Win+U (Ease of Access)'),
                ('block_win_shift_s', 'win+shift+s', 'Win+Shift+S(Screen Snip)'),
                ('block_alt_space', 'alt+space', 'Alt+Space (Window Menu)'),
            ]

            for _, hotkey_combo, description in key_combinations:
                try:
                    hotkey_ref = keyboard.add_hotkey(
                        hotkey_combo, lambda: None, suppress=True)
                    if hotkey_ref:
                        self.active_hotkeys.append(hotkey_ref)
                        print(f"BLOCKED: {description}")
                except Exception as e:
                    print(f"Failed to block {description}: {e}")

            print(
                f"Successfully registered {len(self.active_hotkeys)} hotkey blocks using keyboard.add_hotkey()")

        except Exception as e:
            print(f"Error setting up keyboard hooks: {e}")

    def remove_keyboard_hooks(self):
        try:
            removed_count = 0
            for hotkey_ref in self.active_hotkeys:
                try:
                    keyboard.remove_hotkey(hotkey_ref)
                    removed_count += 1
                except Exception as e:
                    print(f"Failed to remove hotkey {hotkey_ref}: {e}")

            self.active_hotkeys.clear()

            if removed_count > 0:
                print(f"Removed {removed_count} keyboard hotkey blocks")
            else:
                print("No keyboard hotkeys to remove")

        except Exception as e:
            print(f"Error removing keyboard hooks: {e}")
            try:
                keyboard.unhook_all()
                self.active_hotkeys.clear()
                print("Fallback: Cleared all keyboard hooks")
            except Exception as e2:
                print(f"Fallback cleanup also failed: {e2}")

    def start_keyboard_listener(self):
        try:
            self.setup_keyboard_hooks()
            print("Keyboard listener started with hotkey suppression.")
            return True
        except Exception as e:
            print(f"Error starting keyboard listener: {e}")
            return False

    def stop_keyboard_listener(self):
        try:
            self.remove_keyboard_hooks()
            print("Keyboard listener stopped.")
        except Exception as e:
            print(f"Error stopping keyboard listener: {e}")

    def set_target_window(self, hwnd):
        self.browser_window = hwnd

    def disable_task_manager(self):
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
            try:
                key = winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "DisableTaskMgr",
                                  0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
                print("Task Manager disabled via registry (current user only)")
                return True
            except PermissionError:
                return False
        except Exception as e:
            print(f"Could not disable Task Manager: {e}")
            return False

    def enable_task_manager(self):
        """Remove the ``DisableTaskMgr`` policy from BOTH HKCU and HKLM.

        Always attempted, even if we never set it ourselves, so an orphan
        from a prior crashed run is also cleaned. Broadcasts a policy
        refresh so Explorer drops its cached version of the policy
        immediately - without the broadcast Task Manager appears to
        "remain disabled" until logoff.
        """
        cleared_anywhere = False
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"

        for hive, hive_label in (
            (winreg.HKEY_CURRENT_USER, "HKCU"),
            (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
        ):
            try:
                key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE)
                try:
                    winreg.DeleteValue(key, "DisableTaskMgr")
                    cleared_anywhere = True
                    print(f"Task Manager re-enabled via registry ({hive_label})")
                except FileNotFoundError:
                    pass
                finally:
                    winreg.CloseKey(key)
            except FileNotFoundError:
                pass
            except PermissionError:
                # HKLM requires admin. Don't fail the whole cleanup just
                # because the per-user value was the only one we set.
                pass
            except Exception as exc:
                print(f"  enable_task_manager {hive_label} error: {exc}")

        try:
            _broadcast_setting_change("Policy")
        except Exception:
            pass

        if not cleared_anywhere:
            print("DisableTaskMgr registry value was not set anywhere")
        return True

    # ------------------------------------------------------------------
    # Gesture & trackpad suppression via winreg
    # ------------------------------------------------------------------
    def suppress_gestures(self) -> bool:
        """Disable Windows 10/11 edge swipes and Task View button via registry."""
        try:
            self._set_edge_swipe_policy(disabled=True)
            self._set_task_view_button(disabled=True)
            self._gestures_suppressed = True
            print("Gestures and trackpad swipes suppressed via registry")
            return True
        except Exception as e:
            print(f"Error suppressing gestures: {e}")
            return False

    def restore_gestures(self) -> bool:
        """Re-enable edge swipes and Task View button.

        ALWAYS attempts the rollback (no early-out on ``_gestures_suppressed``)
        so an orphaned policy from a previously-crashed session also gets
        cleaned. After writing the registry, broadcasts ``WM_SETTINGCHANGE``
        so Explorer / DWM reload the value without requiring a logoff -
        without this broadcast the Task View button and edge-swipe
        policy stay frozen in their disabled state until the next login.
        """
        ok = True
        try:
            self._set_edge_swipe_policy(disabled=False)
        except Exception as exc:
            print(f"  edge swipe restore error: {exc}")
            ok = False
        try:
            self._set_task_view_button(disabled=False)
        except Exception as exc:
            print(f"  task view button restore error: {exc}")
            ok = False
        try:
            _broadcast_setting_change("TraySettings")
            _refresh_explorer_taskbar()
            print("  Broadcast WM_SETTINGCHANGE + SHChangeNotify to refresh Explorer")
        except Exception:
            pass
        self._gestures_suppressed = False
        if ok:
            print("Gestures and trackpad swipes restored via registry")
        else:
            print("Gestures restore completed with one or more best-effort errors")
        return ok

    @staticmethod
    def _set_edge_swipe_policy(disabled: bool) -> None:
        """Control edge swipe gestures (Action Center / Notifications).
        This is a Group Policy that only takes effect under HKLM, so it
        requires admin and is best-effort. Skipped silently otherwise.
        """
        key_path = r"SOFTWARE\Policies\Microsoft\Windows\EdgeUI"
        try:
            if disabled:
                key = winreg.CreateKeyEx(
                    winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                    winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
                winreg.SetValueEx(key, "AllowEdgeSwipe", 0, winreg.REG_DWORD, 0)
                winreg.CloseKey(key)
                print("  Edge swipe gestures disabled")
            else:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                    winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
                try:
                    winreg.DeleteValue(key, "AllowEdgeSwipe")
                except FileNotFoundError:
                    pass
                winreg.CloseKey(key)
                print("  Edge swipe gestures re-enabled")
        except PermissionError:
            print("  Edge swipe policy: needs admin (HKLM-only); skipped")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"  Edge swipe policy error: {e}")

    @staticmethod
    def _set_task_view_button(disabled: bool) -> None:
        """Control Task View button (Win+Tab trigger area on taskbar).
        Per-user setting under HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced.
        """
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
        try:
            key = winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            value = 0 if disabled else 1
            winreg.SetValueEx(key, "ShowTaskViewButton", 0, winreg.REG_DWORD, value)
            winreg.CloseKey(key)
            state = "hidden" if disabled else "visible"
            print(f"  Task View button set to {state} (current user)")
        except PermissionError:
            print("  Task View button: permission denied")
        except Exception as e:
            print(f"  Task View button error: {e}")

    # ------------------------------------------------------------------

    def start_kiosk_mode(self, target_window_hwnd=None, system_lockdown: bool = True):
        if self.blocked:
            return False

        self.blocked = True
        self.system_lockdown = system_lockdown

        if not self.start_keyboard_listener():
            print("Failed to start keyboard listener")
            self.blocked = False
            return False

        self.running = True
        if system_lockdown:
            self.disable_task_manager()
            self.suppress_gestures()
        else:
            print(
                "System lockdown disabled (dev mode): Task Manager, Task View "
                "button and edge-swipe policy will NOT be modified"
            )

        self.browser_window = target_window_hwnd

        return True

    def stop_kiosk_mode(self):
        """Tear down kiosk mode and ALWAYS roll back system-level changes.

        Idempotent and safe to call from atexit, signal handlers and the
        main shutdown path. Returns True if any cleanup ran.

        Note: the previous implementation early-returned when
        ``self.blocked`` was False, which meant a crash that happened
        between ``disable_task_manager()`` and ``self.blocked = True``
        in ``start_kiosk_mode`` left the registry policy on but skipped
        cleanup on the way out. We now always run the unwind.
        """
        was_active = self.blocked or self._gestures_suppressed
        if was_active:
            print("Stopping kiosk mode...")

        self.running = False
        self.blocked = False

        try:
            self.stop_keyboard_listener()
        except Exception as exc:
            print(f"  stop_keyboard_listener error: {exc}")

        # ALWAYS run these - they are no-ops if the registry value is
        # already absent. This is what catches orphaned registry state
        # from a previously crashed kiosk session.
        try:
            self.enable_task_manager()
        except Exception as exc:
            print(f"  enable_task_manager error: {exc}")
        try:
            self.restore_gestures()
        except Exception as exc:
            print(f"  restore_gestures error: {exc}")

        if was_active:
            print("Kiosk mode deactivated - Normal operation restored")
        return True

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False


kiosk_blocker = KioskModeKeyBlocker()


def start_exam_kiosk_mode(target_window_hwnd=None, system_lockdown: bool = True):
    if not kiosk_blocker.is_admin():
        print("Not Admin")

    return kiosk_blocker.start_kiosk_mode(
        target_window_hwnd, system_lockdown=system_lockdown
    )


def stop_exam_kiosk_mode():
    return kiosk_blocker.stop_kiosk_mode()


def set_target_browser_window(hwnd):
    kiosk_blocker.set_target_window(hwnd)


# ---------------------------------------------------------------------------
# Emergency cleanup: ensures Task Manager / gestures get restored even if
# the process is killed externally or crashes before SecureBrowser.safe_exit
# can run. Must be installed from the main thread (signal.signal restriction).
# ---------------------------------------------------------------------------
_emergency_handlers_installed = False


def _emergency_cleanup(*_args, **_kwargs):
    try:
        kiosk_blocker.stop_kiosk_mode()
    except Exception as exc:
        print(f"emergency keyblock cleanup failed: {exc}")


def install_emergency_handlers() -> None:
    """Register atexit + SIGINT/SIGTERM/SIGBREAK to roll back kiosk policies.

    Idempotent. Safe to call multiple times. Must be invoked from the main
    thread (Python's `signal.signal` raises ValueError otherwise).
    """
    global _emergency_handlers_installed
    if _emergency_handlers_installed:
        return

    atexit.register(_emergency_cleanup)

    for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _emergency_cleanup)
        except (OSError, ValueError):
            # Some signals can't be installed in non-main threads on Windows.
            pass

    _emergency_handlers_installed = True


if __name__ == "__main__":
    print("Testing keyboard library-based Kiosk Mode Key Blocker")
    print("Press Ctrl+C to stop")

    try:
        if start_exam_kiosk_mode():
            print("Kiosk mode started. Try pressing blocked keys...")
            keyboard.wait('ctrl+shift+q')
    except KeyboardInterrupt:
        print("\nStopping kiosk mode...")
    finally:
        stop_exam_kiosk_mode()

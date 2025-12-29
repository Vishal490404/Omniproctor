import ctypes
import keyboard
import winreg


class KioskModeKeyBlocker:
    def __init__(self):
        self.blocked = False
        self.browser_window = None
        self.running = False
        self.active_hotkeys = []

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
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
            try:
                key = winreg.CreateKeyEx(
                    winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "DisableTaskMgr",
                                  0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
                print("Task Manager disabled via registry (system-wide)")
                return True
            except PermissionError:
                return False
        except Exception as e:
            print(f"Could not disable Task Manager: {e}")
            return False

    def enable_task_manager(self):
        success = False
        try:

            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"

            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
                try:
                    winreg.DeleteValue(key, "DisableTaskMgr")
                    print("Task Manager re-enabled via registry (system-wide)")
                    success = True
                except FileNotFoundError:
                    pass
                winreg.CloseKey(key)
            except (PermissionError, FileNotFoundError):
                pass

            if not success:
                print("DisableTaskMgr registry value was not set")
            return True
        except Exception as e:
            print(f"Could not re-enable Task Manager: {e}")
            return False

    def start_kiosk_mode(self, target_window_hwnd=None):
        if self.blocked:
            return False

        self.blocked = True

        if not self.start_keyboard_listener():
            print("Failed to start keyboard listener")
            self.blocked = False
            return False

        self.running = True
        self.disable_task_manager()

        self.browser_window = target_window_hwnd

        return True

    def stop_kiosk_mode(self):
        if not self.blocked:
            return False
        print("Stopping kiosk mode...")

        self.running = False
        self.blocked = False

        self.stop_keyboard_listener()

        self.enable_task_manager()

        print("Kiosk mode deactivated - Normal operation restored")
        return True

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False


kiosk_blocker = KioskModeKeyBlocker()


def start_exam_kiosk_mode(target_window_hwnd=None):
    if not kiosk_blocker.is_admin():
        print("Not Admin")

    return kiosk_blocker.start_kiosk_mode(target_window_hwnd)


def stop_exam_kiosk_mode():
    return kiosk_blocker.stop_kiosk_mode()


def set_target_browser_window(hwnd):
    kiosk_blocker.set_target_window(hwnd)


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

import os
import sys
import json
import shutil
import logging
import subprocess
import tempfile
import time
import threading
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import ctypes
import pyuac
import xml.etree.ElementTree as ET
from xml.dom import minidom


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simplewall_controller.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class SimpleWallConfig:
    """Configuration class for SimpleWall settings."""
    config_backup_path: str = ""
    browser_executable: str = "C:\\Users\\desai\\AppData\\Roaming\\uv\\python\\cpython-3.10.19-windows-x86_64-none\\python.exe"
    simplewall_path: str = ""
    service_name: str = "simplewall"  
    config_file_path: str = ""
    installer_path: str = "simplewall-3.8.7-setup.exe"  


class AdminRightsError(Exception):
    """Raised when admin rights are required but not available."""
    pass


class SimpleWallError(Exception):
    """Base exception for SimpleWall operations."""
    pass


class SimpleWallConfigManager:
    
    @classmethod
    def load_config(cls, config_path: str) -> Optional[ET.Element]:
        try:
            if not os.path.exists(config_path):
                logger.warning(f"Config file not found: {config_path}")
                return None
            
            tree = ET.parse(config_path)
            root = tree.getroot()
            logger.info(f"SimpleWall config loaded from {config_path}")
            return root
            
        except Exception as e:
            logger.error(f"Error loading SimpleWall config: {e}")
            return None
    
    @classmethod
    def save_config(cls, root: ET.Element, config_path: str) -> bool:
        try:
            rough_string = ET.tostring(root, encoding='utf-8')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="\t", encoding='UTF-8')
            
            with open(config_path, 'wb') as f:
                f.write(pretty_xml)
            
            logger.info(f"SimpleWall config saved to {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving SimpleWall config: {e}")
            return False
    
    @classmethod
    def disable_non_undeletable_apps(cls, root: ET.Element) -> int:
        
        disabled_count = 0
        apps = root.find('apps')
        
        if apps is None:
            logger.warning("No apps section found in config")
            return 0
        
        for item in apps.findall('item'):
            is_undeletable = item.get('is_undeletable') == 'true'
            is_enabled = item.get('is_enabled') == 'true'
            path = item.get('path', 'Unknown')
            
            if is_enabled and not is_undeletable:
                item.set('is_enabled', 'false')
                disabled_count += 1
                logger.info(f"Disabled: {path}")
        
        return disabled_count
    
    @classmethod
    def add_browser_to_whitelist(cls, root: ET.Element, browser_path: str) -> bool:
        try:
            apps = root.find('apps')
            if apps is None:
                logger.error("No apps section found in config")
                return False
            
            normalized_browser_path = browser_path.lower()
            
            browser_exists = False
            for item in apps.findall('item'):
                item_path = item.get('path', '').lower()
                if item_path == normalized_browser_path:
                    item.set('is_enabled', 'true')
                    item.set('timestamp', str(int(time.time())))
                    logger.info(f"Updated existing browser entry: {browser_path}")
                    browser_exists = True
                    break
            
            if not browser_exists:
                new_item = ET.SubElement(apps, 'item')
                new_item.set('path', browser_path)
                new_item.set('timestamp', str(int(time.time())))
                new_item.set('is_enabled', 'true')
                logger.info(f"Added new browser entry: {browser_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding browser to whitelist: {e}")
            return False


class SimpleWallController:

    def __init__(self, browser_executable_path: str = ""):
        self.config = SimpleWallConfig()
        self.config.browser_executable = browser_executable_path or self.config.browser_executable
        self._initialize_paths()
        self._check_admin_rights()

    def _initialize_paths(self) -> None:
        possible_paths = [
            r'C:\Program Files\simplewall\simplewall.exe'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.config.simplewall_path = path
                break
        
        appdata = r'C:\Program Files\simplewall'
        self.config.config_file_path = os.path.join(appdata, 'profile.xml')
        
        logger.info(f"SimpleWall executable: {self.config.simplewall_path}")
        logger.info(f"Config file path: {self.config.config_file_path}")

    def _check_admin_rights(self) -> None:
        """Check if running with administrator privileges"""
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                logger.error("Administrator privileges required for SimpleWall operations")
                raise AdminRightsError("This application requires administrator privileges to manage SimpleWall")
            else:
                logger.info("Administrator privileges verified")
        except Exception as e:
            logger.error(f"Failed to check admin rights: {e}")
            raise AdminRightsError("Unable to verify administrator privileges")

    def _auto_click_dialog_button(self, window_title: str, button_text: str, timeout: int = 10) -> None:
        """Background thread to automatically click a dialog button"""
        try:
            user32 = ctypes.windll.user32
            
            start_time = time.time()
            while time.time() - start_time < timeout:
                # Find window by title (partial match)
                hwnd = user32.FindWindowW(None, window_title)
                
                if hwnd:
                    logger.info(f"Found dialog window: {window_title}")
                    button_hwnd = user32.FindWindowExW(hwnd, None, "Button", button_text)
                    
                    if button_hwnd:
                        logger.info(f"Found button '{button_text}', clicking it")
                        BM_CLICK = 0x00F5
                        user32.SendMessageW(button_hwnd, BM_CLICK, 0, 0)
                        return
                    else:
                        WM_COMMAND = 0x0111
                        for button_id in [1, 6, 2]:
                            user32.PostMessageW(hwnd, WM_COMMAND, button_id, 0)
                            logger.info(f"Sent click command to dialog (button ID: {button_id})")
                            time.sleep(0.5)
                            if not user32.IsWindow(hwnd):
                                logger.info("Dialog closed successfully")
                                return
                
                time.sleep(0.5)
            
            logger.warning(f"Dialog '{window_title}' not found within timeout")
            
        except Exception as e:
            logger.error(f"Error auto-clicking dialog: {e}")

    def _is_simplewall_running(self) -> bool:
        """Check if SimpleWall service/process is running"""
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq simplewall.exe'],
                capture_output=True,
                text=True,
                check=False
            )
            print(result)
            return 'simplewall.exe' in result.stdout
        except Exception:
            return False

    def check_simplewall_installed(self) -> bool:
        try:
            if self.config.simplewall_path and os.path.exists(self.config.simplewall_path):
                logger.info("SimpleWall executable found")
                return True
            else:
                logger.warning("SimpleWall executable not found")
                return False
            
        except Exception as e:
            logger.error(f"Error checking SimpleWall installation: {e}")
            return False

    def install_simplewall_silent(self) -> bool:
        """Install SimpleWall silently"""
        try:
            installer_path = os.path.join(os.path.dirname(__file__), self.config.installer_path)
            
            if not os.path.exists(installer_path):
                logger.error(f"SimpleWall installer not found: {installer_path}")
                return False
            
            logger.info(f"Installing SimpleWall from: {installer_path}")
            
            cmd = [installer_path, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("SimpleWall installed successfully")
                self._initialize_paths()
                
                if self.check_simplewall_installed():
                    logger.info("SimpleWall installation verified")
                    return True
                else:
                    logger.error("SimpleWall installation verification failed")
                    return False
            else:
                logger.error(f"SimpleWall installation failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("SimpleWall installation timed out")
            return False
        except Exception as e:
            logger.error(f"Error during SimpleWall installation: {e}")
            return False

    def ensure_simplewall_installed(self) -> bool:
        try:
            logger.info("Checking if SimpleWall is installed...")
            
            if self.check_simplewall_installed():
                logger.info("SimpleWall is already installed")
                return True
            
            logger.info("SimpleWall not found, attempting installation...")
            
            if self.install_simplewall_silent():
                logger.info("SimpleWall installed successfully")
                return True
            else:
                logger.error("Failed to install SimpleWall")
                return False
                
        except Exception as e:
            logger.error(f"Error ensuring SimpleWall installation: {e}")
            return False

    def start_simplewall_service(self) -> bool:
        try:
            if self._is_simplewall_running():
                logger.info("SimpleWall is already running")
                return True
            
            if not self.config.simplewall_path:
                logger.error("SimpleWall executable path not set")
                return False
            
            result = subprocess.run(
                [self.config.simplewall_path, '-install', '-silent'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 575:
            
                logger.info("It has started")
                return True
            start = time.time()
            while time.time() - start < 5:
                if self._is_simplewall_running():
                    logger.info("SimpleWall started successfully with filtering enabled")
                    return True
                time.sleep(0.5)
            
            logger.error("Failed to start SimpleWall")
            return False
                
        except subprocess.TimeoutExpired:
            logger.error("SimpleWall start command timed out")
            return False
        except Exception as e:
            logger.error(f"Error starting SimpleWall: {e}")
            return False

    def backup_simplewall_config(self) -> bool:
        """Backup SimpleWall configuration"""
        try:
            config_dir = os.path.dirname(self.config.config_file_path)
            backup_dir = Path(f"{config_dir}.exam_backup")
            metadata_file = Path(tempfile.gettempdir()) / 'simplewall_backup_metadata.json'
            
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            if os.path.exists(config_dir):
                logger.info(f"Backing up SimpleWall config directory: {config_dir}")
                
                if backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)
                    backup_dir.mkdir(parents=True, exist_ok=True)
                
                shutil.copytree(config_dir, backup_dir, dirs_exist_ok=True)
                logger.info(f"SimpleWall config directory backed up to: {backup_dir}")
            else:
                logger.warning("SimpleWall config directory not found, creating backup placeholder")
            
            metadata = {
                "running": self._is_simplewall_running(),
                "timestamp": datetime.now().isoformat(),
                "config_dir": str(config_dir),
                "backup_dir": str(backup_dir)
            }
            
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"SimpleWall running state saved: {metadata['running']}")
            return True
            
        except Exception as e:
            logger.error(f"Error backing up SimpleWall config: {e}")
            return False

    def whitelist_browser_in_simplewall(self) -> bool:
        try:
            logger.info("=" * 60)
            logger.info("Starting browser whitelisting process")
            logger.info(f"Browser executable: {self.config.browser_executable}")
            logger.info(f"Config file: {self.config.config_file_path}")
            logger.info("=" * 60)
            
            if not os.path.exists(self.config.config_file_path):
                logger.error(f"Config file not found: {self.config.config_file_path}")
                return False
            
            root = SimpleWallConfigManager.load_config(self.config.config_file_path)
            if root is None:
                logger.error("Failed to load SimpleWall configuration")
                return False
            
            logger.info("Step 1: Disabling non-undeletable enabled applications...")
            disabled_count = SimpleWallConfigManager.disable_non_undeletable_apps(root)
            logger.info(f"Disabled {disabled_count} applications")
            
            logger.info("Step 2: Adding browser to whitelist...")
            if not SimpleWallConfigManager.add_browser_to_whitelist(root, self.config.browser_executable):
                logger.error("Failed to add browser to whitelist")
                return False
            
            logger.info("Step 3: Saving modified configuration...")
            if not SimpleWallConfigManager.save_config(root, self.config.config_file_path):
                logger.error("Failed to save SimpleWall configuration")
                return False
            
            
            return True
            
        except Exception as e:
            logger.error(f"Error whitelisting browser in SimpleWall: {e}", exc_info=True)
            return False

    def _kill_simplewall_processes(self) -> bool:
        try:
            logger.info("Forcibly terminating all SimpleWall processes")
            process_names = ['simplewall.exe']
            
            killed_any = False
            for process_name in process_names:
                result = subprocess.run(['taskkill', '/F', '/IM', process_name], 
                                     capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    logger.info(f"Terminated {process_name}")
                    killed_any = True
            
            if killed_any:
                logger.info("SimpleWall processes terminated")
            else:
                logger.info("No SimpleWall processes found to terminate")
                
            return True
            
        except Exception as e:
            logger.warning(f"Error terminating SimpleWall processes: {e}")
            return False

    def stop_simplewall_service(self) -> bool:
        try:
            logger.info("Stopping SimpleWall service")
            
            if not self._is_simplewall_running():
                logger.info("SimpleWall is not running")
                return True
            
            if not self.config.simplewall_path:
                logger.error("SimpleWall executable path not set")
                return False
            
            try:
                logger.info("Starting background thread to handle dialog popup")
                dialog_thread = threading.Thread(
                    target=self._auto_click_dialog_button,
                    args=("simplewall", "Close", 15),
                    daemon=True
                )
                dialog_thread.start()
                
                time.sleep(0.5)
                
                logger.info("Executing SimpleWall uninstall command...")
                result = subprocess.run(
                    [self.config.simplewall_path, '-uninstall'],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False
                )
                
                dialog_thread.join(timeout=5)
                
                # time.sleep(2)
                
                if not self._is_simplewall_running():
                    logger.info("SimpleWall stopped successfully")
                    return True
                else:
                    logger.warning("SimpleWall still running after uninstall, forcing termination")
                    self._kill_simplewall_processes()
                    return True
                
            except subprocess.TimeoutExpired:
                logger.error("SimpleWall uninstall command timed out, forcing termination")
                self._kill_simplewall_processes()
                return True
            except Exception as e:
                logger.warning(f"Error during SimpleWall uninstall: {e}")
                self._kill_simplewall_processes()
                return True
                
        except Exception as e:
            logger.error(f"Error stopping SimpleWall service: {e}")
            return False

    def restart_simplewall_service(self) -> bool:
        """Restart SimpleWall to apply configuration changes"""
        try:
            logger.info("Restarting SimpleWall to apply configuration changes")
            
            self._kill_simplewall_processes()
            # time.sleep(2)
            
            if self.start_simplewall_service():
                logger.info("SimpleWall restarted successfully")
                return True
            else:
                logger.error("Failed to restart SimpleWall")
                return False
                
        except Exception as e:
            logger.error(f"Error restarting SimpleWall: {e}")
            return False

    def enter_exam_mode(self) -> bool:
        try:
            logger.info("=== ENTERING EXAM MODE (SimpleWall) ===")
            
            if not self.ensure_simplewall_installed():
                logger.error("Failed to ensure SimpleWall installation")
                return False
            
            if not self.start_simplewall_service():
                logger.error("Failed to start SimpleWall")
                return False
            
            # if not self.backup_simplewall_config():
            #     logger.error("Failed to backup SimpleWall configuration")
            #     return False
            
            if not self.whitelist_browser_in_simplewall():
                logger.warning("Browser whitelisting may have failed, continuing...")
            
            if not self.restart_simplewall_service():
                logger.warning("Failed to restart SimpleWall, changes may not take effect")
            
            logger.info("=== EXAM MODE ACTIVE (SimpleWall) ===")
            return True
            
        except Exception as e:
            logger.error(f"Fatal error entering exam mode: {e}")
            return False

    def exit_exam_mode(self) -> bool:
        """Exit exam mode and restore previous SimpleWall state"""
        try:
            logger.info("=== EXITING EXAM MODE (SimpleWall) ===")
            
            self.stop_simplewall_service()
            
            logger.info("=== EXAM MODE EXITED (SimpleWall) ===")
            return True
            
        except Exception as e:
            logger.error(f"Error exiting exam mode: {e}")
            return False


def setup_browser_whitelist(browser_path: Optional[str] = None) -> bool:
    """Setup browser whitelist in SimpleWall"""
    try:
        logger.info("Setting up browser whitelist in SimpleWall...")
        
        controller = SimpleWallController(browser_path or "")
        
        if not controller.ensure_simplewall_installed():
            logger.error("Failed to ensure SimpleWall installation")
            return False
        
        if not controller.start_simplewall_service():
            logger.error("Failed to start SimpleWall")
            return False
        
        if not controller.whitelist_browser_in_simplewall():
            logger.error("Failed to whitelist browser")
            return False
        
        if not controller.restart_simplewall_service():
            logger.warning("Failed to restart SimpleWall after whitelisting")
        
        logger.info("Browser whitelist setup completed successfully")
        return True
        
    except AdminRightsError:
        logger.error("Administrator privileges required")
        return False
    except Exception as e:
        logger.error(f"Error setting up browser whitelist: {e}")
        return False


def main():
    """Main test function for SimpleWall controller"""
    try:
        print("SimpleWall Controller Test")
        print("=" * 40)
        print("Log file: simplewall_controller.log")
        print("Administrator privileges: ✓ Verified")
        
        controller = SimpleWallController(SimpleWallConfig.browser_executable)
        
        print("\n1. Testing exam mode entry...")
        if controller.enter_exam_mode():
            print("   ✓ Exam mode entered successfully")
            
            input("\n   Press Enter to exit exam mode...")
            
            print("\n2. Testing exam mode exit...")
            if controller.exit_exam_mode():
                print("   ✓ Exam mode exited successfully")
            else:
                print("   ✗ Failed to exit exam mode")
        else:
            print("   ✗ Failed to enter exam mode - check log for details")
        
        print(f"\nTest completed - See simplewall_controller.log for detailed information")
        
    except AdminRightsError:
        logger.error("Application terminated due to insufficient privileges")
        input("Press Enter to exit...")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Main function unexpected error: {e}", exc_info=True)
        input("Press Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    if not pyuac.isUserAdmin():
        pyuac.runAsAdmin()
    else:
        main()

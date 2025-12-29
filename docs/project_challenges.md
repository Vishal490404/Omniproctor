# Project Challenges

This section documents the technical and operational challenges faced during the development of Omniproctor, along with the solutions implemented to overcome them.

## Development Challenges

### 1. Preventing Screen Sharing and Remote Access

**The Problem:**
Preventing users from sharing their screen or using remote desktop tools during exams is a significant challenge. Existing proctoring platforms typically monitor background processes and flag known applications like Chrome, WhatsApp, or TeamViewer. However, this approach is fundamentally flawed and ineffective because:
- Users can easily rename executable files to bypass blacklist filters
- Advanced users can spawn processes using tools like [`PsExec`](https://learn.microsoft.com/en-us/sysinternals/downloads/psexec) to run applications as the SYSTEM user, making them harder to detect or terminate from a user-level application
- Simply killing other processes can be unstable and intrusive to the user's system

**The Solution:**
Instead of trying to play "whack-a-mole" with process names, we inverted the problem by controlling network access at the firewall level:
- Implemented an "allowlist" approach where only the Omniproctor browser executable is granted internet access
- All other applications and background processes are blocked from accessing the network during the exam
- This effectively cuts off screen sharing, remote desktop, and communication tools without needing to identify or terminate them individually

> **Note:** The current implementation of this solution is specific to the Windows operating system.

### 2. Cross-Process Communication Between Browser and Firewall

**The Problem:**
One of the core security features requires the browser application to dynamically control the Windows firewall (via SimpleWall) when entering and exiting exam mode. The challenge was to coordinate between the Python browser application and the external SimpleWall executable without blocking the UI or causing race conditions.

**The Solution:**
- Implemented a background worker thread (`NetworkWorker`) using `QThread` to handle firewall operations asynchronously
- Created a `SimpleWallController` class that manages SimpleWall process lifecycle
- Used signal-slot mechanism for thread-safe communication between worker and main UI
- Added graceful cleanup methods to ensure firewall rules are restored on exit

**Why SimpleWall?**
I opted to integrate with SimpleWall rather than building a custom firewall solution from scratch due to strict project timelines. Implementing a robust Windows Filtering Platform (WFP) driver or reverse-engineering the complex SimpleWall codebase was deemed too time-consuming for the initial release. This is a temporary workaround, and I plan to replace this external dependency with native firewall rules in future updates.

### 3. System-Wide Keyboard Blocking on Windows

**The Problem:**
To prevent cheating, we needed to block critical keyboard shortcuts (Alt+Tab, Ctrl+Alt+Del, Windows key, etc.) during exam mode. Standard PyQt key event handling cannot intercept system-level hotkeys before Windows processes them.

**The Solution:**
- Implemented low-level keyboard hooks using Windows API (`SetWindowsHookEx`)
- Created a separate `keyblocks.py` module with ctypes bindings to Windows DLLs
- Used a callback function to intercept and filter keyboard events at the OS level
- Maintained a whitelist of allowed keys during exam mode
- Ensured proper cleanup to restore normal keyboard functionality after exams

**Technical Implementation:**
- Used `WH_KEYBOARD_LL` hook type for system-wide keyboard interception
- Implemented `CallNextHookEx` to maintain system stability
- Added thread-safe hook installation/removal

### 4. Preventing Screen Capture and Task Recording

**The Problem:**
Users could potentially capture test content using screen recording software or screenshots. Windows 10+ provides a `WDA_EXCLUDEFROMCAPTURE` API, but it needs proper integration with PyQt6 windows.

**The Solution:**
- Used Windows API `SetWindowDisplayAffinity` with `WDA_EXCLUDEFROMCAPTURE` flag
- Applied the setting to the browser window handle after widget initialization
- Ensured compatibility with different Windows versions
- This prevents the window content from appearing in screen captures, Teams recordings, etc.


## Open Challenges

### Areas for Future Improvement

1. **Cross-Platform Support**: Currently Windows-only; Mac/Linux support requires platform-specific implementations
2. **Video Proctoring**: Integration of webcam monitoring and facial recognition
3. **Advanced Analytics**: Machine learning for suspicious behavior detection
4. **Offline Mode**: Support for tests without continuous internet connectivity
5. **Mobile Support**: Native apps for iOS/Android
6. **Accessibility**: WCAG compliance for users with disabilities

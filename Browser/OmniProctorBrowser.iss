; ============================================================================
; OmniProctor Secure Browser - Inno Setup installer script
; ============================================================================
;
; Build with:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" OmniProctorBrowser.iss
;
; Output:
;   Output\OmniProctorSetup-{#MyAppVersion}.exe
;
; Prerequisites:
;   1. Run pyinstaller first:
;        uv run pyinstaller OmniProctorBrowser.spec --noconfirm --clean
;      This produces dist\OmniProctorBrowser\ which this script bundles.
;   2. Inno Setup 6 must be installed (https://jrsoftware.org/isdl.php).
;
; What this installer does:
;   - Installs the kiosk to C:\Program Files\OmniProctor\
;   - Registers the omniproctor-browser:// URL protocol so a click on
;     "Start Test" in the WebClient launches the kiosk
;   - Creates Start Menu + Desktop shortcuts (Run as administrator
;     enforced via the EXE's embedded manifest)
;   - On uninstall, runs --firewall-recover so a crashed mid-exam
;     session doesn't leave the user without internet
; ============================================================================

#define MyAppName       "OmniProctor Browser"
#define MyAppShortName  "OmniProctorBrowser"
#define MyAppVersion    "0.1.0"
#define MyAppPublisher  "OmniProctor"
#define MyAppURL        "https://omniproctor.example.com"
#define MyAppExeName    "OmniProctorBrowser.exe"
#define MyAppId         "{{C9E2A6F0-9B7A-4ABC-9876-OMNIPROC0001}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

DefaultDirName={autopf}\OmniProctor
DefaultGroupName=OmniProctor
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=no
AllowNoIcons=yes

OutputDir=Output
OutputBaseFilename=OmniProctorSetup-{#MyAppVersion}
Compression=lzma2/ultra
SolidCompression=yes
LZMAUseSeparateProcess=yes

PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

WizardStyle=modern
SetupIconFile=browser\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

CloseApplications=force
RestartApplications=no

; Refuse to run on anything older than Windows 10 (1809+).
MinVersion=10.0.17763

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Bundle the entire onedir output. The spec produces:
;   dist\OmniProctorBrowser\OmniProctorBrowser.exe
;   dist\OmniProctorBrowser\_internal\... (Qt6, PyQt6, keyboard, etc.)
Source: "dist\OmniProctorBrowser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu - both shortcuts inherit the EXE's requireAdministrator
; manifest so they always elevate via UAC.
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; URL protocol registration. Installed under HKCR (machine-wide) so
; every browser on the machine sees the handler. uninsdeletekey wipes
; the whole subtree on uninstall.
Root: HKCR; Subkey: "omniproctor-browser"; ValueType: string; ValueName: ""; ValueData: "URL:OmniProctor Browser"; Flags: uninsdeletekey
Root: HKCR; Subkey: "omniproctor-browser"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCR; Subkey: "omniproctor-browser\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"",0"
Root: HKCR; Subkey: "omniproctor-browser\shell"; ValueType: string; ValueName: ""; ValueData: "open"
Root: HKCR; Subkey: "omniproctor-browser\shell\open"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"
Root: HKCR; Subkey: "omniproctor-browser\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
; Belt-and-braces: ask the kiosk to (re-)register its protocol handler
; on every install/upgrade. This is idempotent and covers the case
; where a user previously ran the EXE without an installer.
Filename: "{app}\{#MyAppExeName}"; Parameters: "--register-protocol"; Flags: runhidden waituntilterminated; StatusMsg: "Registering URL protocol..."

; Optional post-install launch.
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Safety net: if the kiosk crashed mid-exam, this restores the user's
; firewall + gestures + Task Manager state before the files are
; removed. --system-recover is idempotent and exits cleanly even if
; nothing was left over.
Filename: "{app}\{#MyAppExeName}"; Parameters: "--system-recover"; Flags: runhidden waituntilterminated; RunOnceId: "OmniProctorSystemRecover"
Filename: "{app}\{#MyAppExeName}"; Parameters: "--unregister-protocol"; Flags: runhidden waituntilterminated; RunOnceId: "OmniProctorUnregister"

[UninstallDelete]
; The kiosk writes logs and cache under %LOCALAPPDATA% per-user; we
; intentionally do NOT delete those (they belong to the candidate's
; profile). Only files installed by this installer are removed.
Type: dirifempty; Name: "{app}"

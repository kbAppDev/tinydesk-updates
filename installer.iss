#define AppVersion "2.1.0"
[Setup]
AppId={{FB6BBEE5-E9F0-4DD0-9F87-C15E546129B4}
AppName=Flare Tools - Image Compressor
AppVersion={#AppVersion}
AppPublisher=Flare Fireplaces
AppPublisherURL=https://github.com/kbAppDev/tinydesk-updates
AppSupportURL=https://github.com/kbAppDev/tinydesk-updates/issues
AppUpdatesURL=https://github.com/kbAppDev/tinydesk-updates/releases
DefaultDirName={localappdata}\Programs\Flare Tools\Image Compressor
DefaultGroupName=Flare Tools
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=Flare-Image-Compressor-Setup-{#AppVersion}
SetupIconFile=assets\FlareTools.ico
UninstallDisplayIcon={app}\FlareImageCompressor.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoVersion={#AppVersion}.0

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Files]
Source: "dist\FlareImageCompressor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Image Compressor"; Filename: "{app}\FlareImageCompressor.exe"; AppUserModelID: "FlareTools.ImageCompressor"
Name: "{autodesktop}\Flare Image Compressor"; Filename: "{app}\FlareImageCompressor.exe"; Tasks: desktopicon; AppUserModelID: "FlareTools.ImageCompressor"

[Run]
Filename: "{app}\FlareImageCompressor.exe"; Description: "Launch Flare Image Compressor"; Flags: nowait postinstall skipifsilent

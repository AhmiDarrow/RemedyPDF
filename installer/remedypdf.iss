; RemedyPDF — Inno Setup 6 installer
; Built by build_windows.py (defines MyAppVersion, DistDir)

#ifndef MyAppVersion
  #define MyAppVersion "1.4.6"
#endif
#ifndef DistDir
  #define DistDir "..\dist"
#endif

#define MyAppName "RemedyPDF"
#define MyAppPublisher "Ahmi Darrow"
#define MyAppURL "https://github.com/AhmiDarrow/RemedyPDF"
#define MyAppExeName "RemedyPDF.exe"
#define MyAppId "{{B7E2C4A1-8F3D-4A9E-9C1B-5D6E8F0A2B3C}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir={#DistDir}
OutputBaseFilename=RemedyPDF-{#MyAppVersion}-windows-setup
SetupIconFile=..\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[CustomMessages]
english.AboutReleases=About RemedyPDF (Releases)
spanish.AboutReleases=Acerca de RemedyPDF (versiones)
french.AboutReleases=À propos de RemedyPDF (versions)
german.AboutReleases=Über RemedyPDF (Versionen)
brazilianportuguese.AboutReleases=Sobre o RemedyPDF (versões)
italian.AboutReleases=Informazioni su RemedyPDF (versioni)
russian.AboutReleases=О RemedyPDF (выпуски)
polish.AboutReleases=O RemedyPDF (wydania)
japanese.AboutReleases=RemedyPDF について (リリース)
korean.AboutReleases=RemedyPDF 정보 (릴리스)
chinesesimplified.AboutReleases=关于 RemedyPDF（发布）

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; onedir build — install the whole folder (exe + _internal DLLs) so python312.dll
; lives next to the exe; no %TEMP% extraction, no onefile bootloader race.
Source: "{#DistDir}\RemedyPDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\resources\icon.png"; DestDir: "{app}\resources"; Flags: ignoreversion
Source: "..\resources\icon.ico"; DestDir: "{app}\resources"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\resources\logo_ui.png"; DestDir: "{app}\resources"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:AboutReleases}"; Filename: "{#MyAppURL}/releases"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

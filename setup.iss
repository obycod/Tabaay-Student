[Setup]
AppName=تحديث القلم الذكي
AppVersion=5.1
DefaultDirName={autopf}\AlTabaayStudent
DefaultGroupName=Al-Tabaay
OutputDir=Output
OutputBaseFilename=Tabaay_Student_Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=web\icon.ico
PrivilegesRequired=admin

[Files]
Source: "dist\Tabaay_Student\Tabaay_Student.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Tabaay_Student\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\تحديث القلم الذكي"; Filename: "{app}\Tabaay_Student.exe"
Name: "{autodesktop}\تحديث القلم الذكي"; Filename: "{app}\Tabaay_Student.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "إنشاء اختصار على سطح المكتب"; GroupDescription: "اختصارات إضافية:"

[Run]
Filename: "{app}\Tabaay_Student.exe"; Description: "تشغيل البرنامج الآن"; Flags: nowait postinstall skipifsilent
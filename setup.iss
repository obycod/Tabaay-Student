[Setup]
AppName=تحديث القلم الذكي
AppVersion=5.1
DefaultDirName={autopf}\AlTabaayStudent
DefaultGroupName=Al-Tabaay
OutputDir=Output
OutputBaseFilename=Tabaay_Student_Setup
Compression=lzma
SolidCompression=yes
; أضف أيقونة إذا كان لديك ملف icon.ico
; SetupIconFile=icon.ico
PrivilegesRequired=admin

[Files]
; يسحب ملف الـ exe اللي راح يصنعه GitHub Actions
Source: "dist\Tabaay_Student.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\تحديث القلم الذكي"; Filename: "{app}\Tabaay_Student.exe"
Name: "{autodesktop}\تحديث القلم الذكي"; Filename: "{app}\Tabaay_Student.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "إنشاء اختصار على سطح المكتب"; GroupDescription: "اختصارات إضافية:"

[Run]
Filename: "{app}\Tabaay_Student.exe"; Description: "تشغيل البرنامج الآن"; Flags: nowait postinstall skipifsilent
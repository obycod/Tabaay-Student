[Setup]
AppName=تحديث القلم الذكي
AppVersion=11.5
DefaultDirName={autopf}\AlTabaayStudent
DefaultGroupName=Al-Tabaay
OutputDir=Output
OutputBaseFilename=Tabaay_Student_Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=web\icon.ico
PrivilegesRequired=admin
CloseApplications=force

[InstallDelete]
; مسح أي ملفات قديمة متبقية في مجلد البرنامج لضمان تثبيت نظيف 100%
Type: filesandordirs; Name: "{app}\*"

[Files]
Source: "dist\Tabaay_Student\Tabaay_Student.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Tabaay_Student\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "web\*"; DestDir: "{app}\web"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\web\assets"; Permissions: users-modify

[Icons]
Name: "{group}\تحديث القلم الذكي"; Filename: "{app}\Tabaay_Student.exe"
Name: "{autodesktop}\تحديث القلم الذكي"; Filename: "{app}\Tabaay_Student.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "إنشاء اختصار على سطح المكتب"; GroupDescription: "اختصارات إضافية:"

[Run]
Filename: "{app}\Tabaay_Student.exe"; Description: "تشغيل البرنامج الآن"; Flags: nowait postinstall runasoriginaluser
; أمر لفتح البرنامج تلقائياً إذا كان التثبيت يعمل بصمت في الخلفية
Filename: "{app}\Tabaay_Student.exe"; Flags: nowait runasoriginaluser; Check: WizardSilent

[Code]
// هذه الدالة تبحث عن النسخة القديمة في الريجستري وتجلب مسار ملف الحذف
function GetUninstallString(): String;
var
  sUnInstPath, sUnInstallString: String;
begin
  sUnInstPath := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\تحديث القلم الذكي_is1';
  sUnInstallString := '';
  if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
    RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString);
  if (sUnInstallString = '') and IsWin64 then
  begin
    sUnInstPath := 'Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\تحديث القلم الذكي_is1';
    if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
      RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString);
  end;
  Result := sUnInstallString;
end;

// هذه الدالة تعمل تلقائياً عند بدء التنصيب
function InitializeSetup(): Boolean;
var
  sUnInstallString: String;
  AppDir: String;
  iResultCode: Integer;
begin
  Result := True;
  sUnInstallString := GetUninstallString();
  if sUnInstallString <> '' then 
  begin
    sUnInstallString := RemoveQuotes(sUnInstallString);
    AppDir := ExtractFileDir(sUnInstallString);
    // إضافة /_?= مع مسار البرنامج تمنع برنامج الحذف من الانفصال والعمل في الخلفية، مما يحل مشكلة مسح المجلد بالكامل
    Exec(sUnInstallString, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /_?="' + AppDir + '"', '', SW_HIDE, ewWaitUntilTerminated, iResultCode);
  end;
end;
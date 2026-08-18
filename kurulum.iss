; PicaYT kurulum betigi (Inno Setup 6)
;
; Derleme:  ISCC.exe /DSURUM=1.0.0 kurulum.iss
; paketle.py bunu --kurulum bayragiyla kendisi cagirir.
;
; Kurulum kullanici bazlidir: yonetici hakki ve UAC istemi gerekmez, bu da
; sessiz guncellemenin sorunsuz calismasini saglar.

#ifndef SURUM
  #define SURUM "1.0.0"
#endif

#define UYGULAMA "PicaYT"
#define YAYINCI "PicaYT"
#define URL "https://github.com/enesscelik/PicaYT"

[Setup]
AppId={{8F3A6C21-4B7E-4E9A-9E2D-1C5B7A9D3E44}
AppName={#UYGULAMA}
AppVersion={#SURUM}
AppVerName={#UYGULAMA} {#SURUM}
AppPublisher={#YAYINCI}
AppPublisherURL={#URL}
AppSupportURL={#URL}/issues
AppUpdatesURL={#URL}/releases
VersionInfoVersion={#SURUM}
DefaultDirName={autopf}\{#UYGULAMA}
DefaultGroupName={#UYGULAMA}
DisableProgramGroupPage=yes
DisableDirPage=auto
UninstallDisplayIcon={app}\{#UYGULAMA}.exe
UninstallDisplayName={#UYGULAMA} {#SURUM}
OutputDir=dagitim
OutputBaseFilename=PicaYT-Kurulum-{#SURUM}
SetupIconFile=picayt.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Kullanici bazli kurulum: UAC yok, sessiz guncelleme icin sart.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Guncellemede acik olan surumun kapatilmasi
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=yes

[Languages]
Name: "turkce"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "masaustu"; Description: "Masaüstüne kısayol ekle"; \
  GroupDescription: "Ek kısayollar:"

[Files]
Source: "dagitim\PicaYT\PicaYT.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dagitim\PicaYT\_internal\*"; DestDir: "{app}\_internal"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dagitim\PicaYT\ffmpeg\*"; DestDir: "{app}\ffmpeg"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dagitim\PicaYT\paketler\*"; DestDir: "{app}\paketler"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dagitim\PicaYT\js\*"; DestDir: "{app}\js"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "OKUBENI.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#UYGULAMA}"; Filename: "{app}\{#UYGULAMA}.exe"
Name: "{group}\{#UYGULAMA} kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#UYGULAMA}"; Filename: "{app}\{#UYGULAMA}.exe"; \
  Tasks: masaustu

[Run]
Filename: "{app}\{#UYGULAMA}.exe"; \
  Description: "{#UYGULAMA} uygulamasını şimdi çalıştır"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Eski yt-dlp surumleri ve gecici guncelleme dosyalari
Type: filesandordirs; Name: "{localappdata}\PicaYT\paketler"
Type: filesandordirs; Name: "{localappdata}\PicaYT\gecici"

[Code]
// Sessiz guncellemede uygulama yeniden baslatilirken eski surum kapanmis
// olmali; Inno bunu CloseApplications ile hallediyor. Ayarlar ve gecmis
// {localappdata}\PicaYT altinda oldugu icin guncelleme onlara dokunmaz.

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('Ayarlar ve indirme geçmişi de silinsin mi?' + #13#10 +
              'İndirdiğin videolar silinmez.',
              mbConfirmation, MB_YESNO) = IDYES then
      DelTree(ExpandConstant('{localappdata}\PicaYT'), True, True, True);
  end;
end;

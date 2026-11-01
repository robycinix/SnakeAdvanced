; Script Inno Setup per Snake Advanced (richiede Inno Setup 6.7+).
; Viene compilato da build.py dopo aver creato dist\SnakeAdvanced.exe e la
; grafica in build\installer (pannello, logo, sfondo, fotogrammi del serpente).
; Installa per l'utente corrente (nessun permesso di amministratore richiesto).

#define AppName "Snake Advanced"
#define AppVersion "1.0.0"
#define AppExe "SnakeAdvanced.exe"
#define Art "..\build\installer"

[Setup]
AppId={{7E3C2B1A-5D4F-4A8E-9C61-2F0B7A9D4E51}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Roby
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=SnakeAdvanced-Setup
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes

; --- Aspetto: giungla notturna invece del classico Windows ---
WizardStyle=modern dark hidebevels
WizardBackColor=#0a1417
WizardBackImageFile={#Art}\wizard_back.png
WizardImageFile={#Art}\wizard_large_164.png,{#Art}\wizard_large_205.png,{#Art}\wizard_large_246.png,{#Art}\wizard_large_328.png
WizardSmallImageFile={#Art}\wizard_small_55.png,{#Art}\wizard_small_69.png,{#Art}\wizard_small_83.png,{#Art}\wizard_small_110.png
WizardImageBackColor=#0a1417

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Messages]
italian.WelcomeLabel1=Benvenuto nella giungla di [name]!
italian.WelcomeLabel2=Stai per liberare un serpente affamato sul tuo computer.%n%nMele, rivali, boss, tunnel di teletrasporto, veleno e salti ti aspettano.%n%nChiudi le altre applicazioni e premi Avanti per cominciare.
italian.WizardSelectDir=Dove deve vivere il serpente?
italian.SelectDirDesc=Scegli la tana di [name].
italian.SelectDirLabel3=Il serpente si installerà in questa cartella.
italian.WizardReady=Il serpente è pronto a strisciare
italian.ReadyLabel1=Tutto pronto per installare [name] sul tuo computer.
italian.WizardInstalling=Il serpente sta strisciando...
italian.InstallingLabel=Attendi mentre [name] si fa strada nel tuo computer mangiando mele.
italian.StatusExtractFiles=Il serpente sta divorando i file...
italian.StatusCreateIcons=Scavo dei collegamenti nella tana...
italian.FinishedHeadingLabel=Il serpente è libero!
italian.FinishedLabel=[name] è stato installato. Avvialo dai collegamenti e prova a battere il record.
italian.FinishedLabelNoIcons=[name] è stato installato. Prova a battere il record!

[Tasks]
Name: "desktopicon"; Description: "Metti il serpente sul desktop"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
; Fotogrammi del serpente-barra: usati solo durante l'installazione
Source: "{#Art}\progress_*.bmp"; Flags: dontcopy

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Gioca subito a {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
{ La barra di avanzamento standard viene nascosta e sostituita da un'immagine:
  un serpente che si allunga lungo una pista mangiando le mele.
  I fotogrammi (generati da build.py) vengono estratti nella cartella temporanea
  all'avvio e mostrati in base alla percentuale di installazione. }
const
  FRAMES = 25;          { Deve coincidere con PROGRESS_FRAMES in build.py }
  FRAME_W = 480;
  FRAME_H = 64;

var
  SnakeBar: TBitmapImage;
  PercentLabel: TNewStaticText;
  LastFrame: Integer;

function FrameName(Index: Integer): String;
begin
  if Index < 10 then
    Result := 'progress_0' + IntToStr(Index) + '.bmp'
  else
    Result := 'progress_' + IntToStr(Index) + '.bmp';
end;

procedure ShowFrame(Index: Integer);
begin
  if Index < 0 then Index := 0;
  if Index > FRAMES - 1 then Index := FRAMES - 1;
  if Index = LastFrame then Exit;
  LastFrame := Index;
  SnakeBar.Bitmap.LoadFromFile(ExpandConstant('{tmp}\') + FrameName(Index));
end;

procedure InitializeWizard;
var
  I: Integer;
  Gauge: TNewProgressBar;
begin
  for I := 0 to FRAMES - 1 do
    ExtractTemporaryFile(FrameName(I));

  Gauge := WizardForm.ProgressGauge;
  SnakeBar := TBitmapImage.Create(WizardForm);
  SnakeBar.Parent := Gauge.Parent;
  SnakeBar.Left := Gauge.Left;
  SnakeBar.Top := Gauge.Top;
  SnakeBar.Width := Gauge.Width;
  SnakeBar.Height := Gauge.Width * FRAME_H div FRAME_W;
  SnakeBar.Stretch := True;
  SnakeBar.Visible := False;

  PercentLabel := TNewStaticText.Create(WizardForm);
  PercentLabel.Parent := Gauge.Parent;
  PercentLabel.Left := Gauge.Left;
  PercentLabel.Top := SnakeBar.Top + SnakeBar.Height + ScaleY(8);
  PercentLabel.Caption := '';
  PercentLabel.Visible := False;

  LastFrame := -1;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpInstalling then
  begin
    WizardForm.ProgressGauge.Visible := False;
    SnakeBar.Visible := True;
    PercentLabel.Visible := True;
    ShowFrame(0);
  end;
end;

procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
var
  Percent: Integer;
begin
  WizardForm.ProgressGauge.Visible := False;
  if MaxProgress <= 0 then Exit;
  Percent := (CurProgress div 1000) * 100 div ((MaxProgress div 1000) + 1);
  if CurProgress >= MaxProgress then Percent := 100;
  ShowFrame(Percent * (FRAMES - 1) div 100);
  PercentLabel.Caption := 'Il serpente ha mangiato il ' + IntToStr(Percent) + '% del percorso';
end;

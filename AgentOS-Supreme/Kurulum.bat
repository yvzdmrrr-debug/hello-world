@echo off
setlocal
title AgentOS Supreme Kurulum
cd /d "%~dp0"
set "APPDIR=%~dp0"

echo.
echo   AgentOS Supreme kuruluyor...
echo.

where node >nul 2>nul
if errorlevel 1 (
  echo   Node.js bulunamadi. Otomatik kurulum deneniyor...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo.
    echo   Node.js otomatik kurulamadi. https://nodejs.org adresinden LTS surumunu kurun,
    echo   sonra Kurulum.bat dosyasini yeniden calistirin.
    pause
    exit /b 1
  )
  winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
  echo.
  echo   Node.js kuruldu. Bu pencereyi kapatip Kurulum.bat dosyasini yeniden calistirin.
  pause
  exit /b 0
)

echo   Bilesenler indiriliyor (ilk kurulum birkac dakika surebilir)...
call npm install --no-audit --no-fund
if errorlevel 1 (
  echo.
  echo   Kurulum basarisiz oldu. Internet baglantinizi kontrol edip yeniden deneyin.
  pause
  exit /b 1
)

if not exist "%APPDIR%node_modules\electron\dist\electron.exe" (
  echo.
  echo   Electron indirilemedi. Kurulum.bat dosyasini yeniden calistirin.
  pause
  exit /b 1
)

echo   Masaustu kisayolu olusturuluyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=$env:APPDIR; $w=New-Object -ComObject WScript.Shell; $k=$w.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'AgentOS Supreme.lnk')); $k.TargetPath=(Join-Path $d 'node_modules\electron\dist\electron.exe'); $k.Arguments='\"'+$d.TrimEnd('\')+'\"'; $k.WorkingDirectory=$d; $k.Description='AgentOS Supreme'; $k.Save()"
if errorlevel 1 (
  echo   Kisayol olusturulamadi; uygulamayi bu klasordeki Baslat.vbs ile acabilirsiniz.
)

echo.
echo   Kurulum tamamlandi. Masaustundeki "AgentOS Supreme" kisayolu ile acabilirsiniz.
echo   Uygulama simdi baslatiliyor...
start "" "%APPDIR%node_modules\electron\dist\electron.exe" "%APPDIR%."
timeout /t 3 >nul
endlocal

$processes = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" |
  Where-Object {
    $_.CommandLine -like "* -File *start-live-server.ps1*" -or
    $_.CommandLine -like "*\scripts\start-live-server.ps1*"
  }

if (-not $processes) {
  Write-Host "No local live server process was found."
  exit 0
}

foreach ($process in $processes) {
  Write-Host "Stopping local live server process $($process.ProcessId)."
  Stop-Process -Id $process.ProcessId -Force
}

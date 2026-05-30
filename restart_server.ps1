param([int]$Port = 5000)

$ErrorActionPreference = 'SilentlyContinue'
$proj   = 'C:\Projects\PatternFoundry'
$python = "$proj\.venv\Scripts\python.exe"

# Kill any existing listener on the port
Get-NetTCPConnection -LocalPort $Port -State Listen | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force
}
Start-Sleep -Milliseconds 500

# Spawn via WMI — detached, no inherited handles
$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create `
    -Arguments @{
        CommandLine      = "`"$python`" app.py"
        CurrentDirectory = $proj
    }

if ($result.ReturnValue -ne 0) {
    Write-Host "Spawn failed (code $($result.ReturnValue))"
    exit 1
}

# Poll up to 10s
$deadline = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$Port/" -TimeoutSec 1 -UseBasicParsing
        if ($r.StatusCode -eq 200) {
            Write-Host "Server ready (PID $($result.ProcessId)) → http://127.0.0.1:$Port/"
            exit 0
        }
    } catch {}
    Start-Sleep -Milliseconds 400
}

Write-Host "Server did not respond within 10s (PID $($result.ProcessId)). Check flask.log."
exit 1

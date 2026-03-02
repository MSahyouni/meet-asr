$ErrorActionPreference = "Stop"

$root = Resolve-Path $PSScriptRoot
Set-Location $root

$venvDir = Join-Path $root ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$apiDir = Join-Path $root "apps\api"
$requirementsFile = Join-Path $apiDir "requirements.txt"
$requirementsStamp = Join-Path $venvDir ".requirements.sha256"
$url = "http://127.0.0.1:8000/"
$hostName = "127.0.0.1"
$port = 8000

Write-Host "[run] Root: $root" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python غير موجود في PATH. ثبت Python ثم أعد المحاولة."
}

if (-not (Test-Path $venvPython)) {
    Write-Host "[run] إنشاء البيئة الافتراضية .venv ..." -ForegroundColor Yellow
    python -m venv .venv
}

if (-not (Test-Path (Join-Path $apiDir "api.py"))) {
    throw "ملف api.py غير موجود في: $apiDir"
}

if (-not (Test-Path $requirementsFile)) {
    throw "ملف requirements.txt غير موجود في: $requirementsFile"
}

$currentReqHash = (Get-FileHash -Path $requirementsFile -Algorithm SHA256).Hash
$installedReqHash = ""
if (Test-Path $requirementsStamp) {
    $installedReqHash = ((Get-Content -Path $requirementsStamp -ErrorAction SilentlyContinue | Select-Object -First 1) -as [string]).Trim()
}

if ($currentReqHash -ne $installedReqHash) {
    Write-Host "[run] تثبيت/تحديث المتطلبات من requirements.txt ..." -ForegroundColor Yellow
    & $venvPython -m pip install -U pip
    if ($LASTEXITCODE -ne 0) {
        throw "فشل تحديث pip داخل البيئة الافتراضية."
    }

    & $venvPython -m pip install -r $requirementsFile
    if ($LASTEXITCODE -ne 0) {
        throw "فشل تثبيت المتطلبات من $requirementsFile"
    }

    Set-Content -Path $requirementsStamp -Value $currentReqHash -Encoding UTF8
    Write-Host "[run] اكتمل تثبيت المتطلبات." -ForegroundColor Green
} else {
    Write-Host "[run] المتطلبات مثبتة مسبقًا ولا يوجد تغيّر." -ForegroundColor DarkGray
}

Write-Host "[run] سيتم فتح المتصفح تلقائياً عند جاهزية السيرفر..." -ForegroundColor Green
Start-Job -Name "meetasr-open-browser" -ScriptBlock {
    param($Url, $HostName, $Port)
    for ($i = 0; $i -lt 90; $i++) {
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $client.Connect($HostName, $Port)
            if ($client.Connected) {
                $client.Close()
                Start-Process $Url
                return
            }
        } catch {
        }
        Start-Sleep -Seconds 1
    }
} -ArgumentList $url, $hostName, $port | Out-Null

Write-Host "[run] تشغيل السيرفر من البيئة الافتراضية..." -ForegroundColor Green
Write-Host "[run] للإيقاف: Ctrl+C" -ForegroundColor DarkGray

Set-Location $apiDir
& $venvPython -m uvicorn api:app --host 0.0.0.0 --port 8000

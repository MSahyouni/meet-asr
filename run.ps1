$ErrorActionPreference = "Stop"

$root = Resolve-Path $PSScriptRoot
Set-Location $root

$preferredVenvDir = Join-Path $root ".venv"
$legacyVenvDir = Join-Path $root "venv"
$venvDir = $preferredVenvDir

if ((-not (Test-Path (Join-Path $preferredVenvDir "Scripts\python.exe"))) -and
    (Test-Path (Join-Path $legacyVenvDir "Scripts\python.exe")) -and
    (-not (Test-Path $preferredVenvDir))) {
    Write-Host "[run] ربط .venv بـ venv القديم للتوافق..." -ForegroundColor Yellow
    New-Item -ItemType Junction -Path $preferredVenvDir -Target $legacyVenvDir | Out-Null
}

if (Test-Path (Join-Path $preferredVenvDir "Scripts\python.exe")) {
    $venvDir = $preferredVenvDir
    Write-Host "[run] استخدام البيئة الافتراضية: .venv" -ForegroundColor DarkGray
} elseif (Test-Path (Join-Path $legacyVenvDir "Scripts\python.exe")) {
    $venvDir = $legacyVenvDir
    Write-Host "[run] تم اكتشاف venv (قديم) وسيتم استخدامه." -ForegroundColor Yellow
    Write-Host "[run] للتوحيد لاحقًا: أعد إنشاء البيئة باسم .venv." -ForegroundColor DarkGray
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"
$apiDir = Join-Path $root "apps\api"
$requirementsFile = Join-Path $apiDir "requirements.txt"
$requirementsStamp = Join-Path $venvDir ".requirements.sha256"
$hostName = "127.0.0.1"
$port = 8000

function Test-PortInUse {
    param([int]$Port)

    try {
        $matches = netstat -ano | Select-String -Pattern ":$Port\s+.*LISTENING\s+"
        return ($matches.Count -gt 0)
    } catch {
        return $false
    }
}

$maxPortAttempts = 20
$initialPort = $port
for ($attempt = 0; $attempt -lt $maxPortAttempts; $attempt++) {
    if (-not (Test-PortInUse -Port $port)) {
        break
    }
    $port++
}

if ($port -ne $initialPort) {
    Write-Host "[run] المنفذ $initialPort مشغول. سيتم استخدام المنفذ البديل: $port" -ForegroundColor Yellow
}

if (Test-PortInUse -Port $port) {
    throw "تعذّر العثور على منفذ متاح بدءًا من $initialPort. حرّر المنفذ أو زد نطاق البحث في run.ps1."
}

$url = "http://${hostName}:$port/"

Write-Host "[run] Root: $root" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python غير موجود في PATH. ثبت Python ثم أعد المحاولة."
}

if (-not (Test-Path $venvPython)) {
    Write-Host "[run] إنشاء البيئة الافتراضية .venv ..." -ForegroundColor Yellow
    python -m venv $preferredVenvDir
    $venvDir = $preferredVenvDir
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $requirementsStamp = Join-Path $venvDir ".requirements.sha256"
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
Get-Job -Name "meetasr-open-browser" -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue
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
& $venvPython -m uvicorn api:app --host 0.0.0.0 --port $port
$uvicornExitCode = $LASTEXITCODE

if (($uvicornExitCode -eq 0) -or ($uvicornExitCode -eq 1) -or ($uvicornExitCode -eq 130) -or ($uvicornExitCode -eq 3221225786)) {
    Write-Host "[run] تم إيقاف السيرفر بشكل طبيعي." -ForegroundColor DarkGray
    exit 0
}

throw "توقّف uvicorn بكود خروج غير متوقع: $uvicornExitCode"

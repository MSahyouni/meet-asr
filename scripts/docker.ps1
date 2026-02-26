param(
    [ValidateSet("up", "down", "logs", "ps", "restart", "pull")]
    [string]$Action = "up",

    [ValidateSet("dev", "prod")]
    [string]$Env = "dev"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$composeFile = if ($Env -eq "prod") { "docker-compose.prod.yml" } else { "docker-compose.yml" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker غير مثبت أو غير متاح في PATH"
}

Write-Host "[docker] action=$Action env=$Env file=$composeFile" -ForegroundColor Cyan

switch ($Action) {
    "up" {
        docker compose -f $composeFile up -d --build
    }
    "down" {
        docker compose -f $composeFile down
    }
    "logs" {
        docker compose -f $composeFile logs -f api
    }
    "ps" {
        docker compose -f $composeFile ps
    }
    "restart" {
        docker compose -f $composeFile restart api
    }
    "pull" {
        docker compose -f $composeFile pull
    }
}

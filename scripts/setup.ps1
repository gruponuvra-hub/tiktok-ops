# Instalacao do tiktok-ops no Windows.
# Rode no terminal do VS Code:   .\scripts\setup.ps1
# Se o PowerShell recusar por politica de execucao:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Verificando Python" -ForegroundColor Cyan
$py = $null
foreach ($cmd in @("py -3.12", "py -3.11", "python", "python3")) {
    $parts = $cmd.Split(" ")
    $exe = Get-Command $parts[0] -ErrorAction SilentlyContinue
    if ($exe) {
        $ver = & $parts[0] $parts[1..$parts.Length] --version 2>&1
        if ($ver -match "3\.(1[1-9]|[2-9]\d)") { $py = $cmd; break }
    }
}
if (-not $py) {
    Write-Host "Python 3.11 ou superior nao encontrado." -ForegroundColor Red
    Write-Host "Instale em https://www.python.org/downloads/ marcando 'Add to PATH'."
    exit 1
}
Write-Host "    usando: $py" -ForegroundColor Green

Write-Host "==> Criando o ambiente virtual" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    $parts = $py.Split(" ")
    & $parts[0] $parts[1..$parts.Length] -m venv .venv
}

Write-Host "==> Instalando as dependencias" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]" --quiet

Write-Host "==> Rodando os testes" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pytest -q

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host ""
Write-Host "Pronto." -ForegroundColor Green
Write-Host "Ative o ambiente com:  .\.venv\Scripts\Activate.ps1"
Write-Host "Depois experimente:    tiktok-ops --help"

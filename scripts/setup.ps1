# Instalacao do tiktok-ops no Windows.
#
# Rode no terminal do VS Code:
#     powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
#
# (O Windows bloqueia scripts .ps1 por padrao; o -ExecutionPolicy Bypass acima
#  vale so para essa execucao e nao muda nada no sistema.)

Set-Location (Split-Path $PSScriptRoot -Parent)

function Find-Python {
    $candidatos = @()

    # 1. O que estiver no PATH. O "py" e o lancador oficial do Windows.
    $noPath = @(
        @{ Exe = "py";      Args = @("-3.13") },
        @{ Exe = "py";      Args = @("-3.12") },
        @{ Exe = "py";      Args = @("-3.11") },
        @{ Exe = "py";      Args = @("-3")    },
        @{ Exe = "python";  Args = @()        },
        @{ Exe = "python3"; Args = @()        }
    )
    foreach ($c in $noPath) {
        $cmd = Get-Command $c.Exe -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }

        # O Windows instala um atalho falso em WindowsApps que apenas abre a
        # Microsoft Store. Ele responde ao Get-Command, mas nao e um Python.
        if ($cmd.Source -and $cmd.Source -like "*\WindowsApps\*") { continue }

        $candidatos += $c
    }

    # 2. Locais de instalacao padrao. E comum o Python estar instalado mas fora
    #    do PATH, quando a opcao "Add python.exe to PATH" nao foi marcada.
    $raizes = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python"),
        $env:ProgramFiles,
        [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    )
    foreach ($raiz in $raizes) {
        if ([string]::IsNullOrEmpty($raiz)) { continue }
        if (-not (Test-Path $raiz)) { continue }

        $dirs = Get-ChildItem -Path $raiz -Filter "Python3*" -Directory -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending
        foreach ($dir in $dirs) {
            $exe = Join-Path $dir.FullName "python.exe"
            if (Test-Path $exe) { $candidatos += @{ Exe = $exe; Args = @() } }
        }
    }

    foreach ($c in $candidatos) {
        try {
            $saida = (& $c.Exe @($c.Args) --version 2>&1 | Out-String).Trim()
        } catch {
            continue
        }

        if ($saida -match "Python (\d+)\.(\d+)") {
            $maior = [int]$Matches[1]
            $menor = [int]$Matches[2]
            if ($maior -gt 3 -or ($maior -eq 3 -and $menor -ge 11)) {
                return @{ Exe = $c.Exe; Args = $c.Args; Versao = $saida }
            }
        }
    }
    return $null
}

Write-Host "==> Procurando Python 3.11 ou superior" -ForegroundColor Cyan
$py = Find-Python

if (-not $py) {
    Write-Host ""
    Write-Host "Python 3.11 ou superior nao foi encontrado." -ForegroundColor Red
    Write-Host "(Procurei no PATH e em Programs\\Python, Program Files e Program Files (x86).)"
    Write-Host ""
    Write-Host "Instale com um comando so:" -ForegroundColor Yellow
    Write-Host "    winget install -e --id Python.Python.3.12"
    Write-Host ""
    Write-Host "Ou baixe em https://www.python.org/downloads/ marcando"
    Write-Host "'Add python.exe to PATH' na primeira tela do instalador."
    Write-Host ""
    Write-Host "Depois FECHE e reabra o terminal (para o PATH atualizar) e rode"
    Write-Host "este script de novo."
    exit 1
}

Write-Host "    encontrado: $($py.Versao)" -ForegroundColor Green

$ErrorActionPreference = "Stop"

Write-Host "==> Criando o ambiente virtual (.venv)" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    & $py.Exe @($py.Args) -m venv .venv
}

$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Falha ao criar o ambiente virtual em .venv" -ForegroundColor Red
    exit 1
}

Write-Host "==> Instalando as dependencias" -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -e ".[dev]" --quiet

Write-Host "==> Rodando os testes" -ForegroundColor Cyan
& $venvPython -m pytest -q

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host ""
Write-Host "Pronto." -ForegroundColor Green
Write-Host "Ative o ambiente com:  .\.venv\Scripts\Activate.ps1"
Write-Host "Depois experimente:    tiktok-ops --help"

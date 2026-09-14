# Cria o repositorio no GitHub e sobe o projeto.
# Rode DEPOIS do setup.ps1:   .\scripts\github-setup.ps1 -Repo "seu-usuario/tiktok-ops"
#
# Observacao: o PowerShell 5.1 (padrao do Windows) nao entende "&&" entre
# comandos. Por isso este script existe: cada comando vai em sua propria linha.

param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [switch]$Public
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "git nao encontrado. Instale em https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".git")) {
    git init -b main
}

git add .
git commit -m "feat: estrutura inicial do tiktok-ops"

$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
    $vis = if ($Public) { "--public" } else { "--private" }
    gh repo create $Repo $vis --source=. --push
} else {
    Write-Host "gh (GitHub CLI) nao encontrado." -ForegroundColor Yellow
    Write-Host "Crie o repositorio vazio em https://github.com/new e depois rode:"
    Write-Host "  git remote add origin https://github.com/$Repo.git"
    Write-Host "  git push -u origin main"
}

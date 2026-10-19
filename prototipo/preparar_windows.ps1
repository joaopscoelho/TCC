# Prepara o ambiente de testes no Windows e registra tudo em preparar_windows.log.
#
# Uso, na pasta prototipo:
#   powershell -ExecutionPolicy Bypass -File .\preparar_windows.ps1
#   powershell -ExecutionPolicy Bypass -File .\preparar_windows.ps1 -Falar
#
# Faz: acha o Python 3 (mesmo sem PATH), recria o .venv se ele for de Linux,
# instala o requirements.txt, roda os testes e confere o NVDA e a DLL. Com
# -Falar, e com o NVDA aberto e a DLL no lugar, o NVDA fala uma frase de teste.
# Nao muda configuracao do Windows nem instala nada fora desta pasta.
#
# O arquivo e so ASCII de proposito: o Windows PowerShell 5.1 le .ps1 sem BOM
# na codepage ANSI e estragaria os acentos.
param([switch]$Falar)

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$log = Join-Path $PSScriptRoot "preparar_windows.log"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $PSScriptRoot
Set-Content -Path $log -Value ("Preparacao iniciada em " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -Encoding UTF8

function Escrever([string]$texto) {
    Write-Host $texto
    Add-Content -Path $log -Value $texto -Encoding UTF8
}

function Executar([string]$titulo, [scriptblock]$bloco) {
    Escrever ""
    Escrever ("=== " + $titulo)
    & $bloco 2>&1 | ForEach-Object { Escrever ("" + $_) }
    Escrever ("(codigo de saida: " + $LASTEXITCODE + ")")
}

function TestarPython([string]$caminho) {
    if (-not $caminho) { return $null }
    if (-not (Test-Path $caminho)) { return $null }
    if ($caminho -like "*\WindowsApps\*") { return $null }   # atalho da Store, nao e Python
    $texto = (& $caminho --version 2>&1 | Out-String).Trim()
    if ($texto -match "^Python 3\.(\d+)\.") {
        if ([int]$Matches[1] -ge 9) { return $texto }
    }
    return $null
}

function AcharPython {
    $candidatos = New-Object System.Collections.ArrayList
    $raizes = @((Join-Path $env:LOCALAPPDATA "Programs\Python"), $env:ProgramFiles)
    foreach ($raiz in $raizes) {
        if (-not (Test-Path $raiz)) { continue }
        Get-ChildItem -Path $raiz -Directory -Filter "Python3*" -ErrorAction SilentlyContinue |
            Sort-Object { [int]($_.Name -replace '\D', '') } -Descending |
            ForEach-Object { [void]$candidatos.Add((Join-Path $_.FullName "python.exe")) }
    }
    $noPath = Get-Command python -ErrorAction SilentlyContinue
    if ($noPath) { [void]$candidatos.Add($noPath.Source) }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $viaPy = (& $py.Source -3 -c "import sys; print(sys.executable)" 2>&1 | Out-String).Trim()
        [void]$candidatos.Add($viaPy)
    }
    foreach ($c in $candidatos) {
        $versao = TestarPython $c
        if ($versao) { return @{ Caminho = $c; Versao = $versao } }
    }
    return $null
}

function ArquiteturaDaDll([string]$caminho) {
    try {
        $b = [System.IO.File]::ReadAllBytes($caminho)
        $pe = [BitConverter]::ToInt32($b, 60)
        $m = [BitConverter]::ToUInt16($b, $pe + 4)
        switch ($m) {
            34404 { return "x64" }
            332 { return "x86" }
            43620 { return "arm64" }
            default { return ("desconhecida (codigo " + $m + ")") }
        }
    } catch {
        return "nao foi possivel ler"
    }
}

Escrever ("Pasta: " + $PSScriptRoot)
Escrever ("Windows: " + [System.Environment]::OSVersion.VersionString + ", arquitetura " + $env:PROCESSOR_ARCHITECTURE)

$achado = AcharPython
if (-not $achado) {
    Escrever "ERRO: nenhum Python 3.9 ou mais novo foi encontrado (procurei em Programs\Python, Program Files, PATH e py)."
    Escrever "FIM (com erro)"
    exit 1
}
Escrever ("Python escolhido: " + $achado.Caminho + " (" + $achado.Versao + ")")
Executar "Arquitetura do Python" { & $achado.Caminho -c "import struct, platform; print(struct.calcsize('P') * 8, 'bits', platform.machine())" }

$pythonVenv = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if ((Test-Path ".venv") -and (-not (Test-Path $pythonVenv))) {
    Escrever ""
    Escrever "A pasta .venv existente nao e de Windows (sem Scripts\python.exe): sera apagada."
    Remove-Item -Recurse -Force ".venv" -ErrorAction Continue
    if (Test-Path ".venv") {
        Escrever "ERRO: nao foi possivel apagar a pasta .venv. Apague-a a mao e rode de novo."
        Escrever "FIM (com erro)"
        exit 1
    }
}
if (-not (Test-Path $pythonVenv)) {
    Executar "Criando o ambiente virtual" { & $achado.Caminho -m venv .venv }
}
if (-not (Test-Path $pythonVenv)) {
    Escrever "ERRO: o ambiente virtual nao foi criado."
    Escrever "FIM (com erro)"
    exit 1
}

Executar "Instalando as dependencias" { & $pythonVenv -m pip install --disable-pip-version-check --progress-bar off -r requirements.txt }
Executar "Testes automatizados" { & $pythonVenv -m pytest testes -q -p no:cacheprovider }

Escrever ""
Escrever "=== NVDA e DLL"
$nvdaExe = @("$env:ProgramFiles\NVDA\nvda.exe", "${env:ProgramFiles(x86)}\NVDA\nvda.exe") | Where-Object { Test-Path $_ }
if ($nvdaExe) {
    Escrever ("NVDA instalado em: " + ($nvdaExe -join "; "))
} else {
    Escrever "NVDA instalado: nao achei nas pastas padrao (pode ser a versao portatil)."
}
$processo = Get-Process nvda -ErrorAction SilentlyContinue
if ($processo) {
    Escrever ("NVDA em execucao: sim (processo " + $processo[0].Id + ")")
} else {
    Escrever "NVDA em execucao: nao"
}
$dlls = Get-ChildItem -Path (Join-Path $PSScriptRoot "bibliotecas") -Filter "nvdaControllerClient.dll" -Recurse -ErrorAction SilentlyContinue
if ($dlls) {
    foreach ($d in $dlls) {
        Escrever ("DLL encontrada: " + $d.FullName + " (" + $d.Length + " bytes, arquitetura " + (ArquiteturaDaDll $d.FullName) + ")")
    }
} else {
    Escrever "DLL nvdaControllerClient.dll: nao encontrada na pasta bibliotecas."
}

if ($dlls -and $processo) {
    Executar "Conferindo a conversa com o NVDA" { & $pythonVenv -c "from analisador.nvda import criar_falador; f = criar_falador('nvda'); f.verificar(); print('O NVDA respondeu ao teste.')" }
    if ($Falar) {
        Executar "Fala de teste" { & $pythonVenv -c "from analisador.nvda import criar_falador; f = criar_falador('nvda'); f.verificar(); f.falar('Teste de fala do analisador de codigo acessivel.'); print('Texto enviado ao NVDA.')" }
    }
} else {
    Escrever "Teste com o NVDA pulado: precisa da DLL em bibliotecas e do NVDA aberto."
}

Escrever ""
Escrever ("FIM. Registro salvo em: " + $log)

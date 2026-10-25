[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9_-]+$')]
    [string]$SshAlias = 's01',
    [ValidateSet('In_Progress')]
    [string]$ShareName = 'In_Progress'
)
$ErrorActionPreference = 'Stop'
$Utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8

# This launcher stays next to other source ZIPs in _forprint_automation/input.
# The server is authoritative; this client file is disposable/rebuildable.
$InputDirectory = $PSScriptRoot
$Workspace = Split-Path -Parent $InputDirectory
if ((Split-Path -Leaf $InputDirectory) -cne 'input' -or
    (Split-Path -Leaf $Workspace) -cne '_forprint_automation') {
    throw 'Launcher must be installed in _forprint_automation\input.'
}
$UncPattern = '^\\\\[^\\]+\\' + [regex]::Escape($ShareName) + '\\'
$Match = [regex]::Match($Workspace, $UncPattern,
    [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
if (-not $Match.Success) {
    throw 'Run the launcher from its original SMB UNC path, not a mapped drive.'
}
$Relative = $Workspace.Substring($Match.Length).Replace([char]92, '/')
if ($Relative.Split('/').Count -ne 2 -or
    -not $Relative.EndsWith('/_forprint_automation')) {
    throw 'Client workspace has unexpected directory depth.'
}
$Encoded = [Convert]::ToBase64String(
    [System.Text.Encoding]::UTF8.GetBytes($Relative)
).TrimEnd('=').Replace('+','-').Replace('/','_')

$Repository = '/srv/software_development/forprint-project/forprint_graphic_design_lab'
$Remote = "cd $Repository && make gc25-illustrator-queue-check PYTHON=.venv_gdl/bin/python SHARE=$ShareName WORKSPACE_RELATIVE_B64=$Encoded"
Write-Host 'GC25_ILLUSTRATOR_BRANCH=READ_ONLY_PREFLIGHT'
Write-Host 'PDF_LAUNCHER_UNCHANGED=true'
Write-Host 'CLIENT_SOURCE_WRITES=false'
$OldPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & ssh.exe -o BatchMode=yes -o ConnectTimeout=10 $SshAlias $Remote 2>&1 |
        ForEach-Object { Write-Host ([string]$_) }
    $Code = $LASTEXITCODE
}
finally { $ErrorActionPreference = $OldPreference }
if ($Code -ne 0) {
    throw "GC25 Illustrator preflight was blocked by server (exit $Code)."
}
Write-Host 'GC25_ILLUSTRATOR_BRANCH=PREFLIGHT_COMPLETE'
Write-Host 'NATIVE_ILLUSTRATOR_RENDER_NOT_YET_ENABLED=true'

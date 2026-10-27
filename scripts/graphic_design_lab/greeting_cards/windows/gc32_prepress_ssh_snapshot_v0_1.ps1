# GC32 read-only PREPRESS inventory, executed via versioned Worker/ script.
# The server pins and verifies this script by SHA256 before EVERY execution.
param([Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$ClientBase64)
# Does not create files or write to SMB; prints one JSON payload to standard output.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
if ($env:COMPUTERNAME -ine 'PREPRESS' -or $env:USERNAME -ine 'Work') { throw 'GC32_SSH_WRONG_IDENTITY' }
if (-not (Test-Path -LiteralPath $Root -PathType Container)) { throw 'GC32_SSH_ROOT_MISSING' }
$Client = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($ClientBase64))
if ([string]::IsNullOrWhiteSpace($Client) -or $Client -in @('.','..') -or $Client.IndexOfAny([char[]]@('/','\')) -ge 0) { throw 'GC32_SSH_CLIENT_INVALID' }
$Items = [Collections.Generic.List[object]]::new()
$Seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$Partial = $false
function Add-Node([string]$rel) {
    if ($Items.Count -ge 450) { $script:Partial = $true; return }
    if (-not $Seen.Add($rel)) { return }
    $full = Join-Path $Root $rel
    $obj = Get-Item -LiteralPath $full -Force -ErrorAction SilentlyContinue
    if ($null -eq $obj) { return }
    if ($obj.Attributes -band [IO.FileAttributes]::ReparsePoint) { return }
    if (-not ($obj.PSIsContainer -or $obj -is [IO.FileInfo])) { return }
    $record = [ordered]@{
        path=($rel -replace '\\','/'); kind=$(if($obj.PSIsContainer){'dir'}else{'file'})
        size_bytes=$(if($obj.PSIsContainer){$null}else{[long]$obj.Length}); sha256=$null
    }
    if (-not $obj.PSIsContainer -and $obj.Length -le 2000000 -and
        $obj.Extension -in @('.ps1','.cmd','.json','.svg','.png')) {
        $record.sha256 = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $Items.Add([pscustomobject]$record)
}
foreach ($top in @('cache','config','jobs','logs','runtime','Worker')) { Add-Node $top }
foreach ($rel in @('Worker\gc32_prepress_worker_v0_1.ps1','config\worker_config.json')) { Add-Node $rel }
# Show names of previous GC*/W* experimental branches; never classify them as disposable.
$jobs = Join-Path $Root 'jobs'
if (Test-Path -LiteralPath $jobs -PathType Container) {
    Get-ChildItem -LiteralPath $jobs -Directory -Force -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -match '^gdl-(gc|w)[A-Za-z0-9_-]+$' -and -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
      Select-Object -First 90 | ForEach-Object { Add-Node ('jobs\' + $_.Name) }
}
# Only scan global worker/cache and THIS customer's job paths; exclude all other clients.
$segments = @('Worker','cache\shared','config')
$segments += ('jobs\' + $Client)
$segments += ('cache\clients\' + $Client)
foreach ($segment in $segments) {
    Add-Node $segment
    $folder = Join-Path $Root $segment
    if (-not (Test-Path -LiteralPath $folder -PathType Container)) { continue }
    Get-ChildItem -LiteralPath $folder -Recurse -Depth 3 -Force -ErrorAction SilentlyContinue |
       Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
       Select-Object -First 150 | ForEach-Object {
           $rel = $_.FullName.Substring($Root.Length).TrimStart([char[]]@('\','/'))
           Add-Node $rel
       }
}
$doc = [ordered]@{
    schema_version='forprint_gdl_gc32_prepress_tree_snapshot_v0_1'
    machine=$env:COMPUTERNAME.ToUpperInvariant(); user=$env:USERNAME
    client=$Client; root=$Root; captured_utc=[DateTime]::UtcNow.ToString('o')
    entries=@($Items.ToArray()); operator_export_only=$true
    production_authority=$false; scan_truncated=$Partial
}
$json = ConvertTo-Json -InputObject $doc -Depth 8 -Compress
if ([Text.Encoding]::UTF8.GetByteCount($json) -ge 512000) { throw 'GC32_SSH_JSON_TOO_LARGE' }
[Console]::Out.WriteLine('GC32_SNAPSHOT_JSON=' + $json)

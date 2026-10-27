# GC30 r002C exact DEG local-only stage. Windows PowerShell 5.1.
# No SMB, no Illustrator, no worker registration, no writes outside jobs/<ticket>.
[CmdletBinding()]
param(
  [ValidateSet('Check','Stage','Verify')][string]$Mode = 'Check',
  [switch]$ConfirmStage
)
$ErrorActionPreference = 'Stop'
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$TicketId = 'gdl_gc_deg_20261011__34b9b61741d5ca'
$JobRoot = Join-Path (Join-Path $Root 'jobs') $TicketId
$ZipPath = Join-Path $JobRoot 'payload.zip'
$ScriptPath = Join-Path $JobRoot 'gc30_exact_ticket_stage_r002c.ps1'
$StageDir = Join-Path $JobRoot 'stage'
$ReceiptPath = Join-Path $JobRoot 'stage_receipt_r002c.json'
$ExpectedZipHash = 'd3b9329a51272fb195718d124d465da41c4002816c6d6b07c4c66c01e8982ca7'

function Require([bool]$Condition, [string]$Reason) {
  if (-not $Condition) { throw ('GC30_C_BLOCKED_' + $Reason) }
}
function SafeDirectory([string]$Path) {
  Require (Test-Path -LiteralPath $Path -PathType Container) 'DIRECTORY_MISSING'
  $Item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
  Require (-not ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'DIRECTORY_REPARSE_POINT'
}
function ShaFile([string]$Path) {
  (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
}
function ShaStream($Stream) {
  $Hash = [Security.Cryptography.SHA256]::Create()
  try { ([BitConverter]::ToString($Hash.ComputeHash($Stream))).Replace('-', '').ToLowerInvariant() }
  finally { $Hash.Dispose() }
}
function ReadZipText($Entry) {
  Require ($Entry.Length -le 262144) 'JSON_TOO_LARGE'
  $s = $Entry.Open()
  try {
    $reader = [IO.StreamReader]::new($s, [Text.UTF8Encoding]::new($false), $true)
    try { $reader.ReadToEnd() }
    finally { $reader.Dispose() }
  }
  finally { $s.Dispose() }
}

Require ($env:COMPUTERNAME -ieq 'PREPRESS') 'WRONG_HOST'
Require ([Environment]::UserName -ieq 'Work') 'WRONG_USER'
Require (($Mode -eq 'Stage') -eq [bool]$ConfirmStage) 'CONFIRMATION_MISMATCH'
SafeDirectory $Root
SafeDirectory (Join-Path $Root 'jobs')
SafeDirectory $JobRoot
Require (Test-Path -LiteralPath $ZipPath -PathType Leaf) 'PAYLOAD_MISSING'
Require (Test-Path -LiteralPath $ScriptPath -PathType Leaf) 'SCRIPT_MISSING'
Require ((ShaFile $ZipPath) -ceq $ExpectedZipHash) 'ZIP_HASH_DRIFT'
foreach ($f in @($ZipPath,$ScriptPath)) {
  $i = Get-Item -LiteralPath $f -Force
  Require (-not ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'FILE_REPARSE_POINT'
}
$children = @(Get-ChildItem -LiteralPath $JobRoot -Force)
$names = @($children | ForEach-Object { $_.Name })
if ($Mode -eq 'Verify') {
  Require ($names.Count -eq 4) 'UNEXPECTED_ROOT_FILES'
  foreach($n in @('payload.zip','gc30_exact_ticket_stage_r002c.ps1','stage','stage_receipt_r002c.json')) { Require ($names -ccontains $n) 'MISSING_EXPECTED_ENTRY' }
  SafeDirectory $StageDir
  Require (Test-Path -LiteralPath $ReceiptPath -PathType Leaf) 'RECEIPT_MISSING'
} else {
  Require ($names.Count -eq 2) 'UNEXPECTED_ROOT_FILES'
  foreach($n in @('payload.zip','gc30_exact_ticket_stage_r002c.ps1')) { Require ($names -ccontains $n) 'MISSING_EXPECTED_ENTRY' }
  Require (-not (Test-Path -LiteralPath $StageDir)) 'STAGE_ALREADY_EXISTS'
  Require (-not (Test-Path -LiteralPath $ReceiptPath)) 'RECEIPT_ALREADY_EXISTS'
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
  $entries = @($archive.Entries)
  Require ($entries.Count -eq 16) 'ZIP_ENTRY_COUNT'
  $index = @{}
  foreach($e in $entries) {
    $n = $e.FullName
    Require (-not $index.ContainsKey($n)) 'DUPLICATE_ZIP_ENTRY'
    Require ($n -cmatch '^(ticket\.json|scene_manifest\.json|run_in_illustrator\.jsx|offline_payload_manifest\.json|assets/p[0-9]{2}_[a-z0-9_]+\.(png|svg|eps))$') 'UNSAFE_ZIP_ENTRY'
    Require ($e.Length -le 41943040) 'ENTRY_TOO_LARGE'
    $index[$n] = $e
  }
  $metadata = ReadZipText $index['offline_payload_manifest.json'] | ConvertFrom-Json -ErrorAction Stop
  Require ($metadata.ticket_id -ceq $TicketId) 'MANIFEST_TICKET_DRIFT'
  Require ($metadata.job_id -ceq 'gdl_gc_deg_20261011') 'MANIFEST_JOB_DRIFT'
  Require ($metadata.target_root -ceq $Root) 'MANIFEST_ROOT_DRIFT'
  Require ($metadata.target_subtree -ceq ('jobs/'+$TicketId)) 'MANIFEST_SUBTREE_DRIFT'
  Require ($metadata.worker_machine -ceq 'PREPRESS') 'WORKER_DRIFT'
  Require ($metadata.worker_user -ceq 'Work') 'USER_DRIFT'
  Require ($metadata.assets_count -eq 12) 'ASSET_COUNT_DRIFT'
  Require ($metadata.production_ready -eq $false -and $metadata.illustrator_launch -eq $false -and $metadata.automatic_accept -eq $false) 'UNSAFE_AUTHORITY'
  $keys = @($metadata.source_file_sha256.PSObject.Properties | ForEach-Object { $_.Name })
  Require ($keys.Count -eq 15) 'MANIFEST_MEMBER_COUNT'
  Require ($index.Count -eq ($keys.Count + 1)) 'ZIP_MANIFEST_SET_MISMATCH'
  $totalBytes = [int64]0
  foreach($n in $keys) {
    Require ($index.ContainsKey($n)) 'MANIFEST_FILE_MISSING'
    $entry = $index[$n]
    $totalBytes += $entry.Length
    Require ($totalBytes -le 157286400) 'ZIP_EXPANSION_TOO_LARGE'
    $reader = $entry.Open()
    try { $got = ShaStream $reader }
    finally { $reader.Dispose() }
    # PS property access with slash/dot names must use the property bag.
    $want = [string]$metadata.source_file_sha256.PSObject.Properties[$n].Value
    Require ($want -cmatch '^[a-f0-9]{64}$' -and $got -ceq $want) 'ZIP_MEMBER_SHA_DRIFT'
  }
  $ticket = ReadZipText $index['ticket.json'] | ConvertFrom-Json -ErrorAction Stop
  $scene = ReadZipText $index['scene_manifest.json'] | ConvertFrom-Json -ErrorAction Stop
  Require ($ticket.ticket_id -ceq $TicketId -and $ticket.worker_id -ceq 'illustrator-primary') 'TICKET_DRIFT'
  Require ($ticket.production_ready -eq $false -and $ticket.review_only -eq $true) 'TICKET_AUTHORITY'
  Require ($scene.pages -eq 4 -and $scene.production_ready -eq $false) 'SCENE_DRIFT'
  Require ($scene.job_id -ceq 'gdl_gc_deg_20261011') 'SCENE_JOB_DRIFT'
  if ($Mode -eq 'Check') {
    Write-Output ('GC30_R002C_LOCAL_PREFLIGHT=PASS TICKET='+$TicketId+' FILES=16 ASSETS=12')
    Write-Output 'GC30_R002C_STAGE=NOT_EXECUTED'
    return
  }
  if ($Mode -eq 'Stage') {
    # Fail-closed, create-only. A partial stage is never overwritten or deleted automatically.
    $null = New-Item -ItemType Directory -Path $StageDir -ErrorAction Stop
    foreach($e in $entries) {
      $parts = $e.FullName.Split('/')
      $dest = $StageDir
      foreach($segment in $parts) { $dest = Join-Path $dest $segment }
      $parent = Split-Path -Parent $dest
      if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $parent -ErrorAction Stop
      }
      $sourceStream = $e.Open()
      try {
        $targetStream = [IO.FileStream]::new($dest, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $sourceStream.CopyTo($targetStream) }
        finally { $targetStream.Dispose() }
      }
      finally { $sourceStream.Dispose() }
    }
  }
  # Independent verification of the local files (both after Stage and on Verify).
  $allStaged = @(Get-ChildItem -LiteralPath $StageDir -Recurse -Force)
  foreach($i in $allStaged) { Require (-not ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'STAGE_REPARSE_POINT' }
  $found = @($allStaged | Where-Object { -not $_.PSIsContainer })
  Require ($found.Count -eq 16) 'STAGE_FILE_COUNT_DRIFT'
  foreach($e in $entries) {
    $p = $StageDir
    foreach($segment in $e.FullName.Split('/')) { $p = Join-Path $p $segment }
    Require (Test-Path -LiteralPath $p -PathType Leaf) 'STAGED_FILE_MISSING'
    $expected = if($e.FullName -eq 'offline_payload_manifest.json') { $null } else { [string]$metadata.source_file_sha256.PSObject.Properties[$e.FullName].Value }
    if ($null -ne $expected) { Require ((ShaFile $p) -ceq $expected) 'STAGED_FILE_SHA_DRIFT' }
    else {
      $str=$e.Open()
      try { $manifestSha=ShaStream $str }
      finally { $str.Dispose() }
      Require ((ShaFile $p) -ceq $manifestSha) 'STAGED_MANIFEST_HASH_DRIFT'
    }
  }
  $receipt = [ordered]@{
    schema_version = 'forprint_gc30_r002c_local_stage_receipt_v0_1'
    ticket_id = $TicketId
    payload_sha256 = $ExpectedZipHash
    zip_members = 16
    assets = 12
    files_verified = 16
    stage_relpath = 'jobs/'+$TicketId+'/stage'
    state = 'STAGED_HASH_VERIFIED_NON_AUTHORIZING'
    stage_host = $env:COMPUTERNAME
    automatic_accept = $false
    illustrator_launched = $false
    native_ai_reopen_attested = $false
    visual_approved = $false
    production_ready = $false
  }
  if ($Mode -eq 'Stage') {
    $encoded = $receipt | ConvertTo-Json -Depth 4
    $encoding = New-Object System.Text.UTF8Encoding($false)
    $data = $encoding.GetBytes($encoded+"`n")
    $receiptStream = [IO.FileStream]::new($ReceiptPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $receiptStream.Write($data,0,$data.Length); $receiptStream.Flush($true) }
    finally { $receiptStream.Dispose() }
  } else {
    $saved = Get-Content -LiteralPath $ReceiptPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
    Require ($saved.ticket_id -ceq $TicketId -and $saved.payload_sha256 -ceq $ExpectedZipHash) 'RECEIPT_IDENTITY_DRIFT'
    Require ($saved.state -ceq 'STAGED_HASH_VERIFIED_NON_AUTHORIZING' -and $saved.production_ready -eq $false) 'RECEIPT_AUTHORITY_DRIFT'
  }
  Write-Output ('GC30_R002C_STAGE=PASS_NON_AUTHORIZING FILES=16 ASSETS=12 TICKET='+$TicketId)
  Write-Output 'GC30_R002C_ILLUSTRATOR=NOT_LAUNCHED'
}
finally { $archive.Dispose() }

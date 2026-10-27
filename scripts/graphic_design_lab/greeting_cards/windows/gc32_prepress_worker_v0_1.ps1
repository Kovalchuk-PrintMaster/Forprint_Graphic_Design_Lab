[CmdletBinding()]
param(
  [ValidateSet('Register','Check','PollOnce','ReturnResults')][string]$Mode='Check',
  [string]$ShareRoot='',
  [string]$ClientFolder='',
  [string]$RunName='',
  [switch]$ConfirmRegister
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$OutputEncoding=[Console]::OutputEncoding
$WorkerId='illustrator-primary'
# Worker and caches ALWAYS live below the one existing automation root.
# This file must be located in <AUTOMATION_ROOT>\Worker\.
$Base=Split-Path -Parent $PSScriptRoot
$WorkerHome=Join-Path $Base 'Worker'
$ConfigPath=Join-Path (Join-Path $Base 'config') 'worker_config.json'
$ThisName='gc32_prepress_worker_v0_1.ps1'
function Need([bool]$ok,[string]$code){if(-not $ok){throw $code}}
function SafeDirectory([string]$p){
 if(-not (Test-Path -LiteralPath $p -PathType Container)){return $false}
 return -not [bool]((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)
}
function FileOK([string]$p){
 if(-not (Test-Path -LiteralPath $p -PathType Leaf)){return $false}
 return -not [bool]((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)
}
function Sha([string]$p){ (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() }
function SaveExclusive([string]$path,[object]$record){
 Need (-not (Test-Path -LiteralPath $path)) 'GC30_RECEIPT_EXISTS_RECONCILE'
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($record|ConvertTo-Json -Depth 12)+"`n")
 $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
function ValidName([string]$name){ $name -cmatch '^gdl_gc_[a-z0-9_]+__[a-f0-9]{14}$' }
function AcceptedSha([string]$v){ $v -cmatch '^[a-f0-9]{64}$' }
function Cached([string]$remote,[string]$want,[string]$cacheDir,[string]$extension){
 Need (FileOK $remote) 'GC30_RESOURCE_SOURCE_MISSING'
 Need (AcceptedSha $want) 'GC30_RESOURCE_SHA_INVALID'
 if(-not (Test-Path -LiteralPath $cacheDir)){New-Item -ItemType Directory -Path $cacheDir -Force|Out-Null}
 Need (SafeDirectory $cacheDir) 'GC30_RESOURCE_CACHE_UNSAFE'
 $local=Join-Path $cacheDir ($want+$extension)
 if(Test-Path -LiteralPath $local){
   Need (FileOK $local) 'GC30_LOCAL_CACHE_NOT_REGULAR'
   if((Sha $local) -ceq $want){return $local}
   $quarantine=$local+'.damaged.'+[guid]::NewGuid().ToString('N')
   Move-Item -LiteralPath $local -Destination $quarantine -ErrorAction Stop
   Write-Host 'GC30_CACHE_CORRUPT_QUARANTINED'
 }
 $tmp=$local+'.incoming.'+[guid]::NewGuid().ToString('N')
 Copy-Item -LiteralPath $remote -Destination $tmp -ErrorAction Stop
 Need ((Sha $tmp) -ceq $want) 'GC30_REMOTE_SOURCE_HASH_MISMATCH'
 Move-Item -LiteralPath $tmp -Destination $local -ErrorAction Stop
 Need ((Sha $local) -ceq $want) 'GC30_CACHE_INSTALL_HASH_MISMATCH'
 Write-Host 'GC30_CACHE=RESTORED_ONE_ASSET'
 return $local
}
function BaseConfig(){
 Need (FileOK $ConfigPath) 'GC30_WORKER_NOT_REGISTERED'
 $c=Get-Content -LiteralPath $ConfigPath -Encoding UTF8 -Raw|ConvertFrom-Json
 Need ($c.schema_version -ceq 'forprint_gc30_worker_config_v0_1') 'GC30_CONFIG_SCHEMA_INVALID'
 Need ($c.worker_id -ceq $WorkerId) 'GC30_WRONG_WORKER_ID'
 Need ($c.computer_name -ceq $env:COMPUTERNAME) 'GC30_WRONG_WINDOWS_COMPUTER'
 Need ($c.windows_user -ceq [Environment]::UserName) 'GC30_WRONG_WINDOWS_USER'
 Need ($c.worker_root -ceq $Base) 'GC32_WORKER_ROOT_CHANGED'
 Need ($c.share_root -match '^\\\\[^\\]+\\In_Progress$') 'GC30_SHARE_ROOT_UNSAFE'
 $self=Join-Path $WorkerHome $ThisName
 Need ((FileOK $self) -and ((Sha $self) -ceq $c.worker_script_sha256)) 'GC30_WORKER_SCRIPT_CHANGED'
 Need ((Resolve-Path -LiteralPath $PSCommandPath).Path -ceq (Resolve-Path -LiteralPath $self).Path) 'GC30_RUN_LOCAL_INSTALLED_WORKER_ONLY'
 return $c
}
function ValidateTicket([string]$ws,[object]$t){
 Need ($t.schema_version -ceq 'forprint_gdl_gc30_dispatch_ticket_v0_1') 'GC30_TICKET_SCHEMA_INVALID'
 Need ($t.worker_id -ceq $WorkerId) 'GC30_TICKET_WRONG_WORKER'
 Need ($t.worker_machine -ceq $env:COMPUTERNAME) 'GC30_TICKET_WRONG_WINDOWS_MACHINE'
 Need ($t.worker_user -ceq [Environment]::UserName) 'GC30_TICKET_WRONG_WINDOWS_USER'
 Need ((ValidName $t.ticket_id) -and $t.status -ceq 'QUEUED') 'GC30_TICKET_ID_INVALID'
 Need ($t.run_relative -ceq ('template_studio/native_runs/'+$t.ticket_id)) 'GC30_RUN_RELATIVE_INVALID'
 Need ($t.review_only -eq $true -and $t.production_ready -eq $false) 'GC30_TICKET_AUTHORITY_INVALID'
 Need ((AcceptedSha $t.jsx_sha256) -and (AcceptedSha $t.scene_manifest_sha256)) 'GC30_TICKET_HASH_INVALID'
 $run=Join-Path $ws ($t.run_relative.Replace('/','\'))
 Need (SafeDirectory $run) 'GC30_REMOTE_RUN_MISSING'
 $scenePath=Join-Path $run 'scene_manifest.json'
 $jsxPath=Join-Path $run 'run_in_illustrator.jsx'
 Need ((FileOK $scenePath) -and ((Sha $scenePath) -ceq $t.scene_manifest_sha256)) 'GC30_REMOTE_SCENE_HASH_INVALID'
 Need ((FileOK $jsxPath) -and ((Sha $jsxPath) -ceq $t.jsx_sha256)) 'GC30_REMOTE_JSX_HASH_INVALID'
 $scene=Get-Content -LiteralPath $scenePath -Encoding UTF8 -Raw|ConvertFrom-Json
 Need ($scene.schema_version -ceq 'gdl_gc29_native_scene_v0_1' -and $scene.pages -eq 4) 'GC30_SCENE_SCHEMA_INVALID'
 Need ($scene.production_ready -eq $false -and $scene.job_id -ceq $t.job_id) 'GC30_SCENE_SCOPE_INVALID'
 Need ($scene.accepted_zip_sha256 -ceq $t.accepted_zip_sha256) 'GC30_INTAKE_IDENTITY_CHANGED'
 Need ($scene.jsx_sha256 -ceq $t.jsx_sha256) 'GC30_JSX_BINDING_CHANGED'
 Need ((SafeDirectory (Join-Path $run 'assets')) -and $null -ne $scene.asset_sha256) 'GC30_ASSETS_MISSING'
 foreach($p in $scene.asset_sha256.PSObject.Properties){
   Need ($p.Name -cmatch '^[A-Za-z0-9_.-]+\.(png|svg|eps)$') 'GC30_ASSET_FILENAME_INVALID'
   $tp=$t.asset_sha256.PSObject.Properties[$p.Name]
   Need ($null -ne $tp -and [string]$tp.Value -ceq [string]$p.Value) 'GC30_TICKET_ASSET_BINDING_INVALID'
 }
 return [PSCustomObject]@{Run=$run;Scene=$scene;Jsx=$jsxPath;Manifest=$scenePath}
}
function StageTicket([string]$ws,[object]$t,[string]$client,[string]$statusDir){
 $v=ValidateTicket $ws $t
 $pipeline=Join-Path (Join-Path (Join-Path $Base 'jobs') $client) 'GreetingCards'
 $local=Join-Path $pipeline $t.ticket_id
 Need (-not (Test-Path -LiteralPath $local)) 'GC30_LOCAL_JOB_ALREADY_EXISTS_RECONCILE'
 New-Item -ItemType Directory -Path (Join-Path $local 'assets') -Force -ErrorAction Stop | Out-Null
 $assetsDir=Join-Path $local 'assets'
 Copy-Item -LiteralPath $v.Jsx -Destination (Join-Path $local 'run_in_illustrator.jsx')
 Copy-Item -LiteralPath $v.Manifest -Destination (Join-Path $local 'scene_manifest.json')
 Need ((Sha (Join-Path $local 'run_in_illustrator.jsx')) -ceq $t.jsx_sha256) 'GC30_LOCAL_JSX_HASH_INVALID'
 foreach($p in $v.Scene.asset_sha256.PSObject.Properties){
   $n=[string]$p.Name;$sha=[string]$p.Value;$ext=[IO.Path]::GetExtension($n)
   # Standard resources share an immutable SHA cache; intake-specific assets remain client-bound.
   # Only explicitly-known GDL library filenames use shared SHA cache.
   $libraryNames=@('p01_paper.png','p01_frame.png','p01_logo.png',
     'p02_locked.png','p02_watermark.png','p03_paper.png','p03_flowers.png',
     'p03_frame.png','p04_paper.png','p04_watermark.png','p04_frame.png',
     'p04_grigo_signature.svg','p04_grigo_signature.png','p04_herasymenko_signature.png')
   $cacheRoot=if($libraryNames -ccontains $n){
     Join-Path $Base 'cache\shared'
   }else{
     Join-Path (Join-Path $Base 'cache\clients') $client
   }
   $stored=Cached (Join-Path (Join-Path $v.Run 'assets') $n) $sha $cacheRoot $ext
   $target=Join-Path $assetsDir $n
   try{New-Item -ItemType HardLink -Path $target -Target $stored -ErrorAction Stop|Out-Null}
   catch{Copy-Item -LiteralPath $stored -Destination $target -ErrorAction Stop}
   Need ((Sha $target) -ceq $sha) 'GC30_LOCAL_JOB_ASSET_HASH_INVALID'
 }
 $e=@($v.Scene.asset_sha256.PSObject.Properties).Count
 $status=[ordered]@{schema_version='forprint_gdl_gc30_worker_status_v0_1';ticket_id=$t.ticket_id;worker_id=$WorkerId;
    computer_name=$env:COMPUTERNAME;state='STAGED_FOR_ILLUSTRATOR';assets_verified=$e;
    execution_started=$false;local_path=$local;production_ready=$false;client_published=$false}
 SaveExclusive (Join-Path $statusDir ($t.ticket_id+'.stage.json')) $status
 Write-Host ('GC30_JOB_STAGE=PASS JOB='+$t.ticket_id+' CACHE_VERIFIED='+$e)
 Write-Host ('GC30_ILLUSTRATOR_LOCAL_JSX='+ (Join-Path $local 'run_in_illustrator.jsx'))
 Write-Host 'GC30_NATIVE_SVG_BLOCKER=REQUIRES_RENDERER_REPAIR_BEFORE_FULL_AUTO_EXECUTION'
}
function ReturnResults([string]$cshare,[string]$client,[string]$run){
 Need (ValidName $run) 'GC30_RUN_NAME_INVALID'
 $ws=Join-Path (Join-Path $cshare $client) '_forprint_automation'
 Need (SafeDirectory $ws) 'GC30_WORKSPACE_MISSING'
 $local=Join-Path (Join-Path (Join-Path $Base 'jobs') $client) ('GreetingCards\'+$run)
 Need (SafeDirectory $local) 'GC30_LOCAL_RUN_MISSING'
 $out=Join-Path $local 'out'
 Need (SafeDirectory $out) 'GC30_ILLUSTRATOR_OUTPUT_MISSING'
 $resPath=Join-Path $out 'result.json'
 Need (FileOK $resPath) 'GC30_RESULT_JSON_MISSING'
 $res=Get-Content -LiteralPath $resPath -Raw -Encoding UTF8 | ConvertFrom-Json
 if($res.state -cne 'AI_REOPENED_VISUAL_REVIEW_REQUIRED'){
   Write-Host ('GC30_RENDER_BLOCKED='+$res.error)
   throw 'GC30_ILLUSTRATOR_REVIEW_REQUIRED_NOT_PUBLISHABLE'
 }
 Need ($res.pages -eq 4 -and $res.production_ready -eq $false) 'GC30_RESULT_AUTHORITY_CHANGED'
 $names=@('design.ai','review.pdf','preview_p01.png','preview_p02.png','preview_p03.png','preview_p04.png','result.json')
 foreach($n in $names){$p=Join-Path $out $n;Need ((FileOK $p) -and (Get-Item $p).Length -gt 100) ('GC30_OUTPUT_MISSING_'+$n)}
 $destRoot=Join-Path $ws 'output\illustrator_review'
 if(-not (Test-Path -LiteralPath $destRoot)){New-Item -ItemType Directory -Path $destRoot -Force|Out-Null}
 Need (SafeDirectory $destRoot) 'GC30_OUTPUT_ROOT_UNSAFE'
 $dest=Join-Path $destRoot $run
 Need (-not (Test-Path -LiteralPath $dest)) 'GC30_REVIEW_DEST_EXISTS_NO_OVERWRITE'
 New-Item -ItemType Directory -Path $dest -ErrorAction Stop | Out-Null
 foreach($n in $names){$source=Join-Path $out $n;$target=Join-Path $dest $n;Copy-Item -LiteralPath $source -Destination $target -ErrorAction Stop;Need ((Sha $source) -ceq (Sha $target)) ('GC30_WRITEBACK_HASH_FAIL_'+$n)}
 Write-Host ('GC30_REVIEW_RETURN=PASS PATH='+$dest)
 Write-Host 'PRODUCTION_READY=false CLIENT_PUBLISHED=false'
}
try{
 if($Mode -ceq 'Register'){
   Need ($ConfirmRegister.IsPresent) 'GC30_EXPLICIT_REGISTRATION_REQUIRED'
   Need ($ShareRoot -match '^\\\\[^\\]+\\In_Progress$') 'GC30_SHARE_ROOT_INVALID'
   Need (SafeDirectory $ShareRoot) 'GC30_SHARE_NOT_ACCESSIBLE'
   # Fail closed: no registration from TEMP, LOCALAPPDATA, or SMB.
   Need ($Base -match '^[A-Za-z]:\\' -and -not $Base.StartsWith('\\')) 'GC32_LOCAL_FIXED_DRIVE_REQUIRED'
   Need ($PSScriptRoot -ceq (Join-Path $Base 'Worker')) 'GC32_SCRIPT_MUST_BE_IN_WORKER_SUBDIR'
   Need (SafeDirectory $Base) 'GC32_AUTOMATION_ROOT_MISSING'
   Need (SafeDirectory $WorkerHome) 'GC32_WORKER_DIR_MISSING'
   foreach($d in @('cache','config','jobs','logs','runtime')){
     Need (SafeDirectory (Join-Path $Base $d)) ('GC32_EXISTING_ROOT_DIRECTORY_MISSING_'+$d)
   }
   Need (-not (Test-Path -LiteralPath (Join-Path $WorkerHome 'worker_config.json'))) 'GC32_LEGACY_CONFIG_RECONCILE'
   $target=Join-Path $WorkerHome $ThisName
   Need (FileOK $target) 'GC32_WORKER_FILE_MISSING'
   Need ((Resolve-Path -LiteralPath $PSCommandPath).Path -ceq (Resolve-Path -LiteralPath $target).Path) 'GC32_REGISTER_IN_PLACE_ONLY'
   Need (-not (Test-Path -LiteralPath $ConfigPath)) 'GC32_WORKER_ALREADY_REGISTERED_NO_OVERWRITE'
   $config=[ordered]@{schema_version='forprint_gc30_worker_config_v0_1';worker_id=$WorkerId;
     computer_name=$env:COMPUTERNAME;windows_user=[Environment]::UserName;
     share_root=$ShareRoot;worker_root=$Base;worker_script_sha256=(Sha $target);runtime_pdf_dependency=$false}
   SaveExclusive $ConfigPath $config
   Write-Host ('GC30_WORKER_REGISTERED=PASS MACHINE='+$env:COMPUTERNAME+' USER='+[Environment]::UserName)
   Write-Host ('GC32_WORKER_LOCAL_SCRIPT='+$target)
   exit 0
 }
 $c=BaseConfig
 $share=[string]$c.share_root
 Need (SafeDirectory $share) 'GC30_SHARE_UNAVAILABLE'
 if($Mode -ceq 'Check'){
   Write-Host ('GC30_DEDICATED_WORKER=CHECK_PASS MACHINE='+$env:COMPUTERNAME+' WORKER='+$WorkerId)
   Write-Host ('GC32_SINGLE_AUTOMATION_ROOT='+$Base)
   exit 0
 }
 if($Mode -ceq 'ReturnResults'){
   Need ($ClientFolder -ne '' -and $ClientFolder.IndexOfAny([char[]]@('/','\')) -lt 0) 'GC30_CLIENT_FOLDER_INVALID'
   ReturnResults $share $ClientFolder $RunName
   exit 0
 }
 $total=0
 foreach($client in @(Get-ChildItem -LiteralPath $share -Directory -Force)){
   if($client.Attributes -band [IO.FileAttributes]::ReparsePoint){continue}
   $ws=Join-Path $client.FullName '_forprint_automation'
   if(-not (SafeDirectory $ws)){continue}
   $queue=Join-Path $ws 'template_studio\dispatch\queued'
   if(-not (SafeDirectory $queue)){continue}
   $statusDir=Join-Path $ws 'template_studio\dispatch\status'
   if(-not (Test-Path -LiteralPath $statusDir)){New-Item -ItemType Directory -Path $statusDir -ErrorAction Stop|Out-Null}
   Need (SafeDirectory $statusDir) 'GC30_STATUS_DIR_UNSAFE'
   foreach($file in @(Get-ChildItem -LiteralPath $queue -File -Filter '*.json')){
     Need (FileOK $file.FullName) 'GC30_QUEUE_ITEM_UNSAFE'
     Need ((ValidName $file.BaseName) -and $file.Length -lt 128000) 'GC30_QUEUE_NAME_INVALID'
     $t=Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
     if($t.worker_id -cne $WorkerId){continue}
     if(Test-Path -LiteralPath (Join-Path $statusDir ($t.ticket_id+'.stage.json'))){continue}
     StageTicket $ws $t $client.Name $statusDir
     $total++
     # At most one fresh job per PollOnce until visual validation closes this pilot.
     Write-Host 'GC30_POLL_ONCE=STAGED_ONE_JOB'
     exit 0
   }
 }
 Write-Host 'GC30_POLL_ONCE=NO_NEW_JOBS'
 exit 0
}catch{
 Write-Host ('GC30_WORKER=BLOCKED reason='+$_.Exception.Message)
 Write-Host 'No automatic Illustrator invocation; existing runs and caches are preserved.'
 exit 2
}

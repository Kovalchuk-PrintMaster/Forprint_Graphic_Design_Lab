# GC21 one-use Task Scheduler action. Runs as PREPRESS\Work in the active GUI session.
param([Parameter(Mandatory=$true)][int]$ExpectedSessionId,
      [Parameter(Mandatory=$true)][string]$IllustratorExe)
$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'
$Root='D:\ForPrint_Automation\GraficsDesignLab\Automation'
$Attempt=Join-Path $Root 'jobs\gdl-gc21-card-001\a0001'
$Work=Join-Path $Attempt 'work'
$Export=Join-Path $Attempt 'export'
$Jsx=Join-Path $Work 'run_gc21_in_illustrator.jsx'
$Scene=Join-Path $Work 'scene_manifest.json'
$Claim=Join-Path $Work 'gc21_launch_claim.json'
$Result=Join-Path $Export 'gc21_worker_result.json'
$Partial=Join-Path $Work 'out'
$Final=Join-Path $Export 'gc21_native_artifacts'
$phase='INITIAL'; $errorCode='UNSTARTED'; $ok=$false; $exported=$false
$aiReopened=$false; $pidIllustrator=$null; $aiSha=$null; $aiBytes=0
function Fail([string]$code){throw ('GC21_RUNNER_BLOCKED:'+$code)}
function WriteOnce([string]$p,[string]$s){
  $b=[Text.UTF8Encoding]::new($false).GetBytes($s)
  $f=[IO.File]::Open($p,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try{$f.Write($b,0,$b.Length)}finally{$f.Dispose()}
}
try {
  $phase='IDENTITY'
  $session=[Diagnostics.Process]::GetCurrentProcess().SessionId
  if($env:COMPUTERNAME -ine 'PREPRESS' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){Fail 'HOST_IDENTITY_INVALID'}
  if($session -ne $ExpectedSessionId -or $session -le 0 -or -not [Environment]::UserInteractive){Fail 'NOT_IN_EXPECTED_GUI_SESSION'}
  $wp=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
  if($wp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){Fail 'ELEVATED_TOKEN_NOT_ALLOWED'}
  $qs=@(& quser.exe 2>&1 | ForEach-Object {[string]$_})
  if($LASTEXITCODE -ne 0){Fail 'QUSER_FAILED'}
  $active=$false
  foreach($line in $qs){
    $r=[regex]::Match($line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b')
    if($r.Success -and [int]$r.Groups[1].Value -eq $session){$active=$true}
  }
  if(-not $active){Fail 'SESSION_NOT_ACTIVE'}
  if(-not(Test-Path -LiteralPath $Jsx -PathType Leaf) -or -not(Test-Path -LiteralPath $Scene -PathType Leaf)){Fail 'INPUT_MISSING'}
  if(Test-Path -LiteralPath $Result){Fail 'RESULT_ALREADY_EXISTS'}
  if(Test-Path -LiteralPath $Final){Fail 'EXPORT_ALREADY_EXISTS'}
  if(Test-Path -LiteralPath $Partial){Fail 'PARTIAL_OUTPUT_ALREADY_EXISTS'}
  if(@(Get-Process Illustrator -ErrorAction SilentlyContinue).Count -ne 0){Fail 'ILLUSTRATOR_ALREADY_RUNNING'}
  $m=Get-Content -LiteralPath $Scene -Raw | ConvertFrom-Json
  if($m.pages -ne 4 -or $m.sender_variant -ne 'HERASYMENKO'){Fail 'SOURCE_SCOPE_MISMATCH'}
  if((Get-FileHash -LiteralPath $Jsx -Algorithm SHA256).Hash.ToLowerInvariant() -ne $m.jsx_sha256){Fail 'JSX_DIGEST_MISMATCH'}
  $n=0
  foreach($it in $m.asset_sha256.PSObject.Properties){
    $f=Join-Path (Join-Path $Work 'assets') $it.Name
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){Fail 'ASSET_MISSING'}
    if((Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant() -ne $it.Value){Fail 'ASSET_DIGEST_MISMATCH'}
    $n++
  }
  if($n -ne 12){Fail 'ASSET_COUNT_MISMATCH'}
  $phase='SINGLE_USE_CLAIM'
  $doc=[ordered]@{job_id='gdl-gc21-card-001';attempt_id='a0001';session_id=$session;jsx_sha256=$m.jsx_sha256;state='START_CLAIMED'}
  WriteOnce $Claim (ConvertTo-Json -InputObject $doc -Compress)
  $phase='START_ILLUSTRATOR'
  if(-not(Test-Path -LiteralPath $IllustratorExe -PathType Leaf)){Fail 'ILLUSTRATOR_BINARY_MISSING'}
  Start-Process -FilePath $IllustratorExe | Out-Null
  $phase='WAIT_ILLUSTRATOR_AND_COM'
  $app=$null
  for($i=0;$i -lt 60;$i++){
    Start-Sleep -Seconds 2
    $processes=@(Get-Process Illustrator -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $session})
    if($processes.Count -gt 1){Fail 'ILLUSTRATOR_PROCESS_NOT_UNIQUE'}
    if($processes.Count -eq 1){
      $pidIllustrator=$processes[0].Id
      try{$app=[Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')}catch{$app=$null}
      if($null -ne $app){break}
    }
  }
  if($null -eq $app){Fail 'ILLUSTRATOR_COM_TIMEOUT'}
  $phase='EXECUTE_PRIVATE_JSX'
  $pathForJs=$Jsx.Replace('\','/')
  $script='$.evalFile(new File("'+$pathForJs+'"));'
  [void]$app.DoJavaScript($script)
  $phase='VERIFY_JSX_RESULT'
  $resultJsx=Join-Path $Partial 'result.json'
  if(-not(Test-Path -LiteralPath $resultJsx -PathType Leaf)){Fail 'JSX_RESULT_MISSING'}
  $r=Get-Content -LiteralPath $resultJsx -Raw | ConvertFrom-Json
  if($r.state -ne 'NATIVE_AI_REOPENED_REVIEW_REQUIRED' -or $r.ai_reopened -ne $true){Fail 'JSX_REPORTED_BLOCKED'}
  foreach($name in @('design.ai','review.pdf','preview_p01.png','preview_p02.png','preview_p03.png','preview_p04.png')){
    $f=Join-Path $Partial $name
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){Fail 'ARTIFACT_MISSING'}
    if((Get-Item -LiteralPath $f).Length -lt 1000){Fail 'ARTIFACT_TOO_SMALL'}
  }
  $ai=Join-Path $Partial 'design.ai'
  $aiSha=(Get-FileHash -LiteralPath $ai -Algorithm SHA256).Hash.ToLowerInvariant()
  $aiBytes=(Get-Item -LiteralPath $ai).Length
  $aiReopened=$true
  $phase='MOVE_ACCEPTED_ARTIFACTS_TO_EXPORT'
  Move-Item -LiteralPath $Partial -Destination $Final -ErrorAction Stop
  $exported=$true
  $phase='DONE_REVIEW_REQUIRED'
  $ok=$true; $errorCode='NONE'
} catch {
  $message=[string]$_.Exception.Message
  if($message -like 'GC21_RUNNER_BLOCKED:*'){$errorCode=$message.Substring('GC21_RUNNER_BLOCKED:'.Length)}
  else{$errorCode='RUNTIME_EXCEPTION_REQUIRES_REVIEW'}
} finally {
  $report=[ordered]@{
    schema_version='gdl_gc21_remote_worker_result_v0_1'
    job_id='gdl-gc21-card-001';attempt_id='a0001';state=$(if($ok){'AI_REOPENED_REVIEW_REQUIRED'}else{'BLOCKED_REVIEW_PARTIAL_OUTPUT'})
    phase=$phase;error_code=$errorCode;host=$env:COMPUTERNAME
    session_id=[Diagnostics.Process]::GetCurrentProcess().SessionId
    illustrator_pid=$pidIllustrator
    ai_reopened=$aiReopened;exported=$exported;ai_sha256=$aiSha;ai_bytes=$aiBytes
    production_ready=$false;visual_approval=$false;cleanup_executed=$false
  }
  try{WriteOnce $Result (ConvertTo-Json -InputObject $report -Depth 5 -Compress)}catch{}
}
if(-not $ok){exit 2}
exit 0

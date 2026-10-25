# GC21: single-use controller, operated from s01 over SSH. NOT the legacy W2.5.3 task.
param([ValidateSet('check','launch','status')][string]$Mode='check')
$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'
$Root='D:\ForPrint_Automation\GraficsDesignLab\Automation'
$Attempt=Join-Path $Root 'jobs\gdl-gc21-card-001\a0001'
$Work=Join-Path $Attempt 'work'; $InputDir=Join-Path $Attempt 'input'
$Export=Join-Path $Attempt 'export'
$Runner=Join-Path $InputDir 'gc21_windows_runner_v0_1.ps1'
$Jsx=Join-Path $Work 'run_gc21_in_illustrator.jsx'
$Scene=Join-Path $Work 'scene_manifest.json'
$Result=Join-Path $Export 'gc21_worker_result.json'
$TaskName='ForPrint-GDL-GC21-Card-001-A0001'
$ExpectedRunnerSha='7a5a842db75569001c99a060171ea2c861ff03b7babeaa9b386406dfb84990c6'
$Install='C:\Program Files\Adobe\Adobe Illustrator 2026'
function Fail([string]$code){throw ('GC21_REMOTE_BLOCKED:'+ $code)}
function Regular([string]$p) {
  if(-not(Test-Path -LiteralPath $p -PathType Leaf)){Fail 'SOURCE_FILE_MISSING'}
  $f=Get-Item -LiteralPath $p -Force
  if($f.Attributes -band [IO.FileAttributes]::ReparsePoint){Fail 'SOURCE_REPARSE_UNSAFE'}
}
function InteractiveSession {
  $q=@(& quser.exe 2>&1 | ForEach-Object { [string]$_ })
  if($LASTEXITCODE -ne 0){Fail 'QUSER_FAILED'}
  $ids=@()
  foreach($line in $q){
    $m=[regex]::Match($line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b')
    if($m.Success){$ids += [int]$m.Groups[1].Value}
  }
  if($ids.Count -ne 1 -or $ids[0] -le 0){Fail 'NO_UNIQUE_ACTIVE_WORK_SESSION'}
  $explorer=@(Get-Process explorer -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $ids[0]})
  if($explorer.Count -lt 1){Fail 'NO_EXPLORER_IN_SESSION'}
  return $ids[0]
}
function ResolveIllustrator {
  if(-not(Test-Path -LiteralPath $Install -PathType Container)){Fail 'ILLUSTRATOR_2026_DIR_MISSING'}
  $exe=@(Get-ChildItem -LiteralPath $Install -Recurse -File -Filter 'Illustrator.exe' -ErrorAction Stop |
    Where-Object {$_.FullName -notlike '*\Plug-ins\*'})
  if($exe.Count -ne 1){Fail ('ILLUSTRATOR_2026_EXE_COUNT_'+$exe.Count)}
  return $exe[0].FullName
}
function SourceCheck {
  foreach($p in @($Attempt,$Work,$InputDir,$Export)){
    if(-not(Test-Path -LiteralPath $p -PathType Container)){Fail 'ATTEMPT_LAYOUT_MISSING'}
    $item=Get-Item -LiteralPath $p -Force
    if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){Fail 'ATTEMPT_REPARSE_UNSAFE'}
  }
  Regular $Jsx; Regular $Scene
  $m=Get-Content -LiteralPath $Scene -Raw | ConvertFrom-Json
  if($m.pages -ne 4 -or $m.sender_variant -ne 'HERASYMENKO'){Fail 'SCOPE_MISMATCH'}
  if((Get-FileHash -LiteralPath $Jsx -Algorithm SHA256).Hash.ToLowerInvariant() -ne $m.jsx_sha256){Fail 'JSX_SHA_MISMATCH'}
  $n=0
  foreach($item in $m.asset_sha256.PSObject.Properties){
    $f=Join-Path (Join-Path $Work 'assets') $item.Name
    Regular $f
    if((Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.Value){Fail 'ASSET_SHA_MISMATCH'}
    $n++
  }
  if($n -ne 12){Fail 'ASSET_COUNT_MISMATCH'}
  return $n
}
try {
  if($env:COMPUTERNAME -ine 'PREPRESS' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){Fail 'HOST_IDENTITY_INVALID'}
  if($Mode -eq 'status'){
    $task=Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Output ('TASK_STATE=' + $(if($null -eq $task){'ABSENT'}else{[string]$task.State}))
    if(Test-Path -LiteralPath $Result -PathType Leaf){
      $r=Get-Content -LiteralPath $Result -Raw | ConvertFrom-Json
      Write-Output ('GC21_WORKER_STATE=' + $r.state)
      Write-Output ('GC21_WORKER_PHASE=' + $r.phase)
      Write-Output ('GC21_WORKER_ERROR=' + $r.error_code)
      Write-Output ('GC21_AI_REOPENED=' + $r.ai_reopened)
      Write-Output ('GC21_EXPORTED=' + $r.exported)
    } else { Write-Output 'GC21_WORKER_RESULT=NOT_PRESENT' }
    Write-Output ('PARTIAL_WORK_OUT_EXISTS='+(Test-Path -LiteralPath (Join-Path $Work 'out')))
    Write-Output 'GDL_GC21_REMOTE_STATUS=READ_ONLY_PASS'
    exit 0
  }
  if((Get-Service Schedule).Status -ne 'Running'){Fail 'TASK_SCHEDULER_NOT_RUNNING'}
  $session=InteractiveSession
  $exe=ResolveIllustrator
  $n=SourceCheck
  if($Mode -eq 'check'){
    Write-Output ('ACTIVE_SESSION='+$session)
    Write-Output ('ILLUSTRATOR_EXE='+ $exe)
    Write-Output ('GC21_ASSETS='+$n)
    Write-Output ('ILLUSTRATOR_IN_SESSION='+ @(Get-Process Illustrator -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $session}).Count)
    Write-Output ('RUNNER_STAGED='+(Test-Path -LiteralPath $Runner -PathType Leaf))
    Write-Output ('TASK_EXISTS='+($null -ne (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)))
    Write-Output ('CLAIM_EXISTS='+(Test-Path -LiteralPath (Join-Path $Work 'gc21_launch_claim.json')))
    Write-Output ('RESULT_EXISTS='+(Test-Path -LiteralPath $Result))
    Write-Output 'GDL_GC21_REMOTE_CHECK=PASS'
    exit 0
  }
  # launch mode: fail closed before any scheduled task mutation.
  $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
  $principalCheck=New-Object Security.Principal.WindowsPrincipal($identity)
  if(-not $principalCheck.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){Fail 'ADMIN_TOKEN_REQUIRED'}
  Regular $Runner
  if((Get-FileHash -LiteralPath $Runner -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedRunnerSha){Fail 'RUNNER_SHA_MISMATCH'}
  if(@(Get-Process Illustrator -ErrorAction SilentlyContinue).Count -ne 0){Fail 'ILLUSTRATOR_ALREADY_RUNNING_REVIEW_FIRST'}
  if($null -ne (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)){Fail 'TASK_EXISTS_SINGLE_USE'}
  if((Test-Path -LiteralPath (Join-Path $Work 'gc21_launch_claim.json')) -or
     (Test-Path -LiteralPath (Join-Path $Work 'out')) -or
     (Test-Path -LiteralPath $Result) -or
     (Test-Path -LiteralPath (Join-Path $Export 'gc21_native_artifacts'))){Fail 'ATTEMPT_ALREADY_STARTED'}
  $psExe=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
  $args='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$Runner+'" -ExpectedSessionId '+$session+' -IllustratorExe "'+$exe+'"'
  $principal=New-ScheduledTaskPrincipal -UserId 'PREPRESS\Work' -LogonType Interactive -RunLevel Limited
  $action=New-ScheduledTaskAction -Execute $psExe -Argument $args
  $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName $TaskName -Principal $principal -Action $action -Settings $settings | Out-Null
  Start-ScheduledTask -TaskName $TaskName
  Write-Output ('GC21_TASK_NAME='+$TaskName)
  Write-Output ('GC21_EXPECTED_SESSION='+$session)
  Write-Output 'GDL_GC21_REMOTE_LAUNCH=START_REQUESTED_SINGLE_USE'
  exit 0
} catch {
  $msg=[string]$_.Exception.Message
  if($msg -notlike 'GC21_REMOTE_BLOCKED:*'){$msg='GC21_REMOTE_BLOCKED:CONTROLLER_ERROR_REQUIRES_REVIEW'}
  [Console]::Error.WriteLine($msg)
  exit 2
}

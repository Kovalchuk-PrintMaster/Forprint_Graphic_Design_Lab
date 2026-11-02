# GC47T single-use Task Scheduler controller: launch/status/collect, no cleanup.
param([ValidateSet('launch','status','collect')][string]$Mode='status',[Parameter(Mandatory=$true)][string]$AttemptId)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$Base='D:\ForPrint_Automation\GraficsDesignLab\Automation\jobs\gdl-gc47t-client-pilot-001'
$Attempt=Join-Path $Base $AttemptId
$InputDir=Join-Path $Attempt 'input';$Work=Join-Path $Attempt 'work';$Export=Join-Path $Attempt 'export'
$Runner=Join-Path $InputDir 'gc47t_windows_runner_r001.ps1'
$Bindings=Join-Path $InputDir 'gc47t_bindings_r001.json'
$Report=Join-Path $Export 'gc47t_worker_result_r001.json';$Claim=Join-Path $Work 'gc47t_launch_claim_r001.json'
$TaskName='ForPrint-GDL-GC47T-'+$AttemptId
function Fail([string]$code){throw ('GC47T_CTRL:'+ $code)}
function Regular([string]$p){if(!(Test-Path -LiteralPath $p -PathType Leaf)){Fail 'INPUT_MISSING'};$f=Get-Item -LiteralPath $p -Force;if(($f.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Fail 'REPARSE_BLOCK'}}
function CheckSha([string]$p,[string]$sha){Regular $p;if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -cne $sha){Fail 'SHA_MISMATCH'}}
function WriteOnce([string]$p,[string]$text){$b=[Text.UTF8Encoding]::new($false).GetBytes($text);$f=[IO.File]::Open($p,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);try{$f.Write($b,0,$b.Length)}finally{$f.Dispose()}}
function NativeState(){
 if(!(Test-Path -LiteralPath $Report -PathType Leaf)){return 'NOT_RECORDED'}
 $r=Get-Content -LiteralPath $Report -Raw -Encoding UTF8 | ConvertFrom-Json
 if($r.schema -cne 'gc47t_windows_worker_result_r001' -or $r.attempt -cne $AttemptId -or $r.production_ready -ne $false -or $r.visual_approved -ne $false){Fail 'WORKER_REPORT_INVALID'}
 if($r.state -cnotin @('AI_REOPENED_VISUAL_REVIEW_REQUIRED','BLOCKED_REVIEW_PARTIAL_OUTPUT')){Fail 'WORKER_STATE_INVALID'}
 return [string]$r.state
}
try {
 if($AttemptId -cnotmatch '^p\d{14}-[a-f0-9]{8}$'){Fail 'ATTEMPT_ID_INVALID'}
 if($env:COMPUTERNAME -ine 'PREPRESS' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){Fail 'IDENTITY'}
 if($Mode -eq 'status'){
  $t=Get-ScheduledTask -TaskName $TaskName -EA SilentlyContinue
  Write-Output ('T1_TASK='+$(if($null -eq $t){'ABSENT'}else{[string]$t.State.ToString().ToUpperInvariant()}))
  Write-Output ('T1_CLAIM='+$(if(Test-Path -LiteralPath $Claim){'PRESENT'}else{'ABSENT'}))
  Write-Output ('T1_NATIVE_STATE='+ (NativeState))
  Write-Output 'T1_STATUS=READ_ONLY_NON_RELEASE';exit 0
 }
 if($Mode -eq 'collect'){
  if((NativeState) -cne 'AI_REOPENED_VISUAL_REVIEW_REQUIRED'){Fail 'NATIVE_RESULT_NOT_READY'}
  $out=Join-Path $Work 'out'
  foreach($name in @('design.ai','review.pdf','preview_p01.png','preview_p02.png','preview_p03.png','preview_p04.png','result.json')){Regular (Join-Path $out $name)}
  $z=Join-Path $HOME ('gc47t_'+$AttemptId+'_review_r001.zip')
  if(Test-Path -LiteralPath $z){
   Regular $z
   Write-Output ('T1_REVIEW_ZIP_SHA256='+((Get-FileHash -LiteralPath $z -Algorithm SHA256).Hash.ToLowerInvariant()))
   Write-Output 'T1_COLLECT=ZIP_EXISTS_READ_ONLY';exit 0
  }
  Compress-Archive -LiteralPath @((Join-Path $out 'design.ai'),(Join-Path $out 'review.pdf'),(Join-Path $out 'preview_p01.png'),(Join-Path $out 'preview_p02.png'),(Join-Path $out 'preview_p03.png'),(Join-Path $out 'preview_p04.png'),(Join-Path $out 'result.json')) -DestinationPath $z -CompressionLevel Optimal
  Regular $z
  Write-Output ('T1_REVIEW_ZIP_SHA256='+((Get-FileHash -LiteralPath $z -Algorithm SHA256).Hash.ToLowerInvariant()))
  Write-Output 'T1_COLLECT=ZIP_READY_NON_RELEASE';exit 0
 }
 if((Get-Service Schedule).Status -ne 'Running'){Fail 'SCHEDULER_STOPPED'}
 if(@(Get-Process Illustrator -EA SilentlyContinue).Count -ne 0){Fail 'ILLUSTRATOR_ALREADY_RUNNING'}
 if($null -ne (Get-ScheduledTask -TaskName $TaskName -EA SilentlyContinue)){Fail 'TASK_ALREADY_EXISTS'}
 if(Test-Path -LiteralPath $Claim -PathType Leaf){Fail 'ALREADY_CLAIMED'}
 if(Test-Path -LiteralPath (Join-Path $Work 'out')){Fail 'OUTPUT_ALREADY_EXISTS'}
 if(Test-Path -LiteralPath $Report){Fail 'REPORT_ALREADY_EXISTS'}
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 $principalCheck=New-Object Security.Principal.WindowsPrincipal($identity)
 if(-not $principalCheck.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){Fail 'ADMIN_TOKEN_REQUIRED'}
 $q=@(& quser.exe 2>$null);if($LASTEXITCODE -ne 0){Fail 'QUSER_FAILED'}
 $sessions=@()
 foreach($line in $q){$m=[regex]::Match([string]$line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b');if($m.Success){$sessions+=([int]$m.Groups[1].Value)}}
 $sessions=@($sessions|Select-Object -Unique)
 if($sessions.Count -ne 1 -or $sessions[0] -le 0){Fail 'ACTIVE_WORK_SESSION_REQUIRED'}
 if(@(Get-Process explorer -EA SilentlyContinue | Where-Object {$_.SessionId -eq $sessions[0]}).Count -lt 1){Fail 'EXPLORER_SESSION_REQUIRED'}
 $install='C:\Program Files\Adobe\Adobe Illustrator 2026'
 if(!(Test-Path -LiteralPath $install -PathType Container)){Fail 'ILLUSTRATOR_INSTALL_MISSING'}
 $exes=@(Get-ChildItem -LiteralPath $install -Recurse -File -Filter Illustrator.exe -EA Stop | Where-Object {$_.FullName -notlike '*\Plug-ins\*'})
 if($exes.Count -ne 1){Fail 'ILLUSTRATOR_EXE_NOT_UNIQUE'}
 $b=Get-Content -LiteralPath $Bindings -Raw -Encoding UTF8 | ConvertFrom-Json
 if($b.schema -cne 'gc47t_windows_binding_r001' -or $b.attempt -cne $AttemptId -or $b.production_ready -ne $false){Fail 'BINDINGS_INVALID'}
 CheckSha $Runner ([string]$b.files.'input/gc47t_windows_runner_r001.ps1')
 foreach($entry in $b.files.PSObject.Properties){CheckSha (Join-Path $Attempt ($entry.Name.Replace('/','\'))) ([string]$entry.Value)}
 WriteOnce $Claim (ConvertTo-Json -InputObject ([ordered]@{schema='gc47t_launch_claim_r001';attempt=$AttemptId;state='START_CLAIMED';jsx_sha256=$b.files.'work/run_in_illustrator.jsx'}) -Compress)
 $psExe=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
 $args='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$Runner+'" -AttemptId '+$AttemptId+' -ExpectedSessionId '+$sessions[0]+' -IllustratorExe "'+$exes[0].FullName+'"'
 $principal=New-ScheduledTaskPrincipal -UserId 'PREPRESS\Work' -LogonType Interactive -RunLevel Limited
 $action=New-ScheduledTaskAction -Execute $psExe -Argument $args
 $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew
 Register-ScheduledTask -TaskName $TaskName -Principal $principal -Action $action -Settings $settings -ErrorAction Stop | Out-Null
 Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
 Write-Output 'T1_LAUNCH=START_REQUESTED_SINGLE_USE';exit 0
} catch {
 $msg=[string]$_.Exception.Message
 if($msg -notlike 'GC47T_CTRL:*'){$msg='GC47T_CTRL:CONTROLLER_EXCEPTION_REVIEW'}
 [Console]::Error.WriteLine($msg);exit 2
}

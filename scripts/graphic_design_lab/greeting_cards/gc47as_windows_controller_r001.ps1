# GC47AS: administrative scheduler bridge, separate from GC47T claim and attempt.
param([ValidateSet('inspect','prepare')][string]$Mode='inspect',[string]$RunId='')
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$Base='D:\ForPrint_Automation\GraficsDesignLab\Automation\jobs\gc47as_lifecycle_r001'
$Worker=Join-Path $Base 'gc47as_windows_worker_r001.ps1'
function StopSafe([string]$code){throw ('GC47AS_CTRL:'+ $code)}
try {
 if($env:COMPUTERNAME -ine 'PREPRESS' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){StopSafe 'IDENTITY'}
 $q=@(& quser.exe 2>$null)
 if($LASTEXITCODE -ne 0){StopSafe 'QUSER_FAILED'}
 $ids=@()
 foreach($line in $q){$m=[regex]::Match([string]$line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b');if($m.Success){$ids+=([int]$m.Groups[1].Value)}}
 $ids=@($ids|Select-Object -Unique)
 if($ids.Count -ne 1 -or $ids[0] -le 0){StopSafe 'ACTIVE_WORK_SESSION_REQUIRED'}
 if(@(Get-Process explorer -EA SilentlyContinue | Where-Object {$_.SessionId -eq $ids[0]}).Count -lt 1){StopSafe 'EXPLORER_SESSION_REQUIRED'}
 $procs=@(Get-Process Illustrator -EA SilentlyContinue)
 if($Mode -eq 'inspect'){
  Write-Output ('GC47AS_INSPECT='+$(if($procs.Count -eq 0){'CLOSED'}elseif($procs.Count -eq 1 -and $procs[0].SessionId -eq $ids[0]){'OPEN_IN_WORK_SESSION'}else{'BLOCKED_AMBIGUOUS_OR_FOREIGN_SESSION'}))
  Write-Output 'GC47AS_INSPECT_NO_MUTATION=TRUE';exit 0
 }
 if($RunId -cnotmatch '^[a-f0-9]{16}$'){StopSafe 'RUN_ID'}
 if((Get-Service Schedule).Status -ne 'Running'){StopSafe 'SCHEDULER_STOPPED'}
 if(@(Get-ScheduledTask -TaskName 'ForPrint-GDL-GC47T-*' -EA SilentlyContinue | Where-Object {$_.State -eq 'Running'}).Count -gt 0){StopSafe 'NATIVE_WORKER_RUNNING'}
 if(@(Get-ScheduledTask -TaskName 'ForPrint-GDL-GC47AS-*' -EA SilentlyContinue | Where-Object {$_.State -eq 'Running'}).Count -gt 0){StopSafe 'LIFECYCLE_WORKER_RUNNING'}
 $principalCheck=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
 if(-not $principalCheck.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){StopSafe 'ADMIN_TOKEN_REQUIRED'}
 $run=Join-Path $Base ('run_'+$RunId)
 $taskName='ForPrint-GDL-GC47AS-'+$RunId
 if(Test-Path -LiteralPath $run){StopSafe 'RUN_ALREADY_EXISTS'}
 if($null -ne (Get-ScheduledTask -TaskName $taskName -EA SilentlyContinue)){StopSafe 'TASK_EXISTS'}
 if(!(Test-Path -LiteralPath $Worker -PathType Leaf)){StopSafe 'WORKER_MISSING'}
 $file=Get-Item -LiteralPath $Worker -Force
 if(($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){StopSafe 'WORKER_REPARSE'}
 if((Get-FileHash -LiteralPath $Worker -Algorithm SHA256).Hash.ToLowerInvariant() -cne '39248d31f9f88e9fda5134a2a74bdf2cb325a9608d9949a1ff547c111ee7b071'){StopSafe 'WORKER_SHA'}
 $run=New-Item -Path $run -ItemType Directory -ErrorAction Stop
 $acl=Get-Acl -LiteralPath $run.FullName
 $rule=New-Object System.Security.AccessControl.FileSystemAccessRule('PREPRESS\Work','Modify','ContainerInherit,ObjectInherit','None','Allow')
 $acl.AddAccessRule($rule);Set-Acl -LiteralPath $run.FullName -AclObject $acl
 $psExe=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
 $args='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$Worker+'" -RunId '+$RunId+' -ExpectedSession '+$ids[0]
 $principal=New-ScheduledTaskPrincipal -UserId 'PREPRESS\Work' -LogonType Interactive -RunLevel Limited
 $action=New-ScheduledTaskAction -Execute $psExe -Argument $args
 $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
 Register-ScheduledTask -TaskName $taskName -Principal $principal -Action $action -Settings $settings -ErrorAction Stop | Out-Null
 Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
 $report=Join-Path $run.FullName 'result.json'
 for($n=0;$n -lt 42;$n++){if(Test-Path -LiteralPath $report -PathType Leaf){break};Start-Sleep -Seconds 2}
 if(!(Test-Path -LiteralPath $report -PathType Leaf)){StopSafe ('WORKER_PENDING_RUN_'+$RunId)}
 $r=Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
 if($r.schema -cne 'gc47as_illustrator_lifecycle_result_r001' -or $r.run_id -cne $RunId -or $r.force_kill -ne $false -or $r.native_dispatch -ne $false){StopSafe 'RESULT_INVALID'}
 $valid=@('ALREADY_CLOSED','GRACEFULLY_CLOSED_SAVED_DOCUMENTS','BLOCKED_UNSAVED_DOCUMENTS','BLOCKED_MULTIPLE_PROCESSES','BLOCKED_FOREIGN_SESSION','BLOCKED_COM_UNAVAILABLE','BLOCKED_DOCUMENT_COUNT','BLOCKED_QUIT_NOT_CONFIRMED','BLOCKED_PROCESS_CHANGED','BLOCKED_WORKER_ERROR')
 if($r.state -cnotin $valid){StopSafe 'RESULT_STATE_INVALID'}
 Write-Output ('GC47AS_STATE='+$r.state)
 Write-Output ('GC47AS_RUN_ID='+$RunId)
 Write-Output ('GC47AS_DOCUMENT_COUNT='+$r.document_count)
 Write-Output 'GC47AS_FORCE_KILL=FALSE GC47AS_NATIVE_DISPATCH=FALSE'
 Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
 # Valid blocked lifecycle statuses are a verified receipt, not a transport failure.
 # The s01 orchestrator interprets the state and MUST NOT dispatch native.
 exit 0
}
catch {
 $msg=[string]$_.Exception.Message
 if($msg -notlike 'GC47AS_CTRL:*'){$msg='GC47AS_CTRL:CONTROLLER_EXCEPTION_REVIEW'}
 [Console]::Error.WriteLine($msg);exit 2
}

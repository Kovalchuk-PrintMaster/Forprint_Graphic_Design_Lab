# GC47AS: runs only as PREPRESS\Work in active GUI session. No process killing.
param([Parameter(Mandatory=$true)][string]$RunId,[Parameter(Mandatory=$true)][int]$ExpectedSession)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$Base='D:\ForPrint_Automation\GraficsDesignLab\Automation\jobs\gc47as_lifecycle_r001'
$Run=Join-Path $Base ('run_'+$RunId)
$Report=Join-Path $Run 'result.json'
$state='BLOCKED_UNKNOWN';$pidValue=$null;$count=-1
function ResultOnce([string]$file,[string]$json){
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes($json)
 $handle=[IO.File]::Open($file,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$handle.Write($bytes,0,$bytes.Length)}finally{$handle.Dispose()}
}
try {
 if($RunId -cnotmatch '^[a-f0-9]{16}$'){throw 'RUN_ID'}
 if($env:COMPUTERNAME -ine 'PREPRESS' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){throw 'IDENTITY'}
 $session=[Diagnostics.Process]::GetCurrentProcess().SessionId
 if($session -ne $ExpectedSession -or $session -le 0 -or -not [Environment]::UserInteractive){throw 'INTERACTIVE_SESSION'}
 $principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
 if($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'ELEVATED_TOKEN'}
 if(Test-Path -LiteralPath $Report){throw 'REPORT_ALREADY_EXISTS'}
 $q=@(& quser.exe 2>$null)
 if($LASTEXITCODE -ne 0){throw 'QUSER_FAILURE'}
 $active=$false
 foreach($line in $q){$match=[regex]::Match([string]$line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b');if($match.Success -and [int]$match.Groups[1].Value -eq $session){$active=$true}}
 if(-not $active){throw 'SESSION_INACTIVE'}
 $processes=@(Get-Process Illustrator -ErrorAction SilentlyContinue)
 if($processes.Count -eq 0){$state='ALREADY_CLOSED'}
 elseif($processes.Count -ne 1){$state='BLOCKED_MULTIPLE_PROCESSES'}
 elseif($processes[0].SessionId -ne $session){$state='BLOCKED_FOREIGN_SESSION'}
 else {
  $pidValue=$processes[0].Id
  $app=$null
  try{$app=[Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')}catch{}
  if($null -eq $app){$state='BLOCKED_COM_UNAVAILABLE'}
  else {
   $count=[int]$app.Documents.Count
   if($count -lt 0 -or $count -gt 100){$state='BLOCKED_DOCUMENT_COUNT'}
   else {
    $safe=$true
    for($i=1;$i -le $count;$i++){
     $doc=$app.Documents.Item($i)
     if($null -eq $doc -or $doc.Saved -ne $true){$safe=$false;break}
    }
    if(-not $safe){$state='BLOCKED_UNSAVED_DOCUMENTS'}
    else {
     # The dedicated Work user's documents are all saved. Quit politely, never kill.
     $app.Quit()
     $state='BLOCKED_QUIT_NOT_CONFIRMED'
     for($n=0;$n -lt 30;$n++){
      Start-Sleep -Seconds 1
      $live=@(Get-Process Illustrator -ErrorAction SilentlyContinue)
      if($live.Count -eq 0){$state='GRACEFULLY_CLOSED_SAVED_DOCUMENTS';break}
      if($live.Count -ne 1 -or $live[0].Id -ne $pidValue){$state='BLOCKED_PROCESS_CHANGED';break}
     }
    }
   }
  }
 }
}
catch {
 # Never include exception content or document names in public reports.
 if($state -eq 'BLOCKED_UNKNOWN'){$state='BLOCKED_WORKER_ERROR'}
}
finally {
 $record=[ordered]@{
  schema='gc47as_illustrator_lifecycle_result_r001';run_id=$RunId;state=$state
  session_id=[Diagnostics.Process]::GetCurrentProcess().SessionId
  illustrator_pid=$pidValue;document_count=$count;force_kill=$false
  native_dispatch=$false;production_ready=$false
 }
 try{ResultOnce $Report (ConvertTo-Json -InputObject $record -Compress)}catch{}
}
if($state -cin @('ALREADY_CLOSED','GRACEFULLY_CLOSED_SAVED_DOCUMENTS')){exit 0}
exit 2

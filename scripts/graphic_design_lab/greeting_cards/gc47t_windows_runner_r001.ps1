# GC47T: non-release interactive single-use GC29 four-artboard Illustrator execution.
param([Parameter(Mandatory=$true)][string]$AttemptId,[Parameter(Mandatory=$true)][int]$ExpectedSessionId,[Parameter(Mandatory=$true)][string]$IllustratorExe)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$Base='D:\ForPrint_Automation\GraficsDesignLab\Automation\jobs\gdl-gc47t-client-pilot-001'
$Attempt=Join-Path $Base $AttemptId
$InputDir=Join-Path $Attempt 'input';$Work=Join-Path $Attempt 'work';$Export=Join-Path $Attempt 'export'
$Bindings=Join-Path $InputDir 'gc47t_bindings_r001.json';$Jsx=Join-Path $Work 'run_in_illustrator.jsx'
$Report=Join-Path $Export 'gc47t_worker_result_r001.json'
$phase='INITIAL';$errorCode='NOT_STARTED';$ok=$false;$pidIllustrator=$null
function Fail([string]$code){throw ('GC47T_WORKER:'+ $code)}
function Regular([string]$p){if(!(Test-Path -LiteralPath $p -PathType Leaf)){Fail 'FILE_MISSING'};$f=Get-Item -LiteralPath $p -Force;if(($f.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Fail 'REPARSE_BLOCK'}}
function CheckSha([string]$p,[string]$sha){Regular $p;if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -cne $sha){Fail 'SHA_MISMATCH'}}
function WriteOnce([string]$p,[string]$text){$b=[Text.UTF8Encoding]::new($false).GetBytes($text);$f=[IO.File]::Open($p,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);try{$f.Write($b,0,$b.Length)}finally{$f.Dispose()}}
try {
 $phase='IDENTITY'
 if($AttemptId -cnotmatch '^p\d{14}-[a-f0-9]{8}$'){Fail 'ATTEMPT_ID_INVALID'}
 $session=[Diagnostics.Process]::GetCurrentProcess().SessionId
 if($env:COMPUTERNAME -ine 'PREPRESS' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){Fail 'IDENTITY'}
 if($session -ne $ExpectedSessionId -or $session -le 0 -or -not [Environment]::UserInteractive){Fail 'NOT_INTERACTIVE_SESSION'}
 $wp=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
 if($wp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){Fail 'ELEVATED_TOKEN_DENIED'}
 if(Test-Path -LiteralPath $Report){Fail 'EXISTING_REPORT_NO_RETRY'}
 if(Test-Path -LiteralPath (Join-Path $Work 'out')){Fail 'EXISTING_OUTPUT_NO_RETRY'}
 if(@(Get-Process Illustrator -EA SilentlyContinue).Count -ne 0){Fail 'ILLUSTRATOR_ALREADY_RUNNING'}
 $q=@(& quser.exe 2>$null);if($LASTEXITCODE -ne 0){Fail 'QUSER_FAILED'}
 $active=$false
 foreach($line in $q){$m=[regex]::Match([string]$line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b');if($m.Success -and [int]$m.Groups[1].Value -eq $session){$active=$true}}
 if(-not $active){Fail 'SESSION_INACTIVE'}
 $b=Get-Content -LiteralPath $Bindings -Raw -Encoding UTF8 | ConvertFrom-Json
 if($b.schema -cne 'gc47t_windows_binding_r001' -or $b.attempt -cne $AttemptId -or $b.production_ready -ne $false){Fail 'BINDINGS_INVALID'}
 foreach($entry in $b.files.PSObject.Properties){
  $p=Join-Path $Attempt ($entry.Name.Replace('/','\'))
  CheckSha $p ([string]$entry.Value)
 }
 $phase='START_ILLUSTRATOR'
 Regular $IllustratorExe
 Start-Process -FilePath $IllustratorExe | Out-Null
 $phase='WAIT_ILLUSTRATOR_COM';$app=$null
 for($i=0;$i -lt 60;$i++){
  Start-Sleep -Seconds 2
  $procs=@(Get-Process Illustrator -EA SilentlyContinue | Where-Object {$_.SessionId -eq $session})
  if($procs.Count -gt 1){Fail 'MULTIPLE_ILLUSTRATOR_PROCESSES'}
  if($procs.Count -eq 1){$pidIllustrator=$procs[0].Id;try{$app=[Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')}catch{$app=$null};if($null -ne $app){break}}
 }
 if($null -eq $app){Fail 'ILLUSTRATOR_COM_TIMEOUT'}
 $phase='EXECUTE_GC29_JSX'
 $script='$.evalFile(new File("'+$Jsx.Replace('\','/')+'"));'
 [void]$app.DoJavaScript($script)
 $phase='VERIFY_GC29_NATIVE'
 $out=Join-Path $Work 'out';$p=Join-Path $out 'result.json';Regular $p
 $d=Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json
 if($d.schema_version -cne 'gdl_gc29_native_result_v0_1' -or $d.state -cne 'AI_REOPENED_VISUAL_REVIEW_REQUIRED' -or $d.pages -ne 4 -or $d.production_ready -ne $false -or $d.visual_approved -ne $false){Fail 'GC29_NATIVE_RESULT_NOT_SUCCESS'}
 if($d.p04_greeting_fit_state -cne 'VISIBLE_CONTENT_FITS' -or [int]$d.p04_visible_chars -lt [int]$d.p04_total_chars){Fail 'GREETING_VISIBLE_FIT_UNPROVEN'}
 foreach($name in @('design.ai','review.pdf','preview_p01.png','preview_p02.png','preview_p03.png','preview_p04.png')){
  $f=Join-Path $out $name;Regular $f
  if((Get-Item -LiteralPath $f).Length -lt 1000){Fail 'NATIVE_ARTIFACT_TOO_SMALL'}
 }
 $phase='DONE_VISUAL_REVIEW_REQUIRED';$errorCode='NONE';$ok=$true
} catch {
 $message=[string]$_.Exception.Message
 if($message -like 'GC47T_WORKER:*'){$errorCode=$message.Substring('GC47T_WORKER:'.Length)}else{$errorCode='RUNTIME_EXCEPTION_REVIEW_REQUIRED'}
} finally {
 $r=[ordered]@{schema='gc47t_windows_worker_result_r001';attempt=$AttemptId;state=$(if($ok){'AI_REOPENED_VISUAL_REVIEW_REQUIRED'}else{'BLOCKED_REVIEW_PARTIAL_OUTPUT'});phase=$phase;error_code=$errorCode;session_id=[Diagnostics.Process]::GetCurrentProcess().SessionId;illustrator_pid=$pidIllustrator;production_ready=$false;visual_approved=$false;dual_runtime_enabled=$false;cleanup_executed=$false}
 try{WriteOnce $Report (ConvertTo-Json -InputObject $r -Compress)}catch{}
}
if(-not $ok){exit 2};exit 0

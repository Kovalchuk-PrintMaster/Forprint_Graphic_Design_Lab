[CmdletBinding()]
param(
  [ValidateSet('Export')][string]$Mode='Export',
  [Parameter(Mandatory=$true)][string]$ClientFolder,
  [string]$ShareRoot='\\192.168.50.10\In_Progress'
)
$ErrorActionPreference='Stop'
$Root='D:\ForPrint_Automation\GraficsDesignLab\Automation'
function Require([bool]$condition,[string]$errorCode) { if(-not $condition){throw $errorCode} }
Require ($env:COMPUTERNAME -ceq 'PREPRESS' -and $env:USERNAME -ceq 'Work') 'GC32_WRONG_WINDOWS_IDENTITY'
Require ($ClientFolder -ne '' -and $ClientFolder -ne '.' -and $ClientFolder -ne '..' -and $ClientFolder.IndexOfAny([char[]]@('/','\')) -lt 0) 'GC32_CLIENT_NAME_INVALID'
Require ($ShareRoot -match '^\\\\[^\\]+\\In_Progress$') 'GC32_SHARE_ROOT_INVALID'
Require (Test-Path -LiteralPath $Root -PathType Container) 'GC32_ROOT_MISSING'
Require ($PSScriptRoot -ceq (Join-Path $Root 'Worker')) 'GC32_SCRIPT_OUTSIDE_SINGLE_ROOT'
$Workspace=Join-Path (Join-Path $ShareRoot $ClientFolder) '_forprint_automation'
Require (Test-Path -LiteralPath (Join-Path $Workspace 'template_studio\index.html') -PathType Leaf) 'GC32_CLIENT_PORTAL_MISSING'
$Inventory=Join-Path $Workspace 'template_studio\inventory'
if(-not (Test-Path -LiteralPath $Inventory -PathType Container)){
  New-Item -ItemType Directory -Path $Inventory -ErrorAction Stop | Out-Null
}
$Items=New-Object System.Collections.Generic.List[object]
$Seen=New-Object 'System.Collections.Generic.HashSet[string]'
function Add-Observed([string]$rel){
 if($Items.Count -ge 450){return}
 if(-not $Seen.Add($rel)){return}
 $full=Join-Path $Root $rel
 $obj=Get-Item -LiteralPath $full -Force -ErrorAction SilentlyContinue
 if($null -eq $obj){return}
 if($obj.Attributes -band [IO.FileAttributes]::ReparsePoint){return}
 if(-not ($obj.PSIsContainer -or ($obj -is [IO.FileInfo]))){return}
 $o=[ordered]@{path=($rel -replace '\\','/');kind=$(if($obj.PSIsContainer){'dir'}else{'file'});size_bytes=$(if($obj.PSIsContainer){$null}else{[long]$obj.Length});sha256=$null}
 if(-not $obj.PSIsContainer -and $obj.Length -le 25000000 -and ($obj.Extension -in @('.ps1','.cmd','.json','.svg','.png'))){$o.sha256=(Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()}
 $Items.Add([pscustomobject]$o)
}
foreach($key in @('cache','config','jobs','logs','runtime','Worker','cache\shared','Worker\gc32_prepress_worker_v0_1.ps1','config\worker_config.json')){Add-Observed $key}
# Client-relevant jobs only. Other customer files must not be revealed in this customer's portal.
foreach($rel in @('cache\clients','cache\clients\'+$ClientFolder,'jobs\'+$ClientFolder,'jobs\'+$ClientFolder+'\GreetingCards')){Add-Observed $rel}
foreach($segment in @('Worker','cache\shared','jobs\'+$ClientFolder,'cache\clients\'+$ClientFolder)){
 $top=Join-Path $Root $segment
 if(-not (Test-Path -LiteralPath $top -PathType Container)){continue}
 $pending=New-Object System.Collections.Generic.Queue[object]
 $pending.Enqueue([pscustomobject]@{Path=$top;Depth=0})
 while($pending.Count -gt 0 -and $Items.Count -lt 450){
   $next=$pending.Dequeue()
   $entries=@(Get-ChildItem -LiteralPath $next.Path -Force -ErrorAction SilentlyContinue | Select-Object -First 250)
   foreach($entry in $entries){
     if($entry.Attributes -band [IO.FileAttributes]::ReparsePoint){continue}
     $relative=$entry.FullName.Substring($Root.Length).TrimStart([char[]]@('\','/'))
     Add-Observed $relative
     if($entry.PSIsContainer -and $next.Depth -lt 2 -and $Items.Count -lt 450){
       $pending.Enqueue([pscustomobject]@{Path=$entry.FullName;Depth=($next.Depth+1)})
     }
   }
 }
}
$doc=[ordered]@{
 schema_version='forprint_gdl_gc32_prepress_tree_snapshot_v0_1';
 machine=$env:COMPUTERNAME;user=$env:USERNAME;client=$ClientFolder;root=$Root;
 captured_utc=[DateTime]::UtcNow.ToString('o');entries=@($Items.ToArray());
 operator_export_only=$true;production_authority=$false
}
$content=ConvertTo-Json -InputObject $doc -Depth 8 -Compress
Require ([Text.Encoding]::UTF8.GetByteCount($content) -lt 512000) 'GC32_SNAPSHOT_TOO_LARGE'
$target=Join-Path $Inventory 'prepress_snapshot.json'
$temp=Join-Path $Inventory ('prepress_snapshot.incoming.'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($temp,$content,(New-Object Text.UTF8Encoding($false)))
try{
 if(Test-Path -LiteralPath $target -PathType Leaf){
   $old=Get-Item -LiteralPath $target
   Require (-not ($old.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'GC32_EXISTING_SNAPSHOT_UNSAFE'
 }
 Move-Item -LiteralPath $temp -Destination $target -Force -ErrorAction Stop
}finally{}
Write-Host ('GC32_PREPRESS_SNAPSHOT=EXPORTED_REVIEW_ONLY ENTRIES='+$Items.Count)
Write-Host ('GC32_PREPRESS_SNAPSHOT_FILE='+$target)

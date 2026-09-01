#requires -Version 7.0
param(
    [Parameter(Mandatory = $true)] [string] $SourceImage,
    [Parameter(Mandatory = $true)] [string] $EngineExe,
    [int] $VisionTimeoutSeconds = 240
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $SourceImage -PathType Leaf)) { throw "Source image not found: $SourceImage" }
if (-not (Test-Path -LiteralPath $EngineExe -PathType Leaf)) { throw "Engine not found: $EngineExe" }

$runRoot = Join-Path ([IO.Path]::GetTempPath()) ("folder-vision-mvp-" + [guid]::NewGuid().ToString('N'))
$inbox = Join-Path $runRoot 'Downloads'
$localAppData = Join-Path $runRoot 'localappdata'
$eventLog = Join-Path $runRoot 'events.log'
New-Item -ItemType Directory -Path $inbox,$localAppData -Force | Out-Null
$source = Join-Path $inbox ("downloaded-reference" + [IO.Path]::GetExtension($SourceImage))
Copy-Item -LiteralPath $SourceImage -Destination $source -Force
New-Item -ItemType File -Path $eventLog -Force | Out-Null

$psi = [Diagnostics.ProcessStartInfo]::new()
$psi.FileName = (Resolve-Path -LiteralPath $EngineExe).Path
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$psi.Environment['LOCALAPPDATA'] = $localAppData
$psi.Environment['FILEID_LOG'] = 'info'

$proc = [Diagnostics.Process]::new()
$proc.StartInfo = $psi
[void]$proc.Start()
$stdoutSubscription = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -MessageData $eventLog -Action {
    if ($EventArgs.Data) { Add-Content -LiteralPath $event.MessageData -Value $EventArgs.Data }
}
$stderrSubscription = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -MessageData $eventLog -Action {
    if ($EventArgs.Data) { Add-Content -LiteralPath $event.MessageData -Value $EventArgs.Data }
}
$proc.BeginOutputReadLine()
$proc.BeginErrorReadLine()

function Send-Command([hashtable] $Command) {
    $json = $Command | ConvertTo-Json -Compress -Depth 30
    $proc.StandardInput.WriteLine($json)
    $proc.StandardInput.Flush()
}

function Event-LineCount {
    if (-not (Test-Path -LiteralPath $eventLog)) { return 0 }
    return @(Get-Content -LiteralPath $eventLog -ErrorAction SilentlyContinue).Count
}

function Wait-Event([string] $Token, [int] $AfterLine, [int] $TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($proc.HasExited) { throw "Engine exited early with code $($proc.ExitCode)" }
        $lines = @(Get-Content -LiteralPath $eventLog -ErrorAction SilentlyContinue)
        $match = $lines | Select-Object -Skip $AfterLine | Where-Object { $_ -match ('"' + [regex]::Escape($Token) + '"') } | Select-Object -First 1
        if ($match) { return $match }
        Start-Sleep -Milliseconds 250
    }
    throw "Timed out waiting for event: $Token"
}

try {
    [void](Wait-Event 'ready' 0 30)

    $after = Event-LineCount
    Send-Command @{ id = 'scan'; payload = @{ startScan = @{ rootPath = $source; rootDisplay = 'MVP inbox fixture'; rescan = $false } } }
    [void](Wait-Event 'scanComplete' $after 90)

    $after = Event-LineCount
    Send-Command @{ id = 'vision'; payload = @{ deepAnalyzeFolder = @{ pathPrefix = $source; modelKind = 'qwen3_vl_2b_ollama' } } }
    $visionLine = Wait-Event 'deepAnalyzeComplete' $after $VisionTimeoutSeconds
    $vision = $visionLine | ConvertFrom-Json
    if ($vision.payload.deepAnalyzeComplete._0.failed -ne 0) { throw "Local vision failed: $visionLine" }

    $after = Event-LineCount
    Send-Command @{ id = 'plan'; payload = @{ planRestructure = @{ libraryRoot = $inbox } } }
    $planLine = Wait-Event 'restructurePlan' $after 60
    $plan = ($planLine | ConvertFrom-Json).payload.restructurePlan._0
    if (@($plan.moves).Count -ne 1) { throw "Expected exactly one inbox move, got $(@($plan.moves).Count): $planLine" }
    $move = @($plan.moves)[0]
    if ([IO.Path]::GetExtension($move.destination) -ne [IO.Path]::GetExtension($source)) {
        throw "Extension was not preserved: $($move.destination)"
    }
    if ([IO.Path]::GetFileName($move.destination) -eq [IO.Path]::GetFileName($source)) {
        throw "Vision did not produce a contextual rename: $planLine"
    }

    $after = Event-LineCount
    Send-Command @{ id = 'apply'; payload = @{ applyRestructure = @{ libraryRoot = $inbox; moves = @($move); useSymlinks = $false } } }
    $applyLine = Wait-Event 'restructureApplyResult' $after 90
    $apply = ($applyLine | ConvertFrom-Json).payload.restructureApplyResult._0
    if ($apply.applied -ne 1 -or $apply.failed -ne 0) { throw "Apply failed: $applyLine" }
    if (-not (Test-Path -LiteralPath $move.destination -PathType Leaf)) { throw "Destination missing after apply" }
    if (Test-Path -LiteralPath $source) { throw "Source still exists after apply" }

    $after = Event-LineCount
    Send-Command @{ id = 'undo'; payload = @{ undoRestructure = @{ libraryRoot = $inbox } } }
    $undoLine = Wait-Event 'restructureApplyResult' $after 90
    $undo = ($undoLine | ConvertFrom-Json).payload.restructureApplyResult._0
    if ($undo.applied -ne 1 -or $undo.failed -ne 0) { throw "Undo failed: $undoLine" }
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Original source missing after undo" }

    [pscustomobject]@{
        Passed = $true
        OriginalName = [IO.Path]::GetFileName($source)
        ProposedName = [IO.Path]::GetFileName($move.destination)
        DestinationFolder = [IO.Path]::GetDirectoryName($move.destination)
        Apply = "1/1"
        Undo = "1/1"
        StateRoot = $localAppData
    } | Format-List

    Send-Command @{ id = 'shutdown'; payload = @{ shutdown = @{} } }
    [void]$proc.WaitForExit(15000)

    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $resolvedRunRoot = [IO.Path]::GetFullPath($runRoot)
    if (-not $resolvedRunRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing cleanup outside temp: $resolvedRunRoot"
    }
    Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force
}
finally {
    Unregister-Event -SourceIdentifier $stdoutSubscription.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $stderrSubscription.Name -ErrorAction SilentlyContinue
    if (-not $proc.HasExited) { try { $proc.Kill() } catch {} }
    if (Test-Path -LiteralPath $runRoot) { Write-Host "Retained failed-run evidence: $runRoot" }
}

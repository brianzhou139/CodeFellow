param(
    [string]$SegmentsPath = (Join-Path $PSScriptRoot "..\video\demo_segments.json"),
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\video\rendered\narration")
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$segments = Get-Content -Raw -LiteralPath $SegmentsPath | ConvertFrom-Json
for ($index = 0; $index -lt $segments.Count; $index++) {
    $path = Join-Path $OutputDirectory ("{0:D2}-{1}.wav" -f ($index + 1), $segments[$index].kind)
    $voice = New-Object -ComObject SAPI.SpVoice
    $voice.Rate = 2
    $voice.Volume = 100
    $stream = New-Object -ComObject SAPI.SpFileStream
    $stream.Open($path, 3, $false)
    $voice.AudioOutputStream = $stream
    [void]$voice.Speak([string]$segments[$index].narration)
    $stream.Close()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($stream)
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($voice)
}

Write-Output "Rendered $($segments.Count) narration segments to $OutputDirectory"

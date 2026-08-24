param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\docs\demo")
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

function New-Brush([string]$Color) {
    [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml($Color))
}

function Draw-Card {
    param(
        [string]$Path,
        [string]$LanguageLabel,
        [string]$Prompt,
        [string[]]$CodeLines,
        [string]$Explanation,
        [string]$Checks
    )

    $bitmap = [System.Drawing.Bitmap]::new(1180, 700)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

    $background = New-Brush "#07111f"
    $cardBrush = New-Brush "#0c1d31"
    $borderPen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml("#24415e"), 2)
    $green = New-Brush "#2fd6a2"
    $greenText = New-Brush "#8ff0d2"
    $white = New-Brush "#eaf2ff"
    $muted = New-Brush "#9db3cb"
    $code = New-Brush "#f5f9ff"
    $graphics.FillRectangle($background, 0, 0, 1180, 700)

    $logoRect = [System.Drawing.Rectangle]::new(62, 48, 54, 54)
    $graphics.FillRectangle($green, $logoRect)
    $logoFont = [System.Drawing.Font]::new("Consolas", 21, [System.Drawing.FontStyle]::Bold)
    $graphics.DrawString("CF", $logoFont, (New-Brush "#062118"), 70, 60)

    $titleFont = [System.Drawing.Font]::new("Segoe UI", 23, [System.Drawing.FontStyle]::Bold)
    $bodyFont = [System.Drawing.Font]::new("Segoe UI", 14)
    $labelFont = [System.Drawing.Font]::new("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
    $codeFont = [System.Drawing.Font]::new("Consolas", 17)
    $smallFont = [System.Drawing.Font]::new("Consolas", 10)
    $graphics.DrawString("CodeFellow", $titleFont, $white, 132, 45)
    $graphics.DrawString("Learn, debug, and build - completely offline.", $bodyFont, $muted, 134, 79)
    $graphics.DrawString("OFFLINE  |  CPU  |  8 GB", $smallFont, $greenText, 930, 64)

    $graphics.DrawString($LanguageLabel.ToUpperInvariant(), $labelFont, $green, 64, 132)
    $promptRect = [System.Drawing.Rectangle]::new(62, 158, 1056, 130)
    $graphics.FillRectangle($cardBrush, $promptRect)
    $graphics.DrawRectangle($borderPen, $promptRect)
    $promptTextRect = [System.Drawing.RectangleF]::new(88, 181, 1000, 90)
    $graphics.DrawString($Prompt, $bodyFont, $white, $promptTextRect)

    $graphics.DrawString("MODEL RESPONSE", $labelFont, $green, 64, 318)
    $responseRect = [System.Drawing.Rectangle]::new(62, 344, 1056, 250)
    $graphics.FillRectangle($cardBrush, $responseRect)
    $graphics.DrawRectangle($borderPen, $responseRect)
    $y = 371
    foreach ($line in $CodeLines) {
        $graphics.DrawString($line, $codeFont, $code, 88, $y)
        $y += 31
    }
    $explanationRect = [System.Drawing.RectangleF]::new(88, 483, 990, 70)
    $graphics.DrawString($Explanation, $bodyFont, $muted, $explanationRect)

    $graphics.DrawString("Qwen2.5-Coder-3B derivative  |  GGUF Q4_K_M", $smallFont, $muted, 62, 635)
    $checkSize = $graphics.MeasureString($Checks, $smallFont)
    $graphics.DrawString($Checks, $smallFont, $greenText, 1118 - $checkSize.Width, 635)

    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $smallFont.Dispose(); $codeFont.Dispose(); $labelFont.Dispose(); $bodyFont.Dispose(); $titleFont.Dispose(); $logoFont.Dispose()
    $borderPen.Dispose(); $code.Dispose(); $muted.Dispose(); $white.Dispose(); $greenText.Dispose(); $green.Dispose(); $cardBrush.Dispose(); $background.Dispose()
    $graphics.Dispose(); $bitmap.Dispose()
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

Draw-Card `
    -Path (Join-Path $OutputDirectory "codefellow-english.png") `
    -LanguageLabel "English prompt" `
    -Prompt "Implement the Python function get_positive(l). Return only positive numbers in the list. Preserve the exact function name and argument contract." `
    -CodeLines @("def get_positive(l):", "    return [x for x in l if x > 0]") `
    -Explanation "The approach is to use a list comprehension to iterate over the input list and include only elements greater than zero." `
    -Checks "Executable: YES  |  Format: PASS  |  Postprocessing: NONE"

Draw-Card `
    -Path (Join-Path $OutputDirectory "codefellow-kiswahili.png") `
    -LanguageLabel "Kiswahili + code-switching" `
    -Prompt "Tekeleza Python function triangle_area(a, h). Hifadhi function name na argument contract hizi bila kubadilisha. Jibu kwa Kiswahili." `
    -CodeLines @("def triangle_area(a, h):", "    return 0.5 * a * h") `
    -Explanation "Kutokana na urefu wa upande na eneo kubwa la kurudi kwa triangle." `
    -Checks "Inatekelezeka: NDIYO  |  Format: PASS  |  Translator: HAKUNA"

Write-Output "Rendered submission screenshots in $OutputDirectory"

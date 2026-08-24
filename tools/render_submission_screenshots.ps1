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

    $bitmap = [System.Drawing.Bitmap]::new(1200, 800)
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
    $graphics.FillRectangle($background, 0, 0, 1200, 800)

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
    $graphics.DrawString("Learn, debug, and build - no internet required.", $bodyFont, $muted, 134, 79)
    $graphics.DrawString("OFFLINE  |  CPU  |  8 GB", $smallFont, $greenText, 950, 64)

    $graphics.DrawString($LanguageLabel.ToUpperInvariant(), $labelFont, $green, 64, 132)
    $promptRect = [System.Drawing.Rectangle]::new(62, 158, 1076, 155)
    $graphics.FillRectangle($cardBrush, $promptRect)
    $graphics.DrawRectangle($borderPen, $promptRect)
    $promptTextRect = [System.Drawing.RectangleF]::new(88, 185, 1020, 105)
    $graphics.DrawString($Prompt, $bodyFont, $white, $promptTextRect)

    $graphics.DrawString("MODEL RESPONSE", $labelFont, $green, 64, 348)
    $responseRect = [System.Drawing.Rectangle]::new(62, 374, 1076, 300)
    $graphics.FillRectangle($cardBrush, $responseRect)
    $graphics.DrawRectangle($borderPen, $responseRect)
    $y = if ([string]::IsNullOrWhiteSpace($Explanation)) { 465 } else { 407 }
    foreach ($line in $CodeLines) {
        $graphics.DrawString($line, $codeFont, $code, 88, $y)
        $y += 31
    }
    $explanationRect = [System.Drawing.RectangleF]::new(88, 545, 1020, 82)
    $graphics.DrawString($Explanation, $bodyFont, $muted, $explanationRect)

    $graphics.DrawString("CodeFellow  |  Runs entirely on your laptop", $smallFont, $muted, 62, 735)
    $checkSize = $graphics.MeasureString($Checks, $smallFont)
    $graphics.DrawString($Checks, $smallFont, $greenText, 1138 - $checkSize.Width, 735)

    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $smallFont.Dispose(); $codeFont.Dispose(); $labelFont.Dispose(); $bodyFont.Dispose(); $titleFont.Dispose(); $logoFont.Dispose()
    $borderPen.Dispose(); $code.Dispose(); $muted.Dispose(); $white.Dispose(); $greenText.Dispose(); $green.Dispose(); $cardBrush.Dispose(); $background.Dispose()
    $graphics.Dispose(); $bitmap.Dispose()
}

function Draw-Cover([string]$Path) {
    $bitmap = [System.Drawing.Bitmap]::new(1200, 800)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

    $background = New-Brush "#07111f"
    $panel = New-Brush "#0c1d31"
    $green = New-Brush "#2fd6a2"
    $greenText = New-Brush "#8ff0d2"
    $white = New-Brush "#eaf2ff"
    $muted = New-Brush "#9db3cb"
    $dark = New-Brush "#062118"
    $borderPen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml("#24415e"), 2)
    $graphics.FillRectangle($background, 0, 0, 1200, 800)

    $logoRect = [System.Drawing.Rectangle]::new(72, 58, 62, 62)
    $graphics.FillRectangle($green, $logoRect)
    $logoFont = [System.Drawing.Font]::new("Consolas", 24, [System.Drawing.FontStyle]::Bold)
    $brandFont = [System.Drawing.Font]::new("Segoe UI", 26, [System.Drawing.FontStyle]::Bold)
    $headlineFont = [System.Drawing.Font]::new("Segoe UI", 42, [System.Drawing.FontStyle]::Bold)
    $subheadFont = [System.Drawing.Font]::new("Segoe UI", 18)
    $metricFont = [System.Drawing.Font]::new("Segoe UI", 20, [System.Drawing.FontStyle]::Bold)
    $labelFont = [System.Drawing.Font]::new("Consolas", 11, [System.Drawing.FontStyle]::Bold)
    $smallFont = [System.Drawing.Font]::new("Segoe UI", 13)

    $graphics.DrawString("CF", $logoFont, $dark, 82, 72)
    $graphics.DrawString("CodeFellow", $brandFont, $white, 154, 62)
    $graphics.DrawString("OFFLINE CODING TUTOR", $labelFont, $greenText, 158, 102)

    $graphics.DrawString("Learn code offline.", $headlineFont, $white, 72, 185)
    $graphics.DrawString("In English and Kiswahili.", $headlineFont, $greenText, 72, 244)
    $graphics.DrawString("Generate, debug, and understand code on an everyday laptop - without cloud APIs.", $subheadFont, $muted, 77, 330)

    $metrics = @(
        @{ X = 72; Value = "100%"; Label = "OFFLINE" },
        @{ X = 392; Value = "3.29 GiB"; Label = "PEAK MEMORY" },
        @{ X = 712; Value = "4.72"; Label = "TOKENS / SECOND" }
    )
    foreach ($metric in $metrics) {
        $rect = [System.Drawing.Rectangle]::new($metric.X, 410, 280, 145)
        $graphics.FillRectangle($panel, $rect)
        $graphics.DrawRectangle($borderPen, $rect)
        $graphics.DrawString($metric.Value, $metricFont, $white, $metric.X + 26, 440)
        $graphics.DrawString($metric.Label, $labelFont, $greenText, $metric.X + 28, 492)
    }

    $graphics.DrawString("ENGLISH", $labelFont, $greenText, 80, 626)
    $graphics.DrawString("KISWAHILI", $labelFont, $greenText, 252, 626)
    $graphics.DrawString("CODE-SWITCHING", $labelFont, $greenText, 448, 626)
    $graphics.DrawString("Coding assistance + programming education", $smallFont, $muted, 76, 704)
    $graphics.DrawString("BUILT FOR EVERYDAY LAPTOPS", $labelFont, $greenText, 874, 708)

    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $smallFont.Dispose(); $labelFont.Dispose(); $metricFont.Dispose(); $subheadFont.Dispose(); $headlineFont.Dispose(); $brandFont.Dispose(); $logoFont.Dispose()
    $borderPen.Dispose(); $dark.Dispose(); $muted.Dispose(); $white.Dispose(); $greenText.Dispose(); $green.Dispose(); $panel.Dispose(); $background.Dispose()
    $graphics.Dispose(); $bitmap.Dispose()
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

Draw-Cover -Path (Join-Path $OutputDirectory "codefellow-cover.png")

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
    -Prompt "Tekeleza Python function is_palindrome(text). Angalia ikiwa string iliyopewa ni palindrome. Hifadhi function name na argument contract hizi bila kubadilisha." `
    -CodeLines @("def is_palindrome(text):", "    return text == text[::-1]") `
    -Explanation "" `
    -Checks "Inatekelezeka: NDIYO  |  Format: PASS  |  Cloud: HAKUNA"

Write-Output "Rendered submission screenshots in $OutputDirectory"

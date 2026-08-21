# scripts/word_com_export.ps1 — إنشاء .docx عبر Microsoft Word COM
param(
    [Parameter(Mandatory = $true)]
    [string]$PayloadPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $PayloadPath)) {
    throw "Payload not found: $PayloadPath"
}

$raw = Get-Content -LiteralPath $PayloadPath -Raw -Encoding UTF8
$payload = $raw | ConvertFrom-Json

$title = [string]($payload.title)
$outPath = [string]($payload.out_path)
$keywords = [string]($payload.keywords)
$lines = @()
if ($null -ne $payload.lines) {
    $lines = @($payload.lines | ForEach-Object { [string]$_ })
}

if ([string]::IsNullOrWhiteSpace($outPath)) {
    throw "out_path is required"
}

$outDir = Split-Path -Parent $outPath
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

# Word constants
$wdFormatXMLDocument = 12
$wdAlignParagraphRight = 2
$wdAlignParagraphCenter = 1
$wdReadingOrderRtl = 1
$wdCollapseEnd = 0

$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Add()

    function Set-RtlRange {
        param(
            $Range,
            [string]$Text,
            [bool]$Bold = $false,
            [int]$SizePt = 12,
            [int]$Alignment = $wdAlignParagraphRight
        )
        $Range.Text = $Text
        $Range.Font.Name = "Arial"
        $Range.Font.Size = $SizePt
        $Range.Font.Bold = [int]$Bold
        $Range.ParagraphFormat.ReadingOrder = $wdReadingOrderRtl
        $Range.ParagraphFormat.Alignment = $Alignment
        try { $Range.LanguageID = 1025 } catch { }  # Arabic
    }

    function Add-RtlParagraph {
        param(
            [string]$Text,
            [bool]$Bold = $false,
            [int]$SizePt = 12,
            [int]$Alignment = $wdAlignParagraphRight
        )
        $end = $doc.Content.End
        if ($end -le 1) {
            $rng = $doc.Paragraphs.Item(1).Range
            Set-RtlRange -Range $rng -Text $Text -Bold $Bold -SizePt $SizePt -Alignment $Alignment
            return
        }
        $insertAt = $doc.Range($end - 1, $end - 1)
        $insertAt.InsertParagraphAfter() | Out-Null
        $para = $doc.Paragraphs.Last
        Set-RtlRange -Range $para.Range -Text $Text -Bold $Bold -SizePt $SizePt -Alignment $Alignment
    }

    Add-RtlParagraph -Text $title -Bold $true -SizePt 16 -Alignment $wdAlignParagraphCenter

    if ($lines.Count -eq 0) {
        Add-RtlParagraph -Text "—" -SizePt 12
    } else {
        foreach ($line in $lines) {
            Add-RtlParagraph -Text $line -SizePt 12
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($keywords)) {
        Add-RtlParagraph -Text " " -SizePt 12
        Add-RtlParagraph -Text "الكلمات المفتاحية:" -Bold $true -SizePt 12
        Add-RtlParagraph -Text $keywords -SizePt 12
    }

    if (Test-Path -LiteralPath $outPath) {
        Remove-Item -LiteralPath $outPath -Force
    }

    # SaveAs2(FileName, FileFormat)
    $doc.SaveAs2($outPath, $wdFormatXMLDocument) | Out-Null

    if (-not (Test-Path -LiteralPath $outPath)) {
        throw "Word COM did not create file: $outPath"
    }
    Write-Output "ok:$outPath"
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
finally {
    if ($null -ne $doc) {
        try { $doc.Close($false) } catch { }
        try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) } catch { }
    }
    if ($null -ne $word) {
        try { $word.Quit() } catch { }
        try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) } catch { }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

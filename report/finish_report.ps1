# Opens the built report in Word, fills the table of contents and the lists of figures and tables (with page numbers),
# turns the two lists into plain text (Google Docs would otherwise rebuild them from headings), saves, and exports a PDF.
param([string]$Docx = "C:\Users\Shimona\Downloads\ESA_Report_Capstone_updated.docx")
$pdf = [System.IO.Path]::ChangeExtension($Docx, ".pdf")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $d = $word.Documents.Open($Docx)
    $d.Repaginate()
    foreach ($t in $d.TablesOfContents) { $t.Update() }
    $d.Fields.Update() | Out-Null
    $d.Repaginate()
    foreach ($t in $d.TablesOfContents) { $t.Update() }
    # lists of figures / tables: keep as text (index 2 and 3; index 1 is the table of contents)
    $n = $d.TablesOfContents.Count
    for ($i = $n; $i -ge 2; $i--) { $d.TablesOfContents.Item($i).Range.Fields.Unlink() }
    $d.Save()
    $d.SaveAs2($pdf, 17)
    "pages: " + $d.ComputeStatistics(2)
    $d.Close()
} finally { $word.Quit() }
"saved $Docx and $pdf"

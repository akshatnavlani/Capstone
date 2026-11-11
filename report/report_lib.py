"""Formatting helpers for the Phase-3 report (template UE23CS441A: Times New Roman, chapter 18 / section 16 / subsection 14 /
body 12, 1.5 line spacing, A4, 2 cm margins, figures and tables numbered by chapter, header and footer from Chapter 1)."""
import re

from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FONT = "Times New Roman"
TEXT_W = 17.0  # cm between 2 cm margins on A4
BLACK = RGBColor(0, 0, 0)


def font(run, size=12, bold=None, italic=None, name=FONT, color=BLACK):
    run.font.name, run.font.size = name, Pt(size)
    rpr = run._r.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(a), name)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def style_font(style, size, bold=False, italic=False, align=None, before=0, after=6, keep=True, spacing=1.5):
    style.font.name, style.font.size, style.font.bold, style.font.italic = FONT, Pt(size), bold, italic
    style.font.color.rgb = BLACK
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(a), FONT)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        if fonts.get(qn(a)) is not None:
            del fonts.attrib[qn(a)]
    pf = style.paragraph_format
    pf.space_before, pf.space_after, pf.keep_with_next, pf.line_spacing = Pt(before), Pt(after), keep, spacing
    if align is not None:
        pf.alignment = align


class Report:
    def __init__(self, doc):
        self.doc = doc
        self.ch = 0
        self.sec = self.sub = 0
        self.fig = self.tab = self.eq = 0
        st = doc.styles
        style_font(st["Heading 1"], 18, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, before=6, after=18)
        style_font(st["Heading 2"], 16, bold=True, align=WD_ALIGN_PARAGRAPH.LEFT, before=14, after=6)
        style_font(st["Heading 3"], 14, bold=True, align=WD_ALIGN_PARAGRAPH.LEFT, before=10, after=4)
        for name in ("Figure Caption", "Table Caption"):
            s = st.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            style_font(s, 11, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, before=4, after=12, keep=(name == "Table Caption"), spacing=1.0)

    # ---------------- text
    def para(self, text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, size=12, after=8, before=0, italic=False, indent=None, spacing=1.5, bold=False):
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.alignment, pf.space_after, pf.space_before, pf.line_spacing = align, Pt(after), Pt(before), spacing
        if indent is not None:
            pf.left_indent = Cm(indent)
        # **bold** inline markup
        for i, part in enumerate(re.split(r"\*\*", text)):
            if part:
                font(p.add_run(part), size, bold=bold or (i % 2 == 1), italic=italic)
        return p

    def P(self, *texts):
        for t in texts:
            self.para(t)

    def bullets(self, items, size=12):
        for t in items:
            p = self.para("", after=4)
            pf = p.paragraph_format
            pf.left_indent, pf.first_line_indent = Cm(1.0), Cm(-0.6)
            pf.tab_stops.add_tab_stop(Cm(1.0))
            font(p.add_run("•\t"), size)
            for i, part in enumerate(re.split(r"\*\*", t)):
                if part:
                    font(p.add_run(part), size, bold=(i % 2 == 1))

    def numbered(self, items):
        for k, t in enumerate(items, 1):
            p = self.para("", after=4)
            pf = p.paragraph_format
            pf.left_indent, pf.first_line_indent = Cm(1.0), Cm(-0.7)
            pf.tab_stops.add_tab_stop(Cm(1.0))
            font(p.add_run(f"{k}.\t"), 12)
            for i, part in enumerate(re.split(r"\*\*", t)):
                if part:
                    font(p.add_run(part), 12, bold=(i % 2 == 1))

    # ---------------- structure
    def chapter(self, title):
        self.ch += 1
        self.sec = self.sub = self.fig = self.tab = self.eq = 0
        self.doc.add_section(WD_SECTION.NEW_PAGE)
        p = self.doc.add_paragraph()
        p.paragraph_format.alignment, p.paragraph_format.space_after = WD_ALIGN_PARAGRAPH.LEFT, Pt(6)
        font(p.add_run(f"CHAPTER {self.ch}"), 18, bold=True)
        h = self.doc.add_paragraph(style="Heading 1")
        font(h.add_run(title.upper()), 18, bold=True)

    def unnumbered_chapter(self, title):
        self.doc.add_section(WD_SECTION.NEW_PAGE)
        h = self.doc.add_paragraph(style="Heading 1")
        font(h.add_run(title.upper()), 18, bold=True)

    def section(self, title):
        self.sec += 1
        self.sub = 0
        h = self.doc.add_paragraph(style="Heading 2")
        font(h.add_run(f"{self.ch}.{self.sec} {title}"), 16, bold=True)

    def subsection(self, title):
        self.sub += 1
        h = self.doc.add_paragraph(style="Heading 3")
        font(h.add_run(f"{self.ch}.{self.sec}.{self.sub} {title}"), 14, bold=True)

    # ---------------- floats
    def figure(self, path, caption, width=15.0):
        self.fig += 1
        p = self.doc.add_paragraph()
        p.paragraph_format.alignment, p.paragraph_format.keep_with_next = WD_ALIGN_PARAGRAPH.CENTER, True
        p.paragraph_format.space_before = Pt(6)
        p.add_run().add_picture(str(path), width=Cm(width))
        c = self.doc.add_paragraph(style="Figure Caption")
        font(c.add_run(f"Figure {self.ch}.{self.fig}: {caption}"), 11, bold=True)
        return f"Figure {self.ch}.{self.fig}"

    def placeholder(self, what, caption, height_pt=150):
        """A box to paste a screenshot into, with its numbered caption already in place."""
        self.fig += 1
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.alignment, pf.keep_with_next, pf.space_before, pf.space_after = WD_ALIGN_PARAGRAPH.CENTER, True, Pt(height_pt / 2), Pt(height_pt / 2)
        ppr = p._p.get_or_add_pPr()
        bdr = OxmlElement("w:pBdr")
        for side in ("top", "left", "bottom", "right"):
            e = OxmlElement(f"w:{side}")
            e.set(qn("w:val"), "dashed"), e.set(qn("w:sz"), "8"), e.set(qn("w:space"), "8"), e.set(qn("w:color"), "808080")
            bdr.append(e)
        ppr.append(bdr)
        r = p.add_run(f"[ Paste screenshot here: {what} ]")
        font(r, 11, italic=True, color=RGBColor(0x80, 0x80, 0x80))
        c = self.doc.add_paragraph(style="Figure Caption")
        font(c.add_run(f"Figure {self.ch}.{self.fig}: {caption}"), 11, bold=True)
        return f"Figure {self.ch}.{self.fig}"

    def table(self, caption, header, rows, widths, size=10.5, bold_first_col=False):
        self.tab += 1
        c = self.doc.add_paragraph(style="Table Caption")
        font(c.add_run(f"Table {self.ch}.{self.tab}: {caption}"), 11, bold=True)
        t = self.doc.add_table(rows=1 + len(rows), cols=len(header))
        self._grid(t, widths)
        for i, row in enumerate([header] + rows):
            for j, val in enumerate(row):
                cell = t.cell(i, j)
                cell.text = ""
                p = cell.paragraphs[0]
                p.paragraph_format.space_after, p.paragraph_format.line_spacing = Pt(2), 1.0
                for k, part in enumerate(re.split(r"\*\*", str(val))):
                    if part:
                        font(p.add_run(part), size, bold=(i == 0) or (k % 2 == 1) or (bold_first_col and j == 0))
                if i == 0:
                    shade(cell, "D9E2F3")
                    p.paragraph_format.keep_with_next = True   # header row stays with the first data row
        for i, row in enumerate(t.rows):
            trPr = row._tr.get_or_add_trPr()
            trPr.append(OxmlElement("w:cantSplit"))
            if i == 0:
                trPr.append(OxmlElement("w:tblHeader"))      # repeat the header row on a new page
        self.doc.add_paragraph().paragraph_format.space_after = Pt(4)
        return f"Table {self.ch}.{self.tab}"

    def _grid(self, t, widths):
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        tbl = t._tbl
        tblPr = tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement(f"w:{side}")
            e.set(qn("w:val"), "single"), e.set(qn("w:sz"), "4"), e.set(qn("w:space"), "0"), e.set(qn("w:color"), "000000")
            borders.append(e)
        tblPr.append(borders)
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        tblPr.append(layout)
        tw = OxmlElement("w:tblW")
        tw.set(qn("w:w"), str(int(sum(widths) * 567))), tw.set(qn("w:type"), "dxa")
        old = tblPr.find(qn("w:tblW"))
        if old is not None:
            tblPr.remove(old)
        tblPr.append(tw)
        grid = tbl.tblGrid
        for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
            gc.set(qn("w:w"), str(int(w * 567)))
        for row in t.rows:
            for cell, w in zip(row.cells, widths):
                cell.width = Cm(w)

    def code(self, title, lines):
        """Pseudocode in a shaded box, numbered as a table-free 'Algorithm' (listed in the text, not in the figure list)."""
        p = self.para(f"**{title}**", after=2, align=WD_ALIGN_PARAGRAPH.LEFT)
        p.paragraph_format.keep_with_next = True
        t = self.doc.add_table(rows=1, cols=1)
        self._grid(t, [TEXT_W - 0.5])
        cell = t.cell(0, 0)
        shade(cell, "F2F2F2")
        cell.text = ""
        for k, line in enumerate(lines):
            q = cell.paragraphs[0] if k == 0 else cell.add_paragraph()
            q.paragraph_format.space_after, q.paragraph_format.line_spacing = Pt(0), 1.0
            font(q.add_run(line if line else " "), 9.5, name="Courier New")
        self.doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def equation(self, text):
        self.eq += 1
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_before, pf.space_after, pf.line_spacing = Pt(4), Pt(8), 1.2
        pf.tab_stops.add_tab_stop(Cm(TEXT_W / 2), WD_TAB_ALIGNMENT.CENTER)
        pf.tab_stops.add_tab_stop(Cm(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
        font(p.add_run(f"\t{text}\t({self.ch}.{self.eq})"), 12, italic=False)

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"), shd.set(qn("w:color"), "auto"), shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def add_field(paragraph, instr, placeholder="Update field to show the list."):
    def fld(kind):
        r = paragraph.add_run()
        e = OxmlElement("w:fldChar")
        e.set(qn("w:fldCharType"), kind)
        r._r.append(e)
        return r
    fld("begin")
    r = paragraph.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    r._r.append(it)
    fld("separate")
    font(paragraph.add_run(placeholder), 12)
    fld("end")

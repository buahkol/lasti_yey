"""PDF reports (FR-21, FR-25), built with reportlab.

Two documents, both A4 portrait without photos:

- batch_report_pdf: inspection report of one batch (totals, status against the
  NG tolerance, NG per hour chart, loss estimate, production events, top NG scores).
- date_recap_pdf: production recap for a date range (totals, output per day
  chart, table per batch with a total row).

Both take the plain dicts returned by controllers.ReportController, so the
desktop UI and a future server endpoint can share this module.
"""

import os
from dataclasses import dataclass, field
from datetime import date, datetime

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

NG_TOLERANCE_PERCENT = 5.0
_MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
           "November", "Desember"]
_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

# Palette matching the desktop app
NAVY = colors.HexColor("#172A3A")
BRAND = colors.HexColor("#355872")
TEXT_2 = colors.HexColor("#56718A")
TEXT_3 = colors.HexColor("#7F97AB")
BORDER = colors.HexColor("#E4EBF2")
SUBTLE = colors.HexColor("#F6F8FB")
OK_C = colors.HexColor("#355872")
NG_C = colors.HexColor("#FD31AE")
NG_SOFT = colors.HexColor("#F4B3CD")
INDIGO = colors.HexColor("#5C61E4")
HOLD_BG, HOLD_FG = colors.HexColor("#FFF1D6"), colors.HexColor("#8A5A00")
PASS_BG, PASS_FG = colors.HexColor("#E3F6EC"), colors.HexColor("#1E7A4C")
PINK_BG, PINK_FG = colors.HexColor("#FFE9F5"), colors.HexColor("#9B1C5A")

_FONT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "font"))
_FONTS = {
    "Body": "PlusJakartaSans-Regular.ttf",
    "Body-Medium": "PlusJakartaSans-Medium.ttf",
    "Body-SemiBold": "PlusJakartaSans-SemiBold.ttf",
    "Body-Bold": "PlusJakartaSans-Bold.ttf",
    "Display": "BricolageGrotesque-Bold.ttf",
}
_registered = False


def _register_fonts() -> None:
    """Use the app fonts; fall back to Helvetica when the font folder is missing."""
    global _registered
    if _registered:
        return
    for name, filename in _FONTS.items():
        path = os.path.join(_FONT_DIR, filename)
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(name, path))
        else:
            fallback = {"Body": "Helvetica", "Body-Medium": "Helvetica", "Display": "Helvetica-Bold"}
            _FONT_ALIAS[name] = fallback.get(name, "Helvetica-Bold")
    _registered = True


_FONT_ALIAS: dict = {}


def _f(name: str) -> str:
    return _FONT_ALIAS.get(name, name)


# ---------------------------------------------------------------- formatting
def _num(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def _pct(v: float) -> str:
    return f"{v:.1f}%".replace(".", ",")


def _rupiah(v: float) -> str:
    return "Rp" + _num(v)


def _score(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def _long_date(d: date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _short_date(d: date) -> str:
    return f"{d.day} {_SHORT[d.month - 1]}"


def _period(start: date, end: date) -> str:
    """23 sampai 25 November 2026, or full dates when the months differ."""
    if start == end:
        return _long_date(start)
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day} sampai {_long_date(end)}"
    if start.year == end.year:
        return f"{start.day} {_MONTHS[start.month - 1]} sampai {_long_date(end)}"
    return f"{_long_date(start)} sampai {_long_date(end)}"


def _stamp(dt: datetime) -> str:
    return f"{_long_date(dt.date())}, pukul {dt:%H.%M}"


# ---------------------------------------------------------------- styles
@dataclass
class _Styles:
    title: ParagraphStyle = field(init=False)
    overline: ParagraphStyle = field(init=False)
    meta: ParagraphStyle = field(init=False)
    h2: ParagraphStyle = field(init=False)
    body: ParagraphStyle = field(init=False)
    small: ParagraphStyle = field(init=False)
    cell: ParagraphStyle = field(init=False)
    cell_r: ParagraphStyle = field(init=False)
    cell_b: ParagraphStyle = field(init=False)
    head: ParagraphStyle = field(init=False)
    head_r: ParagraphStyle = field(init=False)
    kpi_label: ParagraphStyle = field(init=False)
    kpi_value: ParagraphStyle = field(init=False)
    kpi_meta: ParagraphStyle = field(init=False)

    def __post_init__(self):
        b, sb, bd = _f("Body"), _f("Body-SemiBold"), _f("Body-Bold")
        self.title = ParagraphStyle("title", fontName=_f("Display"), fontSize=20, leading=24, textColor=NAVY)
        self.overline = ParagraphStyle("over", fontName=bd, fontSize=7.5, leading=10, textColor=TEXT_3)
        self.meta = ParagraphStyle("meta", fontName=b, fontSize=9, leading=13, textColor=TEXT_2)
        self.h2 = ParagraphStyle("h2", fontName=_f("Display"), fontSize=12.5, leading=16, textColor=NAVY,
                                 spaceBefore=4, spaceAfter=2)
        self.body = ParagraphStyle("body", fontName=b, fontSize=9, leading=13, textColor=NAVY)
        self.small = ParagraphStyle("small", fontName=b, fontSize=8, leading=11, textColor=TEXT_3)
        self.cell = ParagraphStyle("cell", fontName=b, fontSize=8, leading=10.5, textColor=NAVY)
        self.cell_r = ParagraphStyle("cellr", parent=self.cell, alignment=TA_RIGHT)
        self.cell_b = ParagraphStyle("cellb", parent=self.cell, fontName=sb)
        self.head = ParagraphStyle("head", fontName=bd, fontSize=7.5, leading=10, textColor=TEXT_3)
        self.head_r = ParagraphStyle("headr", parent=self.head, alignment=TA_RIGHT)
        self.kpi_label = ParagraphStyle("kl", fontName=_f("Body-Medium"), fontSize=8, leading=10, textColor=TEXT_2)
        self.kpi_value = ParagraphStyle("kv", fontName=_f("Display"), fontSize=16, leading=19, textColor=NAVY)
        self.kpi_meta = ParagraphStyle("km", fontName=b, fontSize=7.5, leading=10, textColor=TEXT_3)


PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


# ---------------------------------------------------------------- building blocks
def _header(st: _Styles, overline: str, title: str, subtitle: str, status: str | None, printed: str) -> list:
    left = [Paragraph(overline.upper(), st.overline), Spacer(1, 2), Paragraph(title, st.title), Spacer(1, 3),
            Paragraph(subtitle, st.meta)]
    right = [Paragraph("DICETAK", ParagraphStyle("r", parent=st.overline, alignment=TA_RIGHT)), Spacer(1, 2),
             Paragraph(printed, ParagraphStyle("rm", parent=st.meta, alignment=TA_RIGHT))]
    if status:
        right += [Spacer(1, 6), _pill(st, status)]
    t = Table([[left, right]], colWidths=[CONTENT_W * 0.62, CONTENT_W * 0.38])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                           ("LINEBELOW", (0, 0), (-1, 0), 1, BORDER)]))
    return [t, Spacer(1, 12)]


def _pill(st: _Styles, status: str) -> Table:
    bg, fg = {"HOLD": (HOLD_BG, HOLD_FG), "PASSED": (PASS_BG, PASS_FG)}.get(status, (SUBTLE, NAVY))
    label = Paragraph(status, ParagraphStyle("pill", fontName=_f("Body-Bold"), fontSize=8, leading=10, textColor=fg,
                                             alignment=TA_CENTER))
    t = Table([[label]], colWidths=[22 * mm], hAlign="RIGHT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                           ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _kpis(st: _Styles, items: list) -> Table:
    """items: (label, value, meta, highlight)."""
    cells = []
    for label, value, meta, highlight in items:
        size = 16 if len(value) <= 7 else (13 if len(value) <= 10 else 11.5)  # long rupiah values stay on one line
        vstyle = ParagraphStyle("kv2", parent=st.kpi_value, fontSize=size, leading=size + 3,
                                textColor=PINK_FG if highlight else NAVY)
        cells.append([Paragraph(label, st.kpi_label), Spacer(1, 4), Paragraph(value, vstyle), Spacer(1, 2),
                      Paragraph(meta, st.kpi_meta)])
    gap = 3 * mm
    w = (CONTENT_W - gap * (len(items) - 1)) / len(items)
    row, widths = [], []
    for i, c in enumerate(cells):
        if i:
            row.append("")
            widths.append(gap)
        row.append(c)
        widths.append(w)
    t = Table([row], colWidths=widths)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 9),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 9),
             ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    for i in range(0, len(row), 2):
        highlight = items[i // 2][3]
        style += [("BACKGROUND", (i, 0), (i, 0), PINK_BG if highlight else SUBTLE),
                  ("BOX", (i, 0), (i, 0), 0.6, BORDER), ("ROUNDEDCORNERS", [6, 6, 6, 6])]
    for i in range(1, len(row), 2):
        style += [("LEFTPADDING", (i, 0), (i, 0), 0), ("RIGHTPADDING", (i, 0), (i, 0), 0)]
    t.setStyle(TableStyle(style))
    return t


def _note(st: _Styles, held: bool, message: str) -> Table:
    bg, fg = (HOLD_BG, HOLD_FG) if held else (PASS_BG, PASS_FG)
    p = Paragraph(message, ParagraphStyle("note", parent=st.body, textColor=fg))
    t = Table([[p]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def _table(st: _Styles, headers: list, rows: list, widths: list, align: list, total: list | None = None) -> Table:
    """align: 'L' or 'R' per column. rows contain strings; total is an optional bold last row."""
    def cell(v, i, bold=False):
        if isinstance(v, Paragraph):
            return v
        style = st.cell_r if align[i] == "R" else (st.cell_b if bold else st.cell)
        if bold and align[i] == "R":
            style = ParagraphStyle("cbr", parent=st.cell_r, fontName=_f("Body-SemiBold"))
        return Paragraph(str(v), style)

    data = [[Paragraph(h.upper(), st.head_r if align[i] == "R" else st.head) for i, h in enumerate(headers)]]
    data += [[cell(v, i) for i, v in enumerate(r)] for r in rows]
    if total:
        data.append([cell(v, i, bold=True) for i, v in enumerate(total)])
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BACKGROUND", (0, 0), (-1, 0), SUBTLE),
             ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER), ("TOPPADDING", (0, 0), (-1, -1), 5),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 6),
             ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    if total:
        style += [("BACKGROUND", (0, -1), (-1, -1), SUBTLE), ("LINEABOVE", (0, -1), (-1, -1), 0.8, TEXT_3)]
    t.setStyle(TableStyle(style))
    return t


def _bar_chart(labels: list, series: list, bar_colors: list, max_value: float, height: float = 62 * mm,
               stacked: bool = False, highlight: int | None = None, value_labels: bool = False) -> Drawing:
    d = Drawing(CONTENT_W, height)
    ch = VerticalBarChart()
    ch.x, ch.y = 30, 22
    ch.width, ch.height = CONTENT_W - 40, height - 36
    ch.data = series
    ch.categoryAxis.categoryNames = labels
    ch.categoryAxis.labels.fontName = _f("Body")
    ch.categoryAxis.labels.fontSize = 7.5
    ch.categoryAxis.labels.fillColor = TEXT_3
    ch.categoryAxis.strokeColor = BORDER
    ch.categoryAxis.visibleTicks = False
    ch.valueAxis.valueMin = 0
    ch.valueAxis.valueMax = max_value
    ch.valueAxis.valueStep = max_value / 4
    ch.valueAxis.labels.fontName = _f("Body")
    ch.valueAxis.labels.fontSize = 7.5
    ch.valueAxis.labels.fillColor = TEXT_3
    ch.valueAxis.labelTextFormat = lambda v: _num(v)
    ch.valueAxis.strokeColor = colors.white
    ch.valueAxis.visibleGrid = True
    ch.valueAxis.gridStrokeColor = BORDER
    ch.valueAxis.gridStrokeWidth = 0.5
    ch.valueAxis.visibleTicks = False
    ch.barWidth = 6
    ch.groupSpacing = 8
    ch.barSpacing = 0
    if stacked:
        ch.categoryAxis.style = "stacked"
    for i, c in enumerate(bar_colors):
        ch.bars[i].fillColor = c
        ch.bars[i].strokeColor = None
    if highlight is not None and not stacked:
        ch.bars[(0, highlight)].fillColor = NG_C
    d.add(ch)
    if value_labels and series:
        n = len(labels)
        step = ch.width / n
        for i, v in enumerate(series[0]):
            y = ch.y + ch.height * v / max_value + 3
            d.add(String(ch.x + step * (i + 0.5), y, str(v), fontName=_f("Body-SemiBold"), fontSize=7.5,
                         fillColor=NG_C if i == highlight else TEXT_2, textAnchor="middle"))
    return d


def _legend(st: _Styles, items: list) -> Paragraph:
    parts = [f'<font color="{c.hexval().replace("0x", "#")}">■</font> {label}' for label, c in items]
    return Paragraph("&nbsp;&nbsp;&nbsp;".join(parts), ParagraphStyle("lg", parent=st.small, alignment=TA_LEFT))


def _section(st: _Styles, title: str, caption: str | None, *flow) -> KeepTogether:
    items = [Paragraph(title, st.h2)]
    if caption:
        items += [Paragraph(caption, st.small), Spacer(1, 6)]
    items += list(flow)
    return KeepTogether(items + [Spacer(1, 12)])


def _doc(path: str, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(path, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=16 * mm,
                             bottomMargin=18 * mm, title=title, author="SiMonPro", creator="SiMonPro")


def _footer(label: str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
        canvas.setFont(_f("Body"), 7.5)
        canvas.setFillColor(TEXT_3)
        canvas.drawString(MARGIN, 8 * mm, f"SiMonPro, monitoring inspeksi kemasan kaleng sarden. {label}")
        canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, f"Halaman {doc.page}")
        canvas.restoreState()
    return draw


# ---------------------------------------------------------------- documents
BATCH_SECTIONS = ("summary", "chart", "loss", "events", "top_scores")
RECAP_SECTIONS = ("summary", "chart", "loss", "table")


def batch_report_pdf(path: str, report: dict, sections=BATCH_SECTIONS, printed_by: str = "Operasional",
                     printed_at: datetime | None = None) -> str:
    """Write the inspection report of one batch. report comes from ReportController.batch_report()."""
    _register_fonts()
    st = _Styles()
    printed_at = printed_at or datetime.now()
    r = report
    held = r["held"]
    story = _header(st, "Laporan inspeksi batch", f"Batch {r['code']}",
                    f"{r['product']}<br/>Produksi {r['date']}, {r['window']}",
                    "HOLD" if held else "PASSED", f"{_stamp(printed_at)}<br/>oleh {printed_by}")

    if "summary" in sections:
        items = [("Total diperiksa", _num(r["total"]), "kaleng", False),
                 ("Kaleng OK", _num(r["ok"]), _pct(r["ok_percent"]), False),
                 ("Kaleng NG", _num(r["ng"]), f"{_pct(r['ng_percent'])}, batas {NG_TOLERANCE_PERCENT:g}%", True)]
        if "loss" in sections:
            items.append(("Estimasi kerugian", _rupiah(r["loss"]), f"{r['ng']} x {_rupiah(r['unit_price'])}", False))
        items.append(("Kejadian", str(r["events"]), f"{r['events_reject']} REJECT, {r['events_manual']} manual", False))
        gap = r["ng_percent"] - NG_TOLERANCE_PERCENT
        gap_text = f"{gap:.1f}".replace(".", ",")
        msg = (f"Persentase NG {_pct(r['ng_percent'])} melewati batas toleransi {NG_TOLERANCE_PERCENT:g}% sebesar "
               f"{gap_text} poin. Batch berstatus <b>HOLD</b> dan belum lolos inspeksi."
               if held else
               f"Persentase NG {_pct(r['ng_percent'])} berada di bawah batas toleransi {NG_TOLERANCE_PERCENT:g}%. "
               "Batch berstatus <b>PASSED</b> dan lolos inspeksi.")
        story.append(_section(st, "Ringkasan", None, _kpis(st, items), Spacer(1, 8), _note(st, held, msg)))
    elif "loss" in sections:
        story.append(_section(st, "Estimasi kerugian", None, Paragraph(
            f"{r['ng']} kaleng NG x {_rupiah(r['unit_price'])} = <b>{_rupiah(r['loss'])}</b>", st.body)))

    if "chart" in sections and r["ng_per_hour"]:
        hours = r["ng_per_hour"]
        values = [ng for _, ng, _ in hours]
        peak = max(range(len(values)), key=values.__getitem__)
        top = max(4, -(-max(values) // 4) * 4 + 4)
        nxt = f"{int(hours[peak][0][:2]) + 1:02d}.00"
        chart = _bar_chart([h for h, _, _ in hours], [values], [NG_SOFT], top, highlight=peak, value_labels=True)
        rows = [[h, _num(out), str(ng), _pct(ng / out * 100 if out else 0)] for h, ng, out in hours]
        table = _table(st, ["Jam", "Diperiksa", "NG", "Persentase NG"], rows,
                       [CONTENT_W * 0.25] * 4, ["L", "R", "R", "R"])
        story.append(_section(st, "Sebaran NG per jam",
                              f"Puncak pukul {hours[peak][0]} sampai {nxt} dengan {values[peak]} kaleng NG.",
                              chart, Spacer(1, 8), table))

    if "events" in sections:
        events = r["events_list"]
        rows = [[e.time, e.kind.replace("_", " "), e.source, e.note] for e in events]
        body = (_table(st, ["Waktu", "Jenis", "Sumber", "Keterangan"], rows,
                       [16 * mm, 38 * mm, 22 * mm, CONTENT_W - 76 * mm], ["L", "L", "L", "L"])
                if rows else Paragraph("Tidak ada kejadian tercatat.", st.small))
        story.append(_section(st, "Kejadian produksi",
                              f"{r['events']} kejadian; REJECT dicatat otomatis oleh AI. Daftar menampilkan "
                              f"{len(rows)} kejadian terbaru.", body))

    if "top_scores" in sections and r["top_scores"]:
        rows = [[a.time, _score(a.score), _score(a.threshold), _score(a.score - a.threshold)] for a in r["top_scores"]]
        story.append(_section(st, "Skor NG tertinggi", "Skor anomali PatchCore, dari 0 sampai 1.",
                              _table(st, ["Waktu", "Skor", "Ambang", "Selisih"], rows,
                                     [CONTENT_W * 0.25] * 4, ["L", "R", "R", "R"])))

    doc = _doc(path, f"Laporan inspeksi batch {r['code']}")
    footer = _footer(f"Laporan inspeksi batch {r['code']}.")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path


def date_recap_pdf(path: str, recap: dict, sections=RECAP_SECTIONS, printed_by: str = "Operasional",
                   printed_at: datetime | None = None) -> str:
    """Write the production recap for a date range. recap comes from ReportController.date_recap()."""
    _register_fonts()
    st = _Styles()
    printed_at = printed_at or datetime.now()
    r = recap
    start, end = r["start"], r["end"]
    period = _period(start, end)
    story = _header(st, "Rekap produksi per tanggal", period, f"{r['batch_count']} batch dimulai pada rentang ini",
                    None, f"{_stamp(printed_at)}<br/>oleh {printed_by}")

    if "summary" in sections:
        items = [("Total diperiksa", _num(r["total"]), f"{r['batch_count']} batch", False),
                 ("Kaleng OK", _num(r["ok"]), _pct(100 - r["ng_percent"]) if r["total"] else "0,0%", False),
                 ("Kaleng NG", _num(r["ng"]), f"{_pct(r['ng_percent'])}, batas {NG_TOLERANCE_PERCENT:g}%", True)]
        if "loss" in sections:
            items.append(("Estimasi kerugian", _rupiah(r["loss"]), f"{_num(r['ng'])} kaleng NG", False))
        items.append(("Status batch", f"{r['passed']} PASSED", f"{r['hold']} HOLD, {r['running']} berjalan", False))
        msg = (f"{r['hold']} batch ditutup dengan status <b>HOLD</b> dan belum lolos inspeksi." if r["hold"]
               else "Semua batch yang sudah ditutup berstatus <b>PASSED</b> dan lolos inspeksi.")
        story.append(_section(st, "Ringkasan", None, _kpis(st, items), Spacer(1, 8), _note(st, r["hold"] > 0, msg)))
    elif "loss" in sections:
        story.append(_section(st, "Estimasi kerugian", None, Paragraph(
            f"{_num(r['ng'])} kaleng NG, estimasi kerugian <b>{_rupiah(r['loss'])}</b>.", st.body)))

    if "chart" in sections and r["per_day"]:
        per_day = r["per_day"]
        top_total = max((ok + ng for _, ok, ng in per_day), default=0)
        top = max(1000, -(-top_total // 1000) * 1000)
        chart = _bar_chart([d for d, _, _ in per_day], [[ok for _, ok, _ in per_day], [ng for _, _, ng in per_day]],
                           [OK_C, NG_C], top, stacked=True)
        story.append(_section(st, "Output per hari", "Kaleng OK dan NG yang diperiksa setiap hari.",
                              chart, _legend(st, [("OK", OK_C), ("NG", NG_C)])))

    if "table" in sections:
        rows = []
        for row in r["rows"]:
            b = row["batch"]
            status = b.status if b.running else b.inspection
            pct = _pct(b.ng_percent)
            if b.ng_percent > NG_TOLERANCE_PERCENT:
                pct = f'<font color="{PINK_FG.hexval().replace("0x", "#")}">{pct}</font>'
            line = [f"{b.code}<br/><font size=7 color='#7F97AB'>{b.sku}</font>", b.product,
                    _short_date(b.started_at.date()) + f", {b.started_at:%H.%M}", _num(b.output), _num(row["ok"]),
                    _num(row["ng"]), pct, status]
            if "loss" in sections:
                line.append(_rupiah(row["loss"]))
            rows.append(line)
        headers = ["Kode batch", "Produk", "Mulai", "Output", "OK", "NG", "% NG", "Status"]
        widths = [22 * mm, 32 * mm, 20 * mm, 16 * mm, 14 * mm, 9 * mm, 13 * mm, 19 * mm]
        align = ["L", "L", "L", "R", "R", "R", "R", "L"]
        total = ["Total", "", "", _num(r["total"]), _num(r["ok"]), _num(r["ng"]), _pct(r["ng_percent"]), ""]
        if "loss" in sections:
            headers.append("Kerugian")
            widths.append(CONTENT_W - sum(widths))
            align.append("R")
            total.append(_rupiah(r["loss"]))
        else:
            widths[1] += CONTENT_W - sum(widths)
        body = (_table(st, headers, rows, widths, align, total) if rows
                else Paragraph("Tidak ada batch pada rentang tanggal ini.", st.small))
        story.append(Paragraph("Rekap per batch", st.h2))
        story.append(Paragraph("Status PASSED atau HOLD ditentukan saat batch ditutup; batch yang masih berjalan "
                               "ditandai BERJALAN.", st.small))
        story.append(Spacer(1, 6))
        story.append(body)

    label = _period(start, end)
    doc = _doc(path, f"Rekap produksi {label}")
    footer = _footer(f"Rekap produksi {label}.")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path

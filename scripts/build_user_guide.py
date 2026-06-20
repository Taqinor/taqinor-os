#!/usr/bin/env python3
"""Generate the TAQINOR OS User Guide PDF.

A practical operator's manual derived from docs/CODEMAP.md: every module
explained, how each chains to the others, and what the user should actually do.
Pure-Python (reportlab) so it builds anywhere without system libraries.
"""

from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------- brand palette
NUIT = colors.HexColor("#10203A")      # deep navy ("nuit")
NUIT2 = colors.HexColor("#1d3557")     # lighter navy
BRASS = colors.HexColor("#C8932B")     # brass / gold accent
BRASS_LT = colors.HexColor("#F3E6C6")  # pale brass for callout fills
AZUR = colors.HexColor("#2D6CB5")      # azure
INK = colors.HexColor("#1f2933")       # body text
MUTED = colors.HexColor("#52606d")     # secondary text
RULE = colors.HexColor("#cbd2d9")      # hairline rules
CARD = colors.HexColor("#F5F7FA")      # light card fill
GREEN = colors.HexColor("#2f855a")

OUT = "docs/TAQINOR_OS_User_Guide.pdf"
TITLE = "TAQINOR OS — User & Operations Guide"

# ----------------------------------------------------------------------- styles
styles = getSampleStyleSheet()


def S(name, **kw):
    base = kw.pop("parent", styles["Normal"])
    return ParagraphStyle(name, parent=base, **kw)


body = S("body", fontName="Helvetica", fontSize=9.6, leading=14.5,
         textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6)
body_l = S("body_l", parent=body, alignment=TA_LEFT)
lead_in = S("lead_in", parent=body, fontSize=10.5, leading=16, spaceAfter=8,
            alignment=TA_LEFT)
h1 = S("h1", fontName="Helvetica-Bold", fontSize=18, leading=22,
       textColor=NUIT, spaceBefore=6, spaceAfter=2)
h1_num = S("h1_num", fontName="Helvetica-Bold", fontSize=11, leading=13,
           textColor=BRASS, spaceAfter=1)
h2 = S("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
       textColor=NUIT2, spaceBefore=12, spaceAfter=3)
h3 = S("h3", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
       textColor=AZUR, spaceBefore=8, spaceAfter=2)
mini = S("mini", fontName="Helvetica-Bold", fontSize=8, leading=11,
         textColor=BRASS, spaceAfter=2)
label = S("label", fontName="Helvetica-Bold", fontSize=8.6, leading=12,
          textColor=NUIT)
bullet = S("bullet", parent=body, alignment=TA_LEFT, spaceAfter=2.5, leading=13.5)
callout = S("callout", fontName="Helvetica", fontSize=9.3, leading=13.6,
            textColor=INK, alignment=TA_LEFT)
callout_b = S("callout_b", parent=callout, fontName="Helvetica-Bold")
toc_item = S("toc_item", fontName="Helvetica", fontSize=10, leading=18,
             textColor=INK)
small = S("small", fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED)
cover_title = S("cover_title", fontName="Helvetica-Bold", fontSize=34,
                leading=38, textColor=colors.white, alignment=TA_LEFT)
cover_sub = S("cover_sub", fontName="Helvetica", fontSize=13, leading=18,
              textColor=BRASS_LT, alignment=TA_LEFT)
white_small = S("white_small", fontName="Helvetica", fontSize=9.5, leading=14,
                textColor=colors.HexColor("#AFC0D8"), alignment=TA_LEFT)


# --------------------------------------------------------------- custom flowables
class Divider(Flowable):
    def __init__(self, color=BRASS, width=46 * mm, thick=2.2):
        super().__init__()
        self.color = color
        self.w = width
        self.thick = thick
        self.height = 6

    def wrap(self, aw, ah):
        return (self.w, self.height)

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thick)
        self.canv.line(0, 3, self.w, 3)


def chip(text, fill, fg=colors.white):
    p = Paragraph(f'<font color="{fg.hexval()}"><b>{text}</b></font>',
                  S("chip", fontSize=8, leading=11, alignment=TA_CENTER))
    t = Table([[p]], colWidths=[None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


def callout_box(lines, title="WHAT YOU DO", fill=BRASS_LT, bar=BRASS,
                title_color=None):
    """A left-bar callout card holding a bold title + bullet lines."""
    inner = [Paragraph(title, S("co_t", fontName="Helvetica-Bold", fontSize=8.4,
                                leading=11, textColor=title_color or NUIT,
                                spaceAfter=3))]
    for ln in lines:
        inner.append(Paragraph("•&nbsp;&nbsp;" + ln, callout))
    cell = Table([[inner]], colWidths=[None])
    cell.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    outer = Table([[cell]], colWidths=[None])
    outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return outer


def connects(text):
    """A compact 'chained to' strip."""
    p = Paragraph('<b><font color="%s">CHAINED TO&nbsp;&nbsp;</font></b>%s'
                  % (AZUR.hexval(), text),
                  S("conn", fontName="Helvetica", fontSize=8.8, leading=12.6,
                    textColor=INK, alignment=TA_LEFT))
    t = Table([[p]], colWidths=[None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ("LINEABOVE", (0, 0), (-1, -1), 0.5, RULE),
    ]))
    return t


def blist(items, st=bullet):
    return ListFlowable(
        [ListItem(Paragraph(t, st), leftIndent=10, value="•") for t in items],
        bulletType="bullet", bulletFontName="Helvetica", bulletColor=BRASS,
        leftIndent=12, bulletFontSize=8, spaceBefore=1, spaceAfter=4,
    )


# ---------------------------------------------------------------- doc machinery
story = []


def module(num, name, fr, tagline):
    """Module header block."""
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"MODULE {num}", mini))
    story.append(Paragraph(name, h2))
    if fr:
        story.append(Paragraph(
            f'<font color="{MUTED.hexval()}">In the app: <b>{fr}</b></font>',
            small))
    story.append(Paragraph(f'<i>{tagline}</i>',
                           S("tl", parent=body_l, textColor=MUTED, fontSize=9.2,
                             spaceAfter=5)))


# =============================================================== PAGE TEMPLATES
def cover_page(canv, doc):
    canv.saveState()
    canv.setFillColor(NUIT)
    canv.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    # brass band
    canv.setFillColor(BRASS)
    canv.rect(0, A4[1] - 250, 14 * mm, 250, fill=1, stroke=0)
    # subtle azure block bottom
    canv.setFillColor(NUIT2)
    canv.rect(0, 0, A4[0], 60 * mm, fill=1, stroke=0)
    canv.setFillColor(BRASS)
    canv.rect(0, 60 * mm, A4[0], 1.4, fill=1, stroke=0)
    canv.restoreState()


def content_page(canv, doc):
    canv.saveState()
    # header rule
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.6)
    canv.line(20 * mm, A4[1] - 14 * mm, A4[0] - 20 * mm, A4[1] - 14 * mm)
    canv.setFont("Helvetica", 7.5)
    canv.setFillColor(MUTED)
    canv.drawString(20 * mm, A4[1] - 12.4 * mm, "TAQINOR OS")
    canv.drawRightString(A4[0] - 20 * mm, A4[1] - 12.4 * mm,
                         "User & Operations Guide")
    # footer
    canv.setStrokeColor(RULE)
    canv.line(20 * mm, 14 * mm, A4[0] - 20 * mm, 14 * mm)
    canv.setFont("Helvetica", 7.5)
    canv.setFillColor(MUTED)
    canv.drawString(20 * mm, 10.5 * mm,
                    "Confidential — internal operating manual")
    canv.setFillColor(BRASS)
    canv.setFont("Helvetica-Bold", 8)
    canv.drawRightString(A4[0] - 20 * mm, 10.5 * mm, "%d" % doc.page)
    canv.restoreState()


frame = Frame(20 * mm, 16 * mm, A4[0] - 40 * mm, A4[1] - 30 * mm, id="main")
cover_frame = Frame(24 * mm, 70 * mm, A4[0] - 48 * mm, 150 * mm, id="cover")

doc = BaseDocTemplate(
    OUT, pagesize=A4, title=TITLE, author="TAQINOR OS",
    leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
    bottomMargin=16 * mm,
)
doc.addPageTemplates([
    PageTemplate(id="Cover", frames=[cover_frame], onPage=cover_page),
    PageTemplate(id="Content", frames=[frame], onPage=content_page),
])

# ============================================================== COVER (flowables)
story.append(Spacer(1, 8 * mm))
story.append(Paragraph("OPERATING MANUAL", cover_sub))
story.append(Spacer(1, 4))
story.append(Paragraph("TAQINOR&nbsp;OS", cover_title))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "Every module, how it works, how it all chains together — "
    "and exactly what you should do in it.", cover_sub))
story.append(Spacer(1, 14))
story.append(Paragraph(
    "The multi-tenant ERP that runs your solar business end to end: "
    "leads &rarr; quotes &rarr; orders &rarr; invoices &rarr; installation "
    "&rarr; after-sales — on one connected record.", white_small))
story.append(Spacer(1, 30))
story.append(Paragraph(
    f'<font color="#AFC0D8">Prepared {date.today():%d %B %Y} &nbsp;·&nbsp; '
    f'Version 1 &nbsp;·&nbsp; Source of truth: docs/CODEMAP.md</font>',
    white_small))

story.append(NextPageTemplate("Content"))
story.append(PageBreak())

# ============================================================ HOW TO READ / TOC
story.append(Paragraph("How to use this guide", h1))
story.append(Divider())
story.append(Spacer(1, 6))
story.append(Paragraph(
    "This is your operating manual — not a technical spec. It is written for "
    "you (the founder) and your team, so it tells you what each part of "
    "TAQINOR OS is for, how it connects to everything else, and the concrete "
    "actions you should take. Read Sections 1–3 once to understand the whole "
    "system; then keep Section 4 (the modules) and Section 6 (your daily "
    "rhythm) as a reference.", lead_in))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "Throughout, look for these markers:", body_l))
marker_tbl = Table([
    [chip("CHAINED TO", AZUR), Paragraph(
        "where the data comes from and where it flows next", body_l)],
    [chip("WHAT YOU DO", BRASS), Paragraph(
        "the concrete actions for you and your team in that screen", body_l)],
], colWidths=[34 * mm, None])
marker_tbl.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(marker_tbl)
story.append(Spacer(1, 12))

story.append(Paragraph("Contents", h2))
toc = [
    ("1", "The big picture — what TAQINOR OS is"),
    ("2", "The golden thread — how everything chains together"),
    ("3", "Roles, login & who does what"),
    ("4", "The modules, one by one"),
    ("", "    CRM · Sales (Ventes) · Quote Generator & PDFs · Stock ·"),
    ("", "    Installations · Field tools · After-sales (SAV) · Reporting ·"),
    ("", "    Settings · Notifications & Automation · AI · API · Imports"),
    ("5", "The rules you must never break"),
    ("6", "Your operating rhythm — daily, weekly, monthly"),
    ("7", "What protects you — safety, tenancy, audit"),
    ("8", "Quick reference — screen map"),
]
for n, t in toc:
    if n:
        story.append(Paragraph(
            f'<font color="{BRASS.hexval()}"><b>{n}.</b></font>&nbsp;&nbsp;{t}',
            toc_item))
    else:
        story.append(Paragraph(
            f'<font color="{MUTED.hexval()}">{t}</font>',
            S("toc_sub", parent=toc_item, fontSize=9, leading=14,
              textColor=MUTED)))
story.append(PageBreak())

# ====================================================== 1. THE BIG PICTURE
story.append(Paragraph("1", h1_num))
story.append(Paragraph("The big picture", h1))
story.append(Divider())
story.append(Spacer(1, 6))
story.append(Paragraph(
    "TAQINOR OS is the single system that runs your solar installation "
    "business. One customer record travels the whole journey: a prospect "
    "becomes a lead, the lead gets a quote, the quote is signed and becomes an "
    "order, the order is invoiced and paid, the job is installed on site, the "
    "installed equipment is tracked under warranty, and any later problem "
    "becomes an after-sales ticket. Nothing is re-typed between stages — each "
    "module hands its data to the next.", lead_in))
story.append(Paragraph(
    "Under the hood it is a web application you open in a browser. You don't "
    "install anything: your team logs in and works. A few facts that shape how "
    "you should think about it:", body_l))
story.append(blist([
    "<b>It is multi-tenant.</b> Every piece of data belongs to your company "
    "and is invisible to any other company on the platform. You never set "
    "this — the system stamps your company on everything automatically.",
    "<b>Everything is one connected chain.</b> The same client, quote and job "
    "are linked, so a number you enter once (a price, a power rating, a serial "
    "number) is reused everywhere downstream.",
    "<b>It is bilingual and Moroccan-first.</b> Screens are in French, "
    "WhatsApp messages can go out in French or Darija, amounts are in MAD, and "
    "Moroccan legal IDs (ICE, IF, RC, patente, CNSS) live on your company "
    "profile and flow onto documents.",
    "<b>It is safe by design.</b> Every change is logged, the live system can "
    "be rolled back if a release breaks something, and sensitive numbers "
    "(your buy prices, margins, costs) are never shown on anything a client "
    "sees.",
]))
story.append(Spacer(1, 4))
story.append(callout_box([
    "Think of TAQINOR OS as one long conveyor belt. Your job is to keep "
    "records moving along it — never to keep two parallel copies of the same "
    "thing in a spreadsheet on the side.",
    "When something looks wrong, the fastest fix is almost always upstream: "
    "correct the lead or the quote, and the corrected value flows forward.",
], title="THE ONE IDEA TO REMEMBER", fill=BRASS_LT, bar=BRASS))
story.append(PageBreak())

# ====================================================== 2. THE GOLDEN THREAD
story.append(Paragraph("2", h1_num))
story.append(Paragraph("The golden thread — how everything chains together",
                       h1))
story.append(Divider())
story.append(Spacer(1, 6))
story.append(Paragraph(
    "This is the most important page in the guide. Every module exists to move "
    "a record one step further along this thread. Learn it once and the whole "
    "system makes sense.", lead_in))

flow_rows = [
    ("①  LEAD", "CRM",
     "A prospect is captured (typed in, imported, or pushed from the website). "
     "It carries the contact, the energy profile (bills), the roof/site, and "
     "a <b>pipeline stage</b>: Nouveau → Contacté → Devis envoyé → Relance → "
     "Signé (or Froid)."),
    ("②  QUOTE (Devis)", "Ventes",
     "You build a quote for the lead. The client is created automatically from "
     "the lead — you never duplicate it. The quote walks brouillon → envoyé → "
     "<b>accepté</b>. Accepting it is the moment the lead becomes <b>Signé</b>."),
    ("③  ORDER (Bon de commande)", "Ventes",
     "The accepted quote becomes a client order. Marking it <b>livré</b> "
     "automatically takes the sold goods out of stock."),
    ("④  INVOICE (Facture)", "Ventes",
     "From the quote/order you raise invoices — deposit, intermediate, "
     "balance, or full. Payments and credit notes attach here; the system "
     "tracks exactly what is still owed and chases it with relances."),
    ("⑤  INSTALLATION (Chantier)", "Installations",
     "Once signed, the job becomes a chantier. It <b>freezes the bill of "
     "materials</b> from the quote, reserves that stock, schedules field "
     "interventions, and runs a checklist on site."),
    ("⑥  EQUIPMENT", "SAV",
     "During the on-site checklist, serial numbers are captured. Each becomes "
     "a tracked piece of equipment with its own <b>warranty clock</b>, linked "
     "back to the installation and the product."),
    ("⑦  AFTER-SALES (Ticket)", "SAV",
     "Any later issue opens a ticket against that equipment/installation. The "
     "system already knows whether it is still under warranty."),
]
data = [[Paragraph(f'<b>{a}</b>', S("ft", fontName="Helvetica-Bold",
                                    fontSize=9, leading=12,
                                    textColor=colors.white)),
         Paragraph(c, S("fb", parent=body_l, fontSize=8.8, leading=12.4,
                        spaceAfter=0))]
        for a, m, c in flow_rows]
ft = Table(data, colWidths=[42 * mm, None])
sty = [
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("BACKGROUND", (0, 0), (0, -1), NUIT),
    ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 7),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ("LINEBELOW", (0, 0), (-1, -2), 0.5, RULE),
    ("LINEAFTER", (0, 0), (0, -1), 2, BRASS),
    ("BACKGROUND", (1, 0), (1, -1), colors.white),
]
ft.setStyle(TableStyle(sty))
story.append(ft)
story.append(Spacer(1, 8))
story.append(callout_box([
    "Two things ride <b>alongside</b> this thread but never merge into it: the "
    "pipeline <b>stage</b> (Nouveau…Signé — a sales funnel layer) and the "
    "document <b>statuses</b> (a quote being brouillon/accepté, an invoice "
    "being payée…). They are separate on purpose — a lead's funnel position is "
    "not the same as a document's state.",
    "“Perdu” (lost) is a flag you can set from <i>any</i> stage with a reason "
    "— it is not itself a stage.",
], title="KEEP THESE TWO LAYERS SEPARATE", fill=CARD, bar=AZUR))
story.append(PageBreak())

# ====================================================== 3. ROLES
story.append(Paragraph("3", h1_num))
story.append(Paragraph("Roles, login & who does what", h1))
story.append(Divider())
story.append(Spacer(1, 6))
story.append(Paragraph(
    "Everyone logs in at the same address with their own account. What each "
    "person sees and can do is decided by their <b>role</b>. The menu itself "
    "shrinks or grows to match — a technician simply won't see the screens "
    "they don't need.", body_l))
story.append(Paragraph("The seven standard roles", h3))
role_rows = [
    ("Directeur", "Full access incl. margins, costs, commissions and the "
     "activity journal. This is your seat."),
    ("Administrateur", "Manages users, roles and company settings; full "
     "operational access."),
    ("Commercial responsable", "Sales lead — sees and reassigns the whole "
     "sales team's leads, quotes and invoices."),
    ("Commercial", "Works their own leads and quotes."),
    ("Technicien responsable", "Field lead — sees and assigns all chantiers, "
     "interventions and SAV tickets."),
    ("Technicien", "Works their own assigned jobs and tickets."),
    ("Viewer", "Read-only — can look, cannot change."),
]
rt = Table([[Paragraph(f"<b>{r}</b>", body_l), Paragraph(d, body_l)]
            for r, d in role_rows], colWidths=[46 * mm, None])
rt.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("BACKGROUND", (0, 0), (0, -1), CARD),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
    ("LINEAFTER", (0, 0), (0, -1), 0.5, RULE),
]))
story.append(rt)
story.append(Spacer(1, 6))
story.append(Paragraph(
    "Roles can also be scoped to a <b>team</b>: if you set a person's "
    "supervisor, a responsable sees their whole sub-team's records while each "
    "person still sees their own. You can also create custom roles with exactly "
    "the permissions you want.", body_l))
story.append(callout_box([
    "Set up people <b>before</b> you start working: Admin → Utilisateurs adds "
    "each teammate and assigns a role; Admin → Rôles lets you fine-tune "
    "permissions or build a custom role.",
    "Give yourself <b>Directeur</b>. Give Meryem and any office staff "
    "<b>Administrateur</b> or <b>Commercial responsable</b>. Give field staff "
    "<b>Technicien</b>. Reassign as the team grows — never share one login.",
    "Buy prices, margins and commissions are visible <b>only</b> to roles you "
    "grant it to (Directeur by default). Keep it that way.",
], title="WHAT YOU DO — SET UP YOUR TEAM FIRST"))
story.append(PageBreak())

# ====================================================== 4. MODULES
story.append(Paragraph("4", h1_num))
story.append(Paragraph("The modules, one by one", h1))
story.append(Divider())
story.append(Spacer(1, 4))
story.append(Paragraph(
    "Each module below follows the same shape: what it is, how it works, what "
    "it is chained to, and what you should do in it. They are in the order of "
    "the golden thread, so reading top to bottom walks a job from first contact "
    "to after-sales.", body_l))
story.append(Spacer(1, 6))

# ---- 4.1 CRM
module("4.1", "CRM — Leads &amp; Clients", "Menu “CRM” · /crm · /crm/leads",
       "Where every customer relationship begins and lives.")
story.append(Paragraph(
    "The CRM holds two things: <b>Clients</b> (the people/companies you do "
    "business with) and <b>Leads</b> (live sales opportunities). A lead is a "
    "rich solar record — contact (incl. WhatsApp & GPS), the energy profile "
    "(winter/summer bills, the 82-21 regularisation flag), the roof and site, "
    "a light survey, plus pipeline fields: owner, channel, priority, tags, "
    "next-follow-up date, installation type and — if lost — the reason. Every "
    "lead carries a <b>stage</b> on the funnel (Nouveau → Contacté → Devis "
    "envoyé → Relance → Signé, or Froid).", body_l))
story.append(Paragraph(
    "Leads come in three ways: typed in by your team, bulk-imported, or pushed "
    "automatically from your website form. Every lead has an Odoo-style "
    "<b>chatter</b>: it logs field changes by itself and lets you add manual "
    "notes — who did what is always recorded. You can view leads as a kanban "
    "board, a list, a calendar or charts, detect & merge duplicates, and "
    "archive (reversibly) the ones that go cold.", body_l))
story.append(connects(
    "Receives website leads automatically · feeds <b>Ventes</b> (a quote is "
    "built on a lead, and the client is resolved from it — never duplicated) · "
    "the moment a quote is accepted, the lead flips to <b>Signé</b> and the "
    "job is born in <b>Installations</b>."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Capture every prospect as a lead the same day — a lead not in the system "
    "doesn't exist.",
    "Keep the <b>stage</b> honest as the deal moves; set a <b>relance date</b> "
    "so the system reminds you to follow up.",
    "Fill the energy profile (bills, summer-different toggle, 82-21) — those "
    "numbers pre-fill the quote and the solar sizing, saving you re-entry.",
    "When you lose one, mark it <b>Perdu</b> with a reason, don't delete it — "
    "the reasons become your loss analytics.",
    "Use merge when the same prospect shows up twice; archive (not delete) the "
    "truly dead ones.",
]))
story.append(Spacer(1, 6))

# ---- 4.2 VENTES
module("4.2", "Sales — Quotes, Orders, Invoices, Payments",
       "Menu “Ventes” · /ventes/devis · /ventes/bons-commande · "
       "/ventes/factures · /ventes/avoirs · /ventes/relances",
       "The money pipeline: from a priced quote to cash in the bank.")
story.append(Paragraph(
    "This is the largest module and it runs the full commercial lifecycle:", body_l))
story.append(blist([
    "<b>Devis (Quotes)</b> — built per lead, with a reference numbered per "
    "month, a market mode (résidentiel / industriel / agricole), an accepted "
    "option (with/without battery), the technical study, discount handling "
    "(with an approval threshold), and versioning. Statuses: brouillon → "
    "envoyé → accepté / refusé / expiré.",
    "<b>Bons de commande (Orders)</b> — an accepted quote becomes an order; "
    "marking it <b>livré</b> decrements stock.",
    "<b>Factures (Invoices)</b> — deposit / intermediate / balance / full. "
    "Each freezes its amounts (HT, TVA, TTC). The system computes "
    "<b>montant dû = TTC − paid − credit notes</b>.",
    "<b>Paiements</b> — record each payment (cash, transfer, cheque, card…).",
    "<b>Avoirs (Credit notes)</b> — issued against an invoice, they reduce "
    "what's owed.",
    "<b>Relances (Recovery)</b> — escalating follow-ups on unpaid invoices, "
    "plus an aged-balance view and client statements.",
]))
story.append(Paragraph(
    "Quotes and invoices can be shared with the client by a secure tokenized "
    "link (for WhatsApp delivery, no login needed) that expires after 30 days "
    "and never exposes buy prices.", body_l))
story.append(connects(
    "Built from a <b>CRM</b> lead/client · prices its lines from the "
    "<b>Stock</b> catalogue · accepting a quote signs the <b>CRM</b> lead and "
    "lets you spin up an <b>Installation</b> · delivered orders move "
    "<b>Stock</b> · paid/owed totals feed <b>Reporting</b>."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Always start a quote <b>from the lead</b> (CRM → lead → “devis”) so the "
    "client links correctly and you don't create duplicates.",
    "Never hand-build a client-facing quote PDF anywhere else — the only "
    "approved path is the quote generator and its “/proposal” PDF (next "
    "module). This keeps every quote consistent and keeps your buy prices off "
    "the page.",
    "When the client agrees, mark the quote <b>accepté</b> — that one click "
    "signs the lead and unlocks the order and the chantier.",
    "Invoice in stages (deposit → balance) and <b>record every payment</b> the "
    "day it lands, so the relances and aged-balance stay accurate.",
    "Let the system chase late payers (Relances) instead of doing it by hand.",
]))
story.append(Spacer(1, 6))

# ---- 4.3 QUOTE GENERATOR
module("4.3", "Quote Generator &amp; Quote PDFs",
       "/ventes/devis/nouveau · the “/proposal” PDF",
       "Turns an energy profile into a correct, on-brand solar proposal.")
story.append(Paragraph(
    "The generator is the screen where a quote is actually created "
    "(<i>/ventes/devis/nouveau</i>). It does the solar math for you in three "
    "market modes:", body_l))
story.append(blist([
    "<b>Résidentiel</b> — the simulator behaviour (sizing from bills).",
    "<b>Industriel / Commercial</b> — a self-consumption study: "
    "self-consumption & coverage rates, savings, payback.",
    "<b>Agricole (pompage)</b> — pumping: you enter pump CV/type/voltage/HMT "
    "and desired flow; it sizes the panel array, matches the right VEICHI "
    "variateur, and computes m³/day — no battery or inverter.",
]))
story.append(Paragraph(
    "It auto-fills products and prices from your catalogue, is 100% TTC, and "
    "will <b>never reject a number you type</b>. From the list's PDF dialog you "
    "choose the format: a 3-page premium proposal, a 4-page version with the "
    "study, or a 1-page summary. Every PDF shows the full price chain "
    "(Sous-total HT → Remise → Total HT → TVA → Total TTC), a system summary, "
    "and rich product sheets — and <b>never</b> your buy prices or margins.", body_l))
story.append(connects(
    "Reads the <b>CRM</b> lead's energy profile to pre-fill · pulls products & "
    "prices from <b>Stock</b> · writes the quote into <b>Ventes</b> · the PDF "
    "is delivered to the client by secure link / WhatsApp."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Use this screen for <b>every</b> new quote — it is the single approved "
    "way to produce a client quote PDF.",
    "Pick the market mode that matches the job; let the auto-fill do the "
    "sizing, then adjust lines/prices as needed.",
    "Choose the 1-page summary for a quick offer, the 3- or 4-page premium for "
    "a full proposal. The study page needs study data — fill it in the "
    "generator first.",
    "If a price-less pump shows “prix à renseigner”, price it in the catalogue "
    "before quoting it — the generator deliberately won't guess.",
]))
story.append(Spacer(1, 6))

# ---- 4.4 STOCK
module("4.4", "Stock — Catalogue, Inventory &amp; Suppliers",
       "Menu “Stock” · /stock · /stock/mouvements · "
       "/stock/bons-commande-fournisseur · /stock/ocr-import",
       "The product catalogue and the single source of truth for quantities.")
story.append(Paragraph(
    "Stock holds your <b>Produits</b> (each with a sell price, an internal "
    "buy price, quantity, alert threshold, category, supplier, and a "
    "commercial sheet — brand, description, warranty; pumps also carry their "
    "performance curve). Around them sit categories, brands, suppliers, "
    "per-supplier buy prices (for cheapest-sourcing), stock locations "
    "(depot + vans), and the procurement chain: <b>supplier purchase "
    "orders</b> (receiving them adds stock) and <b>supplier returns</b> "
    "(validating them removes stock).", body_l))
story.append(Paragraph(
    "Every quantity change is written as a <b>movement</b> (entry / exit / "
    "transfer / adjustment) — that ledger is the audit trail, so stock is "
    "never edited silently. The catalogue also shows <b>reserved vs "
    "available</b>: stock promised to a signed chantier is held back so you "
    "don't double-sell it. You can even import supplier deliveries by photo "
    "via OCR.", body_l))
story.append(connects(
    "Prices the lines on every <b>quote/invoice</b> · delivered orders & "
    "validated chantiers create <b>movements</b> here · signed jobs reserve "
    "stock via <b>Installations</b> · buy prices feed the admin-only margin "
    "view in <b>Reporting</b> (never a client document)."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Seed and maintain the catalogue first — correct sell prices, brands, "
    "descriptions and warranties make every quote and product sheet correct.",
    "Keep <b>buy prices</b> (prix d'achat) filled for the margin view, but "
    "trust the system: they are internal-only and never reach a client.",
    "Set an <b>alert threshold</b> per product so low-stock warnings fire "
    "before you run out on a job.",
    "Move stock through purchase orders and movements — never adjust a number "
    "by hand unless you're correcting a real count (use an “ajustement”, which "
    "is logged).",
]))
story.append(Spacer(1, 6))

# ---- 4.5 INSTALLATIONS
module("4.5", "Installations — Chantiers &amp; Field Execution",
       "Menu “Chantiers” · /chantiers · /interventions · /ma-journee",
       "Where a signed deal becomes a real job on a real roof.")
story.append(Paragraph(
    "A <b>chantier</b> (installation project) is created from a signed quote "
    "(“créer depuis devis”). It links back to the quote, order, lead and "
    "client, and <b>freezes the bill of materials</b> from the quote so the "
    "job's materials can't drift. It walks a status from SIGNÉ → matériel "
    "commandé → planifié → en cours → installé → réceptionné → clôturé, and "
    "tracks the law 82-21 regulatory dossier.", body_l))
story.append(Paragraph(
    "Underneath sit <b>interventions</b> (site visits — pose, raccordement, "
    "mise en service, contrôle, dépannage) with their own kanban and their own "
    "status track, a per-chantier <b>checklist</b> (auto-chosen by market "
    "type) whose serial-capture steps register equipment, and a "
    "technician's <b>“Ma journée”</b> day view. When the chantier reaches "
    "INSTALLÉ, the reserved stock is consumed exactly once. Cancelling or "
    "closing releases any unused reservation.", body_l))
story.append(connects(
    "Born from a <b>Ventes</b> quote/order · reserves & then consumes "
    "<b>Stock</b> · its checklist creates <b>SAV</b> equipment records · "
    "produces field PDFs (PV de réception, bon de livraison, attestation) · "
    "progress feeds <b>Reporting</b>."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Create the chantier from the quote the moment it's signed — that freezes "
    "the materials and reserves the stock.",
    "Keep the status moving as the job progresses; don't skip INSTALLÉ — it is "
    "what consumes stock and closes the loop.",
    "Plan interventions and assign technicians (or let the default installer "
    "take it); the team works it from “Ma journée”.",
    "Run the on-site checklist and <b>capture serial numbers</b> — that is "
    "what starts every warranty clock.",
    "Generate the PV de réception / attestation at handover, straight from the "
    "chantier.",
]))
story.append(Spacer(1, 6))

# ---- 4.6 OUTILLAGE
module("4.6", "Field Tools (Outillage)",
       "Menu “Chantiers” → /outillage · Settings → “Kits d'outillage”",
       "Your durable tools — tracked, never sold, never consumed.")
story.append(Paragraph(
    "Outillage tracks durable tooling (drills, ladders, meters…) completely "
    "separately from the sellable stock catalogue. Each tool has an asset tag, "
    "a serial number, a home location (a depot or a van), and a status "
    "(available / on intervention / in repair / lost). You can group tools "
    "into reusable <b>kits</b> (e.g. “pose structure”, “raccordement”, “mise "
    "en service”) so the right kit pre-selects for a given intervention type.", body_l))
story.append(connects(
    "Tools attach to <b>Installations</b> interventions via kits · stays out "
    "of <b>Stock</b> and off every client document — never sellable, never "
    "consumed."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Register your durable tools once and assign each a home van/depot.",
    "Build a kit per intervention type so a crew grabs the right tools "
    "without thinking.",
    "Keep statuses current (in repair / lost) so you know what's actually "
    "available before dispatching a crew.",
]))
story.append(Spacer(1, 6))

# ---- 4.7 SAV
module("4.7", "After-Sales (SAV) — Equipment, Tickets, Contracts",
       "Menu “SAV” · /equipements · /parc · /sav · /sav/contrats",
       "Warranty tracking and the support desk for installed systems.")
story.append(Paragraph(
    "SAV has three parts. <b>Équipements</b> is the registry of everything you "
    "installed — each item links to its product and its installation, carries "
    "a serial number and computed warranty end-dates, and a status (in "
    "service / replaced / out of service). <b>Tickets</b> are the support "
    "cases (corrective or preventive), each with a status (nouveau → planifié "
    "→ en cours → résolu → clôturé), a priority, and an automatic "
    "<b>under-warranty</b> determination read from the linked equipment. Parts "
    "consumed on a ticket can decrement stock. <b>Contrats de maintenance</b> "
    "are recurring preventive contracts with renewal tracking.", body_l))
story.append(connects(
    "Equipment is created by the <b>Installations</b> checklist · warranty is "
    "computed from <b>Stock</b> product warranty + install date · tickets can "
    "consume <b>Stock</b> parts · SAV load & costs feed <b>Reporting</b>."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Trust the equipment registry — because serials were captured on site, you "
    "already know what's installed and whether it's under warranty.",
    "Open a ticket for every customer issue; let the system tell you "
    "warranty status instead of digging through paperwork.",
    "Use maintenance contracts for recurring clients so renewals don't slip.",
    "Internal repair costs stay internal — they never appear on a "
    "client-facing report.",
]))
story.append(Spacer(1, 6))

# ---- 4.8 REPORTING
module("4.8", "Reporting, Dashboards &amp; the Activity Journal",
       "Menu “Rapports” · /reporting · /reporting/balance-agee · /journal",
       "Your cockpit — the numbers that tell you how the business is doing.")
story.append(Paragraph(
    "Reporting reads across every other module (it stores no data of its own) "
    "and presents it role-filtered: a <b>dashboard</b> with KPIs and charts, a "
    "<b>pipeline</b> funnel with weighted forecast, sales / stock / service "
    "reports (exportable to Excel), an <b>aged-balance</b> view, client "
    "statements, and admin-only insights — recurring revenue, "
    "<b>job-costing/margins</b> (using internal buy prices) and "
    "<b>commissions</b>. A separate <b>Journal</b> is the activity log: who "
    "did what, when — every create/update/delete/login, bucketed by hour and "
    "day. It is visible only to roles you grant the journal permission "
    "(Directeur by default).", body_l))
story.append(connects(
    "Aggregates <b>CRM</b>, <b>Ventes</b>, <b>Stock</b>, <b>Installations</b> "
    "and <b>SAV</b> · margins read internal <b>Stock</b> buy prices · the "
    "Journal records actions from every module."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Open the dashboard each morning — it's the fastest read on pipeline, "
    "cash owed and jobs in flight.",
    "Watch the <b>aged balance</b> weekly to catch slow payers early.",
    "Use job-costing to see real margins per job (only you and admins see "
    "this) and commissions to settle sales pay.",
    "Use the Journal when you need to know exactly who changed something.",
]))
story.append(Spacer(1, 6))

# ---- 4.9 PARAMETRES / ROLES / CUSTOMFIELDS
module("4.9", "Settings — Company, Templates, Statuses, Users &amp; Roles",
       "Menu “Paramètres” · /parametres · /admin/users · /admin/roles",
       "The control room — set this up once, the whole system follows.")
story.append(Paragraph(
    "Paramètres is where you configure the company so everything downstream is "
    "correct: legal identity and Moroccan IDs (ICE, IF, RC, patente, CNSS, "
    "RIB), branding (logo, signature, brand colour), default lead owner and "
    "default installer, and the quote-engine knobs — payment terms, validity "
    "days, VAT rates, ROI constants, max discount and the discount-approval "
    "threshold, agricole pump hours. You also manage <b>WhatsApp message "
    "templates</b> (French + Darija for devis / facture / relance), per-company "
    "<b>status labels</b>, <b>custom fields</b> (extra fields on leads, "
    "clients, products with no developer needed), commission mode, the "
    "referral program, and toggles like the silent DGI export. Every settings "
    "change is itself audited. <b>Users</b> and <b>Roles</b> are managed in "
    "the admin screens.", body_l))
story.append(connects(
    "Feeds identity & terms onto every <b>Ventes</b> document · templates "
    "drive <b>WhatsApp</b> delivery · roles gate what every module shows · "
    "custom fields appear in <b>CRM</b> and <b>Stock</b>."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Do this first: fill the company profile (legal IDs, RIB, logo, "
    "signature) — these print on quotes and invoices.",
    "Set your VAT rates, payment terms, validity, max discount and approval "
    "threshold so quotes are correct and discounts need your sign-off above "
    "the limit.",
    "Edit the WhatsApp templates in your own words (FR + Darija).",
    "Add custom fields when you need to track something extra — no code, no "
    "waiting.",
]))
story.append(Spacer(1, 6))

# ---- 4.10 NOTIFICATIONS + AUTOMATION
module("4.10", "Notifications &amp; Automation",
       "Header bell · /parametres/notifications · Settings → “Automatisations”",
       "The system nudging you, and doing repetitive steps for you.")
story.append(Paragraph(
    "<b>Notifications</b> surface important events — a lead assigned to you, a "
    "quote accepted, a job to plan, an invoice overdue — in an in-app bell, and "
    "optionally by WhatsApp, email or web push. Each person tunes which events "
    "reach them and on which channel. Daily/weekly digests can summarise the "
    "day's work. <b>Automation</b> is a no-code rules engine: “when X happens, "
    "do Y” (with an optional owner-approval step), every run logged. It's "
    "opt-in and best-effort — it never blocks the action that triggered it.", body_l))
story.append(connects(
    "Listens to events across <b>CRM/Ventes/Installations/SAV</b> · sends via "
    "the same <b>WhatsApp/email</b> channels Settings configures."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Set your notification preferences so the bell shows what matters to you "
    "and stays quiet on what doesn't.",
    "Turn on the daily/weekly digest for you and Meryem to start the day with "
    "a plan.",
    "Add automation rules cautiously, one at a time, and review their run log "
    "— keep an approval step on anything that touches money.",
]))
story.append(Spacer(1, 6))

# ---- 4.11 AI
module("4.11", "AI Assistant — OCR &amp; Ask-Your-Data",
       "Menu “IA” · /ia/ocr · /ia/agent",
       "Read bills by photo, and ask your database in plain language.")
story.append(Paragraph(
    "Two AI tools, both login-protected and only active when their API keys "
    "are set. <b>OCR</b> reads a photographed bill or invoice and turns it into "
    "structured data (useful for capturing a prospect's electricity bill or a "
    "supplier delivery). The <b>Agent</b> answers questions about your own "
    "data in natural language — it writes a read-only query, scoped strictly to "
    "your company, and shows you the answer. It can only read, never change "
    "anything, and never exposes buy prices/margins.", body_l))
story.append(connects(
    "OCR feeds <b>CRM</b> energy profiles and <b>Stock</b> receptions · the "
    "Agent reads (read-only) across all your modules, company-scoped."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Use OCR to capture bills instead of typing them.",
    "Ask the Agent things like “how many quotes are awaiting acceptance?” "
    "instead of building a report — it's faster for ad-hoc questions.",
    "These need API keys configured; if a screen says it's unavailable, the "
    "key isn't set yet.",
]))
story.append(Spacer(1, 6))

# ---- 4.12 PUBLIC API / WEBHOOKS / MONITORING / IMPORT
module("4.12", "Connections — Public API, Webhooks, Monitoring &amp; Imports",
       "Settings → “API &amp; Webhooks” · /production · /stock/ocr-import · imports",
       "How TAQINOR OS talks to the outside world and ingests bulk data.")
story.append(Paragraph(
    "A read-only <b>public API</b> (scoped API keys, company-limited, never buy "
    "prices) and <b>webhooks</b> (signed notifications on lead.created, "
    "devis.accepted, chantier.completed, facture.paid) let other tools "
    "integrate — for example your website pushing leads in. <b>Monitoring</b> "
    "can record system production yields and raise an under-performance flag "
    "(optionally auto-opening a SAV ticket). <b>Imports</b> bring in leads, "
    "clients or products from CSV/XLSX in a safe two-step way: a dry-run "
    "preview, then a create-only commit that skips duplicates.", body_l))
story.append(connects(
    "Website → <b>CRM</b> leads via webhook · API exposes <b>CRM/Ventes/"
    "Installations</b> read-only · Monitoring under-performance → <b>SAV</b> "
    "ticket · Imports populate <b>CRM</b> and <b>Stock</b>."))
story.append(Spacer(1, 5))
story.append(callout_box([
    "Use the two-step import to load existing leads/clients/products — always "
    "review the dry-run before committing.",
    "Issue an API key only when a real integration needs it; each is scoped "
    "and revocable.",
    "Webhook secrets are set by you in the dashboard — treat them like "
    "passwords.",
]))
story.append(PageBreak())

# ====================================================== 5. RULES
story.append(Paragraph("5", h1_num))
story.append(Paragraph("The rules you must never break", h1))
story.append(Divider())
story.append(Spacer(1, 6))
story.append(Paragraph(
    "These are the founder's standing rules baked into the system. They protect "
    "your money, your data and your reputation. Keep to them and the system "
    "keeps its guarantees.", lead_in))
rules = [
    ("One quote-PDF path only", "Client quote PDFs come <b>only</b> from the "
     "quote generator and its “/proposal” engine. Never build a quote PDF by "
     "any other route — that's how buy prices stay off the page and every "
     "quote stays consistent."),
    ("Buy prices are never client-facing", "Your purchase prices, margins, "
     "costs and commissions appear only on internal, admin-only screens — never "
     "on any quote, invoice or document a client receives. The system enforces "
     "this; don't try to work around it."),
    ("Pipeline stages are fixed", "The funnel stages (Nouveau, Contacté, Devis "
     "envoyé, Relance, Signé, Froid) are the canonical set. Don't invent or "
     "rename stages; if you need a change, it's a deliberate decision, not an "
     "ad-hoc one."),
    ("Campaigns are born paused", "Any advertising campaign created through the "
     "system starts <b>paused</b> — it never goes live automatically. You turn "
     "it on deliberately."),
    ("Accounting integration is API-only", "Any future accounting/Odoo "
     "integration writes only through the official API — never directly into a "
     "database. This keeps your books trustworthy."),
    ("Scraping is gated", "Any data scraping never runs from personal accounts "
     "and requires a written risk note plus your explicit approval before the "
     "first run."),
]
for t, d in rules:
    story.append(Paragraph(
        f'<font color="{BRASS.hexval()}">▸</font> <b>{t}.</b> {d}',
        S("rule", parent=body_l, spaceAfter=7)))
story.append(Spacer(1, 4))
story.append(callout_box([
    "You don't have to police most of this by hand — the software enforces it. "
    "The one habit that's on you: always quote through the generator, and "
    "never keep a side-spreadsheet of prices or stages that competes with the "
    "system.",
], title="IN PRACTICE", fill=CARD, bar=AZUR))
story.append(PageBreak())

# ====================================================== 6. RHYTHM
story.append(Paragraph("6", h1_num))
story.append(Paragraph("Your operating rhythm", h1))
story.append(Divider())
story.append(Spacer(1, 6))
story.append(Paragraph(
    "A simple cadence keeps the conveyor belt moving and the data trustworthy. "
    "Adapt it to your team, but keep the shape.", lead_in))

cadence = [
    ("EACH DAY", GREEN, [
        "Open the <b>dashboard</b> — read pipeline, cash owed, jobs in flight.",
        "Capture every new prospect as a <b>lead</b>; reply to the bell's "
        "notifications.",
        "Move quotes forward; mark accepted ones <b>accepté</b> (this signs "
        "the lead).",
        "Record every <b>payment</b> received today.",
        "Technicians work their day from <b>“Ma journée”</b> and update "
        "intervention status + checklists on site.",
    ]),
    ("EACH WEEK", AZUR, [
        "Review the <b>pipeline</b> and chase leads with a due relance.",
        "Check the <b>aged balance</b> and let relances chase late invoices.",
        "Review open <b>chantiers</b> and <b>SAV tickets</b>; reassign as "
        "needed.",
        "Check <b>low-stock</b> alerts and raise supplier purchase orders.",
    ]),
    ("EACH MONTH", BRASS, [
        "Review <b>margins (job-costing)</b> and <b>commissions</b>.",
        "Reconcile stock counts (logged adjustments only).",
        "Review loss reasons (Perdu) and conversion — tune your sales motion.",
        "Confirm company settings, VAT and templates are still right; add "
        "users/roles as the team changes.",
    ]),
]
for head, col, items in cadence:
    story.append(Spacer(1, 2))
    story.append(Paragraph(head, S("cad", fontName="Helvetica-Bold",
                                   fontSize=9.5, leading=12,
                                   textColor=colors.white)))
    # colored header bar
    bar = Table([[Paragraph(
        f'<font color="white"><b>{head}</b></font>',
        S("cadh", fontSize=9.5, leading=12))]], colWidths=[None])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), col),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story[-1] = bar  # replace the placeholder paragraph
    story.append(Spacer(1, 3))
    story.append(blist(items))
    story.append(Spacer(1, 4))
story.append(PageBreak())

# ====================================================== 7. SAFETY
story.append(Paragraph("7", h1_num))
story.append(Paragraph("What protects you", h1))
story.append(Divider())
story.append(Spacer(1, 6))
story.append(blist([
    "<b>Your data is isolated.</b> Everything is stamped with your company and "
    "invisible to anyone else on the platform — automatically, on every record.",
    "<b>Everything is audited.</b> The Journal records who did what and when "
    "across all modules; settings changes are logged separately.",
    "<b>Releases are reversible.</b> The live system can be rolled back to its "
    "previous state if an update ever misbehaves — nothing is one-way.",
    "<b>Sensitive numbers are walled off.</b> Buy prices, margins, costs and "
    "commissions are visible only to the roles you allow and never leak onto "
    "client documents.",
    "<b>Numbering can't collide.</b> Quote and invoice references are assigned "
    "safely even under load, so two documents never share a number.",
    "<b>Quotes never lose your data.</b> The generator never rejects a typed "
    "number, and inbound website leads are always captured raw even before "
    "they're processed.",
]))
story.append(Spacer(1, 6))
story.append(callout_box([
    "Because of all this, the right instinct when something looks off is to "
    "<b>fix it in the system</b> (correct the lead/quote/stock and let it flow "
    "forward), not to patch around it in a spreadsheet. The system remembers; "
    "the spreadsheet drifts.",
], title="WHY THIS MATTERS TO YOU", fill=BRASS_LT, bar=BRASS))
story.append(PageBreak())

# ====================================================== 8. SCREEN MAP
story.append(Paragraph("8", h1_num))
story.append(Paragraph("Quick reference — screen map", h1))
story.append(Divider())
story.append(Spacer(1, 6))
story.append(Paragraph(
    "The main screens and what you go there to do.", body_l))
screens = [
    ("CRM", "/crm/leads", "Capture & work leads; keep stages and relances current"),
    ("CRM", "/crm", "Client records"),
    ("Ventes", "/ventes/devis/nouveau", "Create a quote (the only quote path)"),
    ("Ventes", "/ventes/devis", "Quote list; generate PDFs; accept quotes"),
    ("Ventes", "/ventes/bons-commande", "Orders; mark delivered (moves stock)"),
    ("Ventes", "/ventes/factures", "Invoices & payments"),
    ("Ventes", "/ventes/relances", "Chase unpaid invoices"),
    ("Chantiers", "/chantiers", "Installation projects; status & handover PDFs"),
    ("Chantiers", "/interventions", "Site visits kanban; assign technicians"),
    ("Chantiers", "/ma-journee", "Technician's day view (on site)"),
    ("Chantiers", "/outillage", "Durable field tools"),
    ("SAV", "/equipements", "Installed-equipment registry & warranty"),
    ("SAV", "/sav", "Support tickets"),
    ("SAV", "/sav/contrats", "Maintenance contracts"),
    ("Stock", "/stock", "Product catalogue & quantities"),
    ("Stock", "/stock/bons-commande-fournisseur", "Supplier purchase orders"),
    ("Rapports", "/reporting", "Dashboard & KPIs"),
    ("Rapports", "/reporting/balance-agee", "Aged balance (who owes what)"),
    ("Journal", "/journal", "Activity log (who did what)"),
    ("IA", "/ia/ocr", "Read a bill/invoice by photo"),
    ("IA", "/ia/agent", "Ask your data in plain language"),
    ("Paramètres", "/parametres", "Company profile, VAT, templates, settings"),
    ("Admin", "/admin/users", "Add people & assign roles"),
    ("Admin", "/admin/roles", "Define roles & permissions"),
]
rows = [[Paragraph("<b>Module</b>", small),
         Paragraph("<b>Screen</b>", small),
         Paragraph("<b>Go there to…</b>", small)]]
for m, u, d in screens:
    rows.append([
        Paragraph(m, S("sm_m", fontName="Helvetica-Bold", fontSize=8.4,
                       leading=11, textColor=NUIT2)),
        Paragraph(u, S("sm_u", fontName="Helvetica", fontSize=8.2, leading=11,
                       textColor=AZUR)),
        Paragraph(d, S("sm_d", fontName="Helvetica", fontSize=8.4, leading=11,
                       textColor=INK)),
    ])
smt = Table(rows, colWidths=[24 * mm, 56 * mm, None], repeatRows=1)
smt.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("BACKGROUND", (0, 0), (-1, 0), NUIT),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CARD]),
]))
story.append(smt)
story.append(Spacer(1, 12))
story.append(HRFlowable(width="100%", thickness=0.6, color=RULE))
story.append(Spacer(1, 6))
story.append(Paragraph(
    "This guide is a living document — it mirrors the system as built "
    "(docs/CODEMAP.md). When the product gains a module, regenerate it so the "
    "team always has an accurate map.", small))

doc.build(story)
print("WROTE", OUT)

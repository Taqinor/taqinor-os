# -*- coding: utf-8 -*-
# flake8: noqa
"""Générateur de FACTURE premium TAQINOR (une page A4).

Réutilise EN LECTURE SEULE le design system du moteur de devis vendored
(``apps/ventes/quote_engine/generate_devis_premium.py``) : tokens couleurs,
polices embarquées, logo recoloré, formatage monétaire et rendu WeasyPrint.
C'est un chemin de code SÉPARÉ du devis (règle #4 CLAUDE.md) : le moteur de
devis n'est jamais modifié ni utilisé pour rendre autre chose qu'un devis.

Usage (dans l'image docker prod, Python 3.11 + WeasyPrint) :

    docker run --rm -v "<repo>:/repo" erp-agentique-django_core:latest \
        python /repo/tools/facture/generate_facture.py \
        /repo/tools/facture/<client>.json /repo/tools/facture/out/<nom>.pdf

Les montants du JSON sont saisis en TTC (culture maison) ; le HT et la TVA
sont recalculés par ligne (Decimal, arrondi bancaire commercial 2 déc.) et la
TVA est ventilée par taux (10 % modules PV / 20 % le reste — art. 145 CGI).
"""

import json
import pathlib
import sys
from decimal import Decimal, ROUND_HALF_UP

HERE = pathlib.Path(__file__).resolve().parent
ENGINE_DIR = HERE.parent.parent / "backend" / "django_core" / "apps" / "ventes" / "quote_engine"
sys.path.insert(0, str(ENGINE_DIR))

import generate_devis_premium as g  # noqa: E402  (design system, lecture seule)

CENT = Decimal("0.01")


def r2(x):
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


# ── Montant en toutes lettres (français) ────────────────────────────────────
_UNITS = ["", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit",
          "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze",
          "seize", "dix-sept", "dix-huit", "dix-neuf"]
_TENS = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante",
         60: "soixante", 70: "soixante-dix", 80: "quatre-vingt",
         90: "quatre-vingt-dix"}


def _under100(n):
    if n < 20:
        return _UNITS[n]
    t, u = divmod(n, 10)
    if t in (7, 9):
        rest = n - (t - 1) * 10
        sep = " et " if rest == 11 and t == 7 else "-"
        return _TENS[(t - 1) * 10] + sep + _UNITS[rest]
    word = _TENS[t * 10]
    if u == 0:
        return word + ("s" if t == 8 else "")
    sep = " et " if u == 1 and t != 8 else "-"
    return word + sep + _UNITS[u]


def _under1000(n):
    h, rest = divmod(n, 100)
    if h == 0:
        return _under100(rest)
    word = "cent" if h == 1 else _UNITS[h] + " cent" + ("s" if rest == 0 else "")
    return word + (" " + _under100(rest) if rest else "")


def _int_words(n):
    if n == 0:
        return "zéro"
    parts = []
    millions, rest = divmod(n, 1_000_000)
    if millions:
        parts.append("un million" if millions == 1 else _under1000(millions) + " millions")
    thousands, units = divmod(rest, 1000)
    if thousands:
        parts.append("mille" if thousands == 1 else _under1000(thousands) + " mille")
    if units:
        parts.append(_under1000(units))
    return " ".join(parts)


def montant_en_lettres(amount):
    amount = r2(amount)
    dh = int(amount)
    cts = int((amount - dh) * 100)
    s = _int_words(dh) + (" dirham" if dh == 1 else " dirhams")
    if cts:
        s += " et " + _int_words(cts) + (" centime" if cts == 1 else " centimes")
    return s


def _fmt_pu(pu4):
    """Format français du P.U. HT : 2 décimales si exact, sinon 4."""
    pu2 = pu4.quantize(CENT, rounding=ROUND_HALF_UP)
    if pu4 == pu2:
        return f"{pu2:,.2f}".replace(",", " ").replace(".", ",")
    return f"{pu4:,.4f}".replace(",", " ").replace(".", ",")


# ── Calcul des lignes (TTC saisi → HT/TVA recalculés) ──────────────────────
def compute(data):
    rows, total_ht = [], Decimal("0")
    tva_by_rate = {}
    for li in data["lignes"]:
        qty = Decimal(str(li["qte"]))
        rate = Decimal(str(li["tva_pct"])) / 100
        total_ttc = r2(Decimal(str(li["pu_ttc"])) * qty)
        ligne_ht = r2(total_ttc / (1 + rate))
        # P.U. HT affiché en 4 décimales quand la division TTC/(1+taux) ne
        # tombe pas juste : ainsi P.U. × Qté redonne exactement le Total HT
        # imprimé (arrondi 2 déc.) — un client ou un vérificateur qui
        # multiplie les colonnes retombe sur le montant de la ligne.
        pu4 = (Decimal(str(li["pu_ttc"])) / (1 + rate)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP)
        rows.append({
            "designation": li["designation"],
            "note": li.get("note", ""),
            "marque": li.get("marque", ""),
            "qte": li["qte"],
            "pu_ht_aff": _fmt_pu(pu4),
            "tva_pct": li["tva_pct"],
            "total_ht": ligne_ht,
        })
        total_ht += ligne_ht
        tva_by_rate[li["tva_pct"]] = tva_by_rate.get(li["tva_pct"], Decimal("0")) + (total_ttc - ligne_ht)
    total_tva = sum(tva_by_rate.values(), Decimal("0"))
    total_ttc = total_ht + total_tva
    avance = r2(data.get("acompte_regle", 0))
    reste = total_ttc - avance
    return rows, total_ht, tva_by_rate, total_tva, total_ttc, avance, reste


# ── Construction HTML ───────────────────────────────────────────────────────
def _kicker(text, color=None):
    c = color or g.CG4
    return ('<div style="font-size:6.5pt;font-weight:700;letter-spacing:1.2px;'
            f'text-transform:uppercase;color:{c};margin-bottom:4px;">{text}</div>')


def _badge(marque):
    if not marque:
        return '<span style="color:' + g.CG4 + ';">—</span>'
    try:
        return g.badge(marque)
    except Exception:
        return ('<span style="display:inline-block;background:' + g.CNM + ';color:#fff;'
                'border-radius:8px;padding:1px 7px;font-size:6.3pt;font-weight:600;">'
                + marque + '</span>')


def _tot(label, value, size="8.5pt", weight="600", color=None, pad="3px"):
    c = color or g.CG7
    return (f'<tr><td style="text-align:right;padding:{pad} 10px {pad} 0;font-size:{size};'
            f'font-weight:{weight};color:{c};">{label}</td>'
            f'<td style="text-align:right;width:118px;padding:{pad} 0;font-size:{size};'
            f'font-weight:{weight};color:{c};white-space:nowrap;">{value}</td></tr>')


def page_facture(data):
    rows, total_ht, tva_by_rate, total_tva, total_ttc, avance, reste = compute(data)

    numero = g._esc(data["numero"])
    date_emission = g._esc(data["date_emission"])
    devis_ref = g._esc(data["devis_ref"])
    devis_date = g._esc(data["devis_date"])
    client = data["client"]
    inst = data["installation"]

    logo = g.logo_html("64px")

    # Lignes du tableau (zébrage calculé côté Python — pas de :nth-child)
    body_rows = []
    for i, row in enumerate(rows):
        bg = "#FFFFFF" if i % 2 == 0 else g.CG1
        desig = '<div style="font-weight:700;color:' + g.CN + ';font-size:8pt;">' + g._esc(row["designation"]) + "</div>"
        if row["note"]:
            desig += ('<div style="color:' + g.CG4 + ';font-size:6.5pt;margin-top:1px;">– '
                      + g._esc(row["note"]) + "</div>")
        body_rows.append(
            f'<tr style="background:{bg};">'
            f'<td style="padding:8px 8px;border-bottom:1px solid {g.CG2};">{desig}</td>'
            f'<td style="padding:8px 8px;border-bottom:1px solid {g.CG2};text-align:center;">{_badge(g._esc(row["marque"]))}</td>'
            f'<td style="padding:8px 8px;border-bottom:1px solid {g.CG2};text-align:center;color:{g.CG7};font-size:8pt;">{row["qte"]}</td>'
            f'<td style="padding:8px 8px;border-bottom:1px solid {g.CG2};text-align:right;color:{g.CG7};font-size:8pt;">{row["pu_ht_aff"]}</td>'
            f'<td style="padding:8px 8px;border-bottom:1px solid {g.CG2};text-align:center;color:{g.CG4};font-size:7pt;">{row["tva_pct"]}%</td>'
            f'<td style="padding:8px 8px;border-bottom:1px solid {g.CG2};text-align:right;color:{g.CN};font-weight:600;font-size:8pt;">{g._fmt2(row["total_ht"])}</td>'
            "</tr>"
        )
    table_rows = "".join(body_rows)

    # Chaîne des totaux — TVA ventilée par taux (art. 145 CGI)
    tva_lines = "".join(
        _tot(f"TVA {pct} % (base {g._fmt2(sum(r['total_ht'] for r in rows if r['tva_pct'] == pct))} MAD)",
             g._fmt2(v) + " MAD")
        for pct, v in sorted(tva_by_rate.items())
    )

    ttc_lettres = montant_en_lettres(total_ttc)
    reste_lettres = montant_en_lettres(reste)
    avance_fmt = g._fmt2(avance)

    mode_paiement = g._esc(data.get("mode_paiement", "Virement bancaire"))

    return f"""
<div class="page" style="position:relative;display:block;">
  <div style="position:absolute;top:0;left:0;right:0;bottom:76px;overflow:hidden;">

    <!-- Bandeau en-tête -->
    <div style="background:{g.CN};padding:22px 24px 20px;">
      <table style="width:100%;border-collapse:collapse;"><tr>
        <td style="vertical-align:middle;">{logo}</td>
        <td style="vertical-align:middle;text-align:right;">
          <div style="font-size:16pt;font-weight:800;color:#FFFFFF;letter-spacing:.5px;">
            FACTURE <span style="color:{g.CA};">N&deg;&nbsp;{numero}</span>
          </div>
          <div style="font-size:8pt;color:rgba(255,255,255,.65);margin-top:4px;">
            Date d&rsquo;&eacute;mission&nbsp;: {date_emission}
          </div>
          <div style="font-size:8pt;color:rgba(255,255,255,.85);font-weight:600;">
            R&eacute;f. devis N&deg;&nbsp;{devis_ref} du {devis_date}
          </div>
        </td>
      </tr></table>
    </div>

    <!-- Client + installation facturée -->
    <div style="background:{g.CG1};padding:16px 24px;border-bottom:1px solid {g.CG2};">
      <table style="width:100%;border-collapse:collapse;table-layout:fixed;"><tr>
        <td style="width:44%;vertical-align:top;">
          {_kicker("Factur&eacute; &agrave;")}
          <div style="font-size:11pt;font-weight:700;color:{g.CN};">{g._esc(client["nom"])}</div>
          <div style="font-size:8pt;color:{g.CG7};margin-top:2px;">{g._esc(client["adresse"])}</div>
          <div style="font-size:8pt;color:{g.CG7};">{g._esc(client.get("tel", ""))}</div>
        </td>
        <td style="width:4%;"></td>
        <td style="width:52%;vertical-align:top;">
          {_kicker("Installation factur&eacute;e")}
          <div style="font-size:9.5pt;font-weight:700;color:{g.CN};">{g._esc(inst["titre"])}</div>
          <div style="font-size:8pt;color:{g.CG7};margin-top:2px;">{g._esc(inst["detail"])}</div>
          <div style="font-size:8pt;color:{g.CG7};">{g._esc(inst["site_line"])}</div>
        </td>
      </tr></table>
    </div>

    <!-- Tableau des lignes -->
    <div style="margin:20px 24px 0;">
      {_kicker("D&eacute;tail de la facturation", g.CN)}
      <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
        <colgroup>
          <col style="width:40%"><col style="width:13%"><col style="width:6%">
          <col style="width:15%"><col style="width:7%"><col style="width:19%">
        </colgroup>
        <tr style="background:{g.CN};">
          <th style="padding:7px 8px;color:#fff;font-weight:700;font-size:7.5pt;text-transform:uppercase;letter-spacing:.5px;text-align:left;">D&eacute;signation</th>
          <th style="padding:7px 8px;color:#fff;font-weight:700;font-size:7.5pt;text-transform:uppercase;letter-spacing:.5px;text-align:center;">Marque</th>
          <th style="padding:7px 8px;color:#fff;font-weight:700;font-size:7.5pt;text-transform:uppercase;letter-spacing:.5px;text-align:center;">Qt&eacute;</th>
          <th style="padding:7px 8px;color:#fff;font-weight:700;font-size:7.5pt;text-transform:uppercase;letter-spacing:.5px;text-align:right;">P.U. HT (MAD)</th>
          <th style="padding:7px 8px;color:#fff;font-weight:700;font-size:7.5pt;text-transform:uppercase;letter-spacing:.5px;text-align:center;">TVA</th>
          <th style="padding:7px 8px;color:#fff;font-weight:700;font-size:7.5pt;text-transform:uppercase;letter-spacing:.5px;text-align:right;">Total HT (MAD)</th>
        </tr>
        {table_rows}
      </table>
    </div>

    <!-- Totaux -->
    <table style="width:100%;border-collapse:collapse;table-layout:fixed;margin-top:18px;"><tr>
      <td style="width:40%;"></td>
      <td style="width:60%;padding-right:24px;">
        <div style="background:{g.CAL};border-top:2px solid {g.CA};padding:10px 14px 12px;">
          <table style="width:100%;border-collapse:collapse;">
            {_tot("Total HT", g._fmt2(total_ht) + "&nbsp;MAD")}
            {tva_lines}
            {_tot("Total TTC", g._fmt2(total_ttc) + "&nbsp;MAD", size="9.5pt", weight="700", color=g.CN, pad="5px")}
            {_tot("Acompte d&eacute;j&agrave; r&eacute;gl&eacute;", "&minus;&nbsp;" + avance_fmt + "&nbsp;MAD", color=g.CGR)}
          </table>
          <div style="background:{g.CN};margin-top:8px;padding:8px 12px;">
            <table style="width:100%;border-collapse:collapse;"><tr>
              <td style="font-size:9pt;font-weight:800;color:#fff;letter-spacing:1px;">RESTE &Agrave; PAYER</td>
              <td style="text-align:right;font-size:14pt;font-weight:800;color:{g.CA};white-space:nowrap;">{g._fmt2(reste)}&nbsp;MAD</td>
            </tr></table>
          </div>
        </div>
      </td>
    </tr></table>

    <!-- Arrêté en toutes lettres -->
    <div style="margin:16px 24px 0;font-size:8pt;color:{g.CG7};line-height:1.55;">
      Arr&ecirc;t&eacute;e la pr&eacute;sente facture &agrave; la somme de&nbsp;:
      <strong>{ttc_lettres} TTC</strong>.<br>
      Soit, apr&egrave;s d&eacute;duction de l&rsquo;acompte d&eacute;j&agrave; r&eacute;gl&eacute;
      de {avance_fmt}&nbsp;MAD, un net &agrave; payer de&nbsp;:
      <strong>{reste_lettres}</strong>.
    </div>

    <!-- Règlement + cachet -->
    <table style="width:100%;border-collapse:collapse;table-layout:fixed;margin-top:16px;"><tr>
      <td style="width:24px;"></td>
      <td style="width:58%;vertical-align:top;">
        <div style="background:{g.CG1};border:1px solid {g.CG2};padding:10px 12px;">
          {_kicker("R&egrave;glement du solde")}
          <div style="font-size:8pt;color:{g.CG7};margin-bottom:3px;">Mode de r&egrave;glement&nbsp;: <strong>{mode_paiement}</strong></div>
          <div style="font-size:7.5pt;color:{g.CG7};">{g.ENT_RIB_LINE}</div>
          <div style="font-size:7.5pt;color:{g.CG4};margin-top:3px;">R&eacute;f&eacute;rence &agrave; rappeler&nbsp;: {numero}</div>
        </div>
      </td>
      <td style="width:3%;"></td>
      <td style="vertical-align:top;">
        <div style="border:1px solid {g.CG2};padding:10px 12px;height:96px;">
          {_kicker("Cachet &amp; signature TAQINOR")}
        </div>
      </td>
      <td style="width:24px;"></td>
    </tr></table>

    <div style="margin:22px 24px 0;padding-top:10px;border-top:1px solid {g.CG2};text-align:center;font-size:8pt;color:{g.CG4};font-style:italic;">
      Nous vous remercions de votre confiance.
    </div>
  </div>

  <!-- Pied de page fixe -->
  <div style="position:absolute;left:0;right:0;bottom:0;background:{g.CN};padding:6px 24px 5px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
      <div style="font-size:9pt;font-weight:800;color:{g.CA};letter-spacing:1px;">{g.ENT_NOM_MARQUE}</div>
      <div style="font-size:7pt;color:#888;text-align:center;">{g.ENT_CONTACT_LINE}</div>
      <div style="font-size:7pt;color:#888;">Facture N&deg;&nbsp;{numero}</div>
    </div>
    <div style="font-size:7.5px;color:#888;text-align:center;font-style:italic;">{legal_line(data)}</div>
  </div>
</div>
"""


def legal_line(data):
    """Ligne légale du pied de page : identité Taqinor + identifiants
    fiscaux additionnels (IF / TP / CNSS) quand ils sont fournis dans le JSON
    — l'art. 145 CGI les exige ; les renseigner dès qu'ils sont connus."""
    line = g.ENT_LEGAL_LINE
    extra = data.get("entreprise", {})
    parts = []
    if extra.get("if_fiscal"):
        parts.append("IF " + g._esc(extra["if_fiscal"]))
    if extra.get("taxe_professionnelle"):
        parts.append("TP " + g._esc(extra["taxe_professionnelle"]))
    if extra.get("cnss"):
        parts.append("CNSS " + g._esc(extra["cnss"]))
    if parts:
        line = line + " &middot; " + " &middot; ".join(parts)
    return line


def build_html(data):
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            + g.CSS + "</style></head><body>" + page_facture(data) + "</body></html>")


def main():
    data_path, out_path = sys.argv[1], sys.argv[2]
    data = json.loads(pathlib.Path(data_path).read_text(encoding="utf-8"))
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    html = build_html(data)
    g._render_pdf_weasyprint(html, str(out_path))
    print("OK", out_path)


if __name__ == "__main__":
    main()

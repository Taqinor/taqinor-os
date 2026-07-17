# flake8: noqa
"""quote_engine commercial — PAGE 3 (confiance + étapes + signature).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``c3-``.
"""


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]
    theme = ctx["theme"]
    ident = ctx.get("ident") or {}
    brand = ident.get("brand_name") or "TAQINOR"

    navy = C["navy"]
    gold = C["gold"]
    green = C["green"]
    green_bg = C.get("green_bg", "#E8F5EC")
    ink = C.get("ink", "#1F2937")
    muted = C.get("muted", "#6B7280")
    muted_2 = C.get("muted_2", "#9BA3AE")
    line = C.get("line", "#E5E7EB")
    line_soft = C.get("line_soft", "#EFF1F4")
    wash = C.get("wash", "#F7F9FC")

    f_display = fonts["display"]
    f_serif = fonts["serif"]
    f_sans = fonts["sans"]

    steps = [
        ("1", "Étude &amp; validation", "Dimensionnement, visite technique et validation du projet."),
        ("2", "Installation", "Pose des équipements par nos équipes, sans interrompre votre activité."),
        ("3", "Mise en service", "Raccordement, tests et réception — votre production démarre."),
        ("4", "Suivi &amp; O&amp;M", "Supervision temps réel + maintenance : performance garantie dans la durée."),
    ]
    steps_cells = ""
    for i, (n, t, s) in enumerate(steps):
        gap = '<td class="c3-sgap"></td>' if i < len(steps) - 1 else ""
        steps_cells += (
            f'<td class="c3-step"><div class="c3-step-n">{n}</div>'
            f'<div class="c3-step-t">{t}</div>'
            f'<div class="c3-step-s">{s}</div></td>{gap}')

    accepte_nom = (d.get("accepte_par_nom") or "").strip()
    date_accept = (d.get("date_acceptation") or "").strip()
    if accepte_nom and date_accept:
        sign_client = (f'<div class="c3-sign-name">{theme._esc(accepte_nom)}</div>'
                       f'<div class="c3-sign-date">Le {date_accept}</div>')
    else:
        sign_client = '<div class="c3-sign-blank">Nom, date &amp; « Bon pour accord »</div>'

    css = f"""
<style>
.c3-root{{font-family:{f_sans};color:{ink};width:210mm;min-height:283mm;
  padding:13mm 14mm 0 14mm;background:#fff;}}
.c3-root *{{box-sizing:border-box;}}
.c3-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{muted_2};font-weight:700;}}
.c3-sec{{font-family:{f_serif};font-weight:700;font-size:16pt;color:{navy};margin-top:2px;}}
.c3-steprow{{display:table;width:100%;margin-top:10px;border-spacing:0;}}
.c3-step{{display:table-cell;vertical-align:top;border:1px solid {line};
  border-top:4px solid {gold};border-radius:12px;padding:11px 12px;background:{wash};}}
.c3-sgap{{display:table-cell;width:9px;}}
.c3-step-n{{font-family:{f_display};font-size:19pt;color:{gold};line-height:1;}}
.c3-step-t{{font-size:8.5pt;font-weight:700;color:{navy};margin-top:4px;}}
.c3-step-s{{font-size:7pt;color:{muted};margin-top:4px;line-height:1.35;}}
.c3-h2{{font-family:{f_serif};font-weight:700;font-size:13pt;color:{navy};margin-top:16px;}}
.c3-warr{{margin-top:8px;border:1px solid {line};border-radius:12px;background:{wash};padding:11px 14px;}}
.c3-warr-row{{display:table;width:100%;border-spacing:0;}}
.c3-warr-c{{display:table-cell;vertical-align:top;text-align:center;padding:0 6px;}}
.c3-warr-v{{font-family:{f_display};font-size:16pt;color:{green};line-height:1;}}
.c3-warr-l{{font-size:7pt;color:{muted};margin-top:3px;}}
.c3-trust{{margin-top:14px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:linear-gradient(100deg,{green_bg},#fff 72%);
  padding:10px 14px;font-size:8.5pt;color:{ink};line-height:1.45;}}
.c3-trust b{{color:{navy};}}
.c3-sign{{margin-top:16px;display:table;width:100%;border-spacing:0;}}
.c3-sign-c{{display:table-cell;vertical-align:top;width:50%;border:1px solid {line};
  border-radius:12px;padding:12px 14px;}}
.c3-sign-gap{{display:table-cell;width:12px;}}
.c3-sign-h{{font-size:7.5pt;letter-spacing:1.4px;text-transform:uppercase;
  color:{muted};font-weight:700;}}
.c3-sign-box{{margin-top:8px;height:20mm;border:1px dashed {line};border-radius:8px;background:{wash};}}
.c3-sign-name{{margin-top:8px;font-size:11pt;color:{navy};font-weight:700;}}
.c3-sign-date{{font-size:8pt;color:{muted};margin-top:2px;}}
.c3-sign-blank{{margin-top:8px;font-size:8pt;color:{muted_2};font-style:italic;}}
.c3-sign-co{{font-size:8pt;color:{muted};margin-top:8px;}}
.c3-sign-co b{{color:{navy};}}
</style>
"""

    html = f"""{css}
<div class="c3-root">
  <div class="c3-kicker">Votre projet, étape par étape</div>
  <div class="c3-sec">Comment nous procédons</div>
  <div class="c3-steprow">{steps_cells}</div>

  <div class="c3-h2">Garanties</div>
  <div class="c3-warr">
    <div class="c3-warr-row">
      <div class="c3-warr-c"><div class="c3-warr-v">25 ans</div><div class="c3-warr-l">Performance panneaux</div></div>
      <div class="c3-warr-c"><div class="c3-warr-v">5-10 ans</div><div class="c3-warr-l">Onduleurs</div></div>
      <div class="c3-warr-c"><div class="c3-warr-v">10 ans</div><div class="c3-warr-l">Installation</div></div>
      <div class="c3-warr-c"><div class="c3-warr-v">O&amp;M</div><div class="c3-warr-l">Maintenance &amp; supervision</div></div>
    </div>
  </div>

  <div class="c3-trust">
    Un <b>interlocuteur unique</b> du devis à la mise en service, une <b>supervision
    temps réel</b> de votre production et un engagement de <b>performance</b> dans la durée.
  </div>

  <div class="c3-sign">
    <div class="c3-sign-c">
      <div class="c3-sign-h">Bon pour accord — Client</div>
      <div class="c3-sign-box"></div>
      {sign_client}
    </div>
    <div class="c3-sign-gap"></div>
    <div class="c3-sign-c">
      <div class="c3-sign-h">Pour {brand}</div>
      <div class="c3-sign-box"></div>
      <div class="c3-sign-co"><b>{brand}</b> &nbsp;·&nbsp; {ident.get('email','')} &nbsp;·&nbsp; {ident.get('phone','')}</div>
    </div>
  </div>
</div>
"""
    return html

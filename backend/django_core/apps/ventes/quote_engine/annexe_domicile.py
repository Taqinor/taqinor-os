"""AMOT23 (C-AMOT-021) / CAD122 — le CORPS de l'annexe de rétractation d'une
commande signée AU DOMICILE (loi 31-08, art. 45-50), en UNE fonction HTML
PURE partagée par le moteur legacy (``generate_devis_premium.page_annexe_domicile``)
et le gabarit résidentiel 3 pages (``residential/render``).

Aucun chiffre inventé : le délai vient de la loi (art. 49 et 50) ; les dates
restent à remplir à la main (art. 47 al. 2). Rendu seul, aucun statut
(règle #4) ; jamais une seconde voie de PDF : une page de plus du même
document, seulement quand le bon de commande porte ``signe_au_domicile``.
"""

#: Délai légal de rétractation d'un démarchage à domicile (loi 31-08, art. 49).
DELAI_RETRACTATION_DOMICILE_JOURS = 7

MENTIONS_ARTICLE_48 = (
    "Nom et adresse du vendeur, et nom du représentant qui vous a "
    "rendu visite.",
    "Désignation précise de la nature et des caractéristiques des "
    "biens ou services proposés.",
    "Conditions d&#8217;exécution du contrat, notamment les modalités "
    "et le délai de livraison.",
    "Prix global à payer et modalités de paiement.",
    "Faculté de renonciation, ainsi que ses conditions d&#8217;exercice, "
    "et de façon apparente le texte intégral des articles 49 et 50.",
)


def corps_annexe_domicile(*, ref, vendeur, couleurs) -> str:
    """Le corps (texte légal + mentions + formulaire détachable) de l'annexe.

    ``ref`` et ``vendeur`` sont déjà échappés par l'appelant ; ``couleurs`` =
    ``{navy, texte, muet, fond, filet}`` (chaque gabarit garde sa charte)."""
    c = couleurs
    cadre = (f'border:1px dashed {c["muet"]};border-radius:8px;'
             'padding:12px 14px;background:white;')
    mentions_html = "".join(
        f'<li style="margin-bottom:3px;">{m}</li>' for m in MENTIONS_ARTICLE_48)
    return f"""
    <div style="font-size:8pt;color:{c['texte']};line-height:1.5;margin-bottom:10px;">
      Cette commande a été signée à votre domicile. La loi
      n° 31-08 édictant des mesures de protection du consommateur vous
      ouvre un délai de rétractation de
      <strong>{DELAI_RETRACTATION_DOMICILE_JOURS} jours</strong> à
      compter de la commande. Pendant ce délai, <strong>aucun acompte ni
      aucun paiement ne peut être exigé ni encaissé</strong>
      (articles 49 et 50).
    </div>

    <div style="background:{c['fond']};border:1px solid {c['filet']};border-radius:7px;padding:9px 12px;margin-bottom:12px;">
      <div style="font-size:7.5pt;font-weight:700;color:{c['navy']};text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;">Mentions de l&#8217;article 48</div>
      <ul style="margin:0;padding-left:16px;font-size:7.5pt;color:{c['texte']};line-height:1.45;">{mentions_html}</ul>
    </div>

    <div style="font-size:7.5pt;color:{c['muet']};font-style:italic;margin-bottom:8px;">
      Détachez, complétez et renvoyez le formulaire ci-dessous si vous
      souhaitez renoncer à cette commande.
    </div>

    <div style="{cadre}">
      <div style="font-size:9pt;font-weight:700;color:{c['navy']};text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Formulaire détachable de rétractation</div>
      <div style="font-size:8pt;color:{c['texte']};line-height:1.9;">
        À l&#8217;attention de : <strong>{vendeur}</strong><br>
        Je soussigné(e) : _______________________________________________<br>
        Adresse : ____________________________________________________<br>
        déclare renoncer à la commande n° <strong>{ref}</strong>,
        signée le : ___/___/______<br>
        Fait à : _______________________ le : ___/___/______
      </div>
      <div style="display:flex;gap:18px;margin-top:10px;">
        <div style="flex:1;">
          <div style="border-bottom:1px solid {c['filet']};min-height:26px;"></div>
          <div style="font-size:7pt;color:{c['muet']};margin-top:3px;">Signature du client (de sa main)</div>
        </div>
      </div>
    </div>
"""

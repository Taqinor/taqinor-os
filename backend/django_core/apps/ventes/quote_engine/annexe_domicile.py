"""AMOT23 (C-AMOT-021) / CAD122 — le CORPS de l'annexe de rétractation d'une
commande signée AU DOMICILE (loi 31-08, art. 45-50), en UNE fonction HTML
PURE partagée par le moteur legacy (``generate_devis_premium.page_annexe_domicile``)
et le gabarit résidentiel 3 pages (``residential/render``).

Aucun chiffre inventé : le délai vient de la loi (art. 49 et 50) ; les dates
restent à remplir à la main (art. 47 al. 2).

AMOT52 (D-AMOT-1 = a) — chaque texte passe par ``i18n_labels`` (clés
``res_ret_*``) : le français y est le littéral EXACT d'hier (octet pour
octet), l'anglais et l'arabe suivent la langue du document. Rendu seul, aucun statut
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


def corps_annexe_domicile(*, ref, vendeur, couleurs, langue=None) -> str:
    """Le corps (texte légal + mentions + formulaire détachable) de l'annexe.

    ``ref`` et ``vendeur`` sont déjà échappés par l'appelant ; ``couleurs`` =
    ``{navy, texte, muet, fond, filet}`` (chaque gabarit garde sa charte).
    AMOT52 — ``langue`` (fr/en/ar, repli fr) choisit les textes du catalogue."""
    from . import i18n_labels

    def t(cle):
        return i18n_labels.libelle(cle, langue)
    c = couleurs
    cadre = (f'border:1px dashed {c["muet"]};border-radius:8px;'
             'padding:12px 14px;background:white;')
    mentions_html = "".join(
        f'<li style="margin-bottom:3px;">{t(f"res_ret_mention_{i}")}</li>'
        for i in range(1, len(MENTIONS_ARTICLE_48) + 1))
    return f"""
    <div style="font-size:8pt;color:{c['texte']};line-height:1.5;margin-bottom:10px;">
      {t("res_ret_intro").format(jours=DELAI_RETRACTATION_DOMICILE_JOURS)}
    </div>

    <div style="background:{c['fond']};border:1px solid {c['filet']};border-radius:7px;padding:9px 12px;margin-bottom:12px;">
      <div style="font-size:7.5pt;font-weight:700;color:{c['navy']};text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;">{t("res_ret_mentions_titre")}</div>
      <ul style="margin:0;padding-left:16px;font-size:7.5pt;color:{c['texte']};line-height:1.45;">{mentions_html}</ul>
    </div>

    <div style="font-size:7.5pt;color:{c['muet']};font-style:italic;margin-bottom:8px;">
      {t("res_ret_detachez")}
    </div>

    <div style="{cadre}">
      <div style="font-size:9pt;font-weight:700;color:{c['navy']};text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">{t("res_ret_formulaire")}</div>
      <div style="font-size:8pt;color:{c['texte']};line-height:1.9;">
        {t("res_ret_formulaire_corps").format(vendeur=vendeur, ref=ref)}
      </div>
      <div style="display:flex;gap:18px;margin-top:10px;">
        <div style="flex:1;">
          <div style="border-bottom:1px solid {c['filet']};min-height:26px;"></div>
          <div style="font-size:7pt;color:{c['muet']};margin-top:3px;">{t("res_ret_signature")}</div>
        </div>
      </div>
    </div>
"""

"""Libellés du document agricole ajoutés après le 27/10/2026 (session AGC).

Le catalogue commun ``i18n_labels.py`` ne grossit plus (guide des sessions
L3) : les nouvelles clés agricoles vivent ici, avec le même repli français que
``i18n_labels.libelle``. ``agricole/pages._t`` et ``agricole/onepage.py``
consultent ce catalogue d'abord, puis le catalogue commun.
"""

LIBELLES_AGRICOLE = {
    # AGC11 (D-AGC-6) — bloc argent non publiable mais dépense DÉCLARÉE : la
    # seule somme déclarée par le client, jamais une économie calculée.
    "agr_depense_declaree_neutre": {
        "fr": "Votre dépense actuelle déclarée : {mad} par an. L'économie "
              "sera chiffrée après la visite du point d'eau.",
        "en": "Your declared current spending: {mad} per year. The savings "
              "will be calculated after the water-point visit.",
        "ar": "نفقتكم الحالية المصرّح بها: {mad} في السنة. سيُحتسب التوفير "
              "بعد زيارة نقطة الماء.",
    },
    # AGC12 — carte eau courte du une-page : « estimation » + heures + mois.
    "agr_op_eau_jour": {
        "fr": "Eau / jour", "en": "Water / day", "ar": "الماء / يوم",
    },
    "agr_op_heures_mois": {
        "fr": "{heures} h/j en {mois}", "en": "{heures} h/day in {mois}",
        "ar": "{heures} س/يوم في {mois}",
    },
    "agr_op_heures": {
        "fr": "{heures} h/j", "en": "{heures} h/day", "ar": "{heures} س/يوم",
    },
    "agr_op_debit_declare": {
        "fr": "débit déclaré", "en": "declared flow", "ar": "صبيب مصرّح به",
    },
    # AGC13 — « HMT » du une-page traduit (EN « Head », AR).
    "agr_op_hmt": {
        "fr": "HMT", "en": "Head", "ar": "الارتفاع المانومتري",
    },
}


def a_la_cle(cle):
    """Vrai si ``cle`` appartient à ce catalogue."""
    return cle in LIBELLES_AGRICOLE


def libelle(cle, langue):
    """Le libellé ``cle`` dans ``langue`` (repli français) ; ``KeyError`` si
    la clé n'existe pas — comme ``i18n_labels.libelle``."""
    textes = LIBELLES_AGRICOLE[cle]
    return textes.get(langue) or textes["fr"]

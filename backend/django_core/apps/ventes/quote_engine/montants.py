"""Formateur monétaire UNIQUE du moteur de devis (QJR613).

Stdlib seulement : importable par le moteur legacy vendorisé comme par les
paquets premium (résidentiel / commercial / industriel), qui ne peuvent pas
importer ``generate_devis_premium`` (matplotlib au chargement).
"""
import contextvars
import html
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

#: Décision fondateur 08/10/2026 — vrai pendant le rendu d'un devis envoyé
#: AVANT les corrections (``data['regles_calcul_origine']``) : les formateurs
#: gardent alors leur arrondi d'origine. Posé par le builder et par chaque
#: moteur de rendu à partir du dict de données.
_REGLES_ORIGINE = contextvars.ContextVar('regles_calcul_origine',
                                         default=False)


def poser_regles_origine(valeur):
    """Pose le drapeau « règles d'origine » du rendu en cours."""
    _REGLES_ORIGINE.set(bool(valeur))


def fmt_centimes(v):
    """Montant au CENTIME à la française : 1 166,67.

    QJR122 — l'arrondi est aligné sur la chaîne canonique
    (``selectors._canonical_totaux`` quantifie en ``ROUND_HALF_UP`` au
    centime) : le formatage flottant de Python arrondit en mode BANQUIER,
    de sorte que le MÊME devis pouvait afficher deux nombres différents
    entre le PDF et l'échéancier / ``option_totaux``. On repasse par
    ``Decimal(str(v))`` — la représentation décimale courte, celle que la
    chaîne canonique aurait produite — avant de quantifier.
    """
    try:
        d = Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return str(v)
    return f"{d:,.2f}".replace(",", " ").replace(".", ",")


# ── AMOT45 — LA REMISE GLOBALE SUR CHAQUE LIGNE (QJRREM), UN SEUL HELPER ─────
# Le builder pose sur chaque item ``pu_ht_remise`` / ``total_ht_remise``
# (répartis par ``domain.argent.repartir_remise_par_ligne``, somme == Total HT
# net au centime). Le résidentiel les affichait déjà ; l'agricole et la page
# équipements commerciale / industrielle imprimaient le catalogue, si bien que
# les lignes ne s'additionnaient pas au Total HT. Ces trois fonctions sont la
# lecture UNIQUE de ces clés ; un item sans elles (bâti à la main, devis sans
# remise) retombe sur le catalogue : page inchangée au caractère près.


def pu_ht_remise(it):
    """P.U. HT à afficher : après remise globale, ou le catalogue à défaut."""
    valeur = it.get("pu_ht_remise")
    if valeur is None:
        return float(it.get("prix_unit_ht") or 0)
    return float(valeur)


def total_ht_remise(it):
    """Total HT de la ligne à afficher : après remise globale, ou catalogue."""
    valeur = it.get("total_ht_remise")
    if valeur is None:
        return float(it.get("prix_unit_ht") or 0) * float(it.get("quantite") or 0)
    return float(valeur)


def lignes_remisees(items, *, catalogue_seul=False):
    """``[{item, pu_catalogue, pu, total_catalogue, total}]`` pour un tableau
    d'équipements : ``pu`` / ``total`` = après remise globale (Σ ``total`` =
    Total HT net). ``catalogue_seul`` (devis aux règles d'origine, décision
    fondateur 08/10/2026) : les prix remisés valent le catalogue — l'affichage
    d'hier, sans prix barré."""
    out = []
    for it in items or ():
        pu_cat = float(it.get("prix_unit_ht") or 0)
        total_cat = pu_cat * float(it.get("quantite") or 0)
        out.append({
            "item": it,
            "pu_catalogue": pu_cat,
            "pu": pu_cat if catalogue_seul else pu_ht_remise(it),
            "total_catalogue": total_cat,
            "total": total_cat if catalogue_seul else total_ht_remise(it),
        })
    return out


def deux_prix(fmt, valeur_catalogue, valeur_remisee, cls_was="", cls_now=""):
    """« <s>1 500</s> 1 425 » : le prix catalogue barré, puis le prix remisé.
    Les deux nombres FORMATÉS sont comparés : identiques ⇒ un seul prix."""
    catalogue = fmt(valeur_catalogue)
    remise = fmt(valeur_remisee)
    if catalogue == remise:
        return remise
    was = f' class="{cls_was}"' if cls_was else ''
    now = f'<span class="{cls_now}">{remise}</span>' if cls_now else remise
    return f'<s{was}>{catalogue}</s> {now}'


def tronquer_texte(texte, limite):
    """AMOT46 — tronque un texte du document sur son texte BRUT, au mot, avec
    « … », PUIS l'échappe : jamais une entité HTML coupée (« l&#x2 »).

    Les renderers reçoivent des textes déjà échappés (``echapper_textes_client``
    au point de rendu) : couper la chaîne échappée tranchait les entités. Ici
    le texte est d'abord rendu brut (``html.unescape``), coupé au dernier
    espace avant ``limite`` (le mot en cours n'est jamais tranché, sauf un mot
    unique plus long que la limite), puis ré-échappé comme à l'ingestion.
    """
    brut = html.unescape(str(texte or ""))
    if len(brut) <= limite:
        return html.escape(brut)
    coupe = brut[:limite]
    if not brut[limite].isspace():
        espace = coupe.rfind(" ")
        if espace > 0:
            coupe = coupe[:espace]
    return html.escape(coupe.rstrip(" ,;:.-—") + "…")


def fmt_centimes_mad(v):
    """``fmt_centimes`` suffixé « MAD » — le format des lignes de total."""
    return fmt_centimes(v) + " MAD"


def pct_fr(v):
    """AMOT24 — UN pourcentage à la française : valeur EXACTE, virgule
    décimale, sans zéros inutiles (2,5 · 20 · 12,25). Jamais tronqué en
    entier (« −2 % » pour une remise de 2,5 %), jamais un point décimal."""
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return str(v)
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), "f").replace(".", ",")


def fmt_dirhams(v, sep=" "):
    """AMOT26 — UN montant client ENTIER : arrondi HALF_UP au dirham (52 650,50
    → 52 651, la règle de l'écran ``Intl``), milliers séparés par ``sep``.

    Python ``round`` arrondit au PAIR (52 650,5 → 52 650) : trois formateurs
    du moteur imprimaient donc un dirham de moins que l'écran. Devis aux
    règles d'origine : l'arrondi d'hier. ``ValueError`` sur une valeur non
    numérique (l'appelant décide de son repli)."""
    if _REGLES_ORIGINE.get():
        n = int(round(float(v)))
    else:
        try:
            n = int(Decimal(str(v)).quantize(Decimal("1"),
                                             rounding=ROUND_HALF_UP))
        except (InvalidOperation, TypeError) as exc:
            raise ValueError(str(v)) from exc
    return f"{n:,}".replace(",", sep)

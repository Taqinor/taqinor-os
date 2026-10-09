"""Formateur monétaire UNIQUE du moteur de devis (QJR613).

Stdlib seulement : importable par le moteur legacy vendorisé comme par les
paquets premium (résidentiel / commercial / industriel), qui ne peuvent pas
importer ``generate_devis_premium`` (matplotlib au chargement).
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


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


def fmt_centimes_mad(v):
    """``fmt_centimes`` suffixé « MAD » — le format des lignes de total."""
    return fmt_centimes(v) + " MAD"


def pct_fr(v):
    """AMOT24 — UN pourcentage (remise, TVA) à la française : valeur EXACTE,
    virgule décimale, sans zéros inutiles — 2,5 ; 20 ; 7,25.

    Jamais ``int(x)`` (qui imprimait « −2 % » pour une remise de 2,5 %) ni
    le point anglais (« 2.5 »). Stdlib seulement."""
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return str(v)
    txt = format(d.normalize(), "f")
    if "." in txt:
        txt = txt.rstrip("0").rstrip(".")
    return txt.replace(".", ",")


def fmt_dirhams(v, sep="\u202f"):
    """AMOT26 — montant client ENTIER (au dirham) à la française, arrondi
    ROUND_HALF_UP (la règle de l'écran ``Intl``/``solar.js formatMoney`` et
    de la chaîne canonique) : 52 650,50 → « 52 651 ».

    LE formateur entier du moteur : ``round(float(x))`` arrondissait au PAIR
    (banquier), donc 52 650,5 → 52 650 au PDF contre 52 651 à l'écran.
    ``sep`` = séparateur de milliers (espace fine insécable par défaut)."""
    try:
        d = Decimal(str(v)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return str(v)
    return f"{int(d):,}".replace(",", sep)


def pu_ht_remise(it):
    """AMOT45 — P.U. HT d'une ligne APRÈS remise globale (QJRREM :
    ``pu_ht_remise`` posé par le builder), le catalogue à défaut."""
    valeur = (it or {}).get("pu_ht_remise")
    if valeur is None:
        return float((it or {}).get("prix_unit_ht") or 0)
    return float(valeur)


def total_ht_remise(it):
    """AMOT45 — total HT d'une ligne APRÈS remise globale
    (``total_ht_remise`` du builder), P.U. catalogue × quantité à défaut."""
    valeur = (it or {}).get("total_ht_remise")
    if valeur is None:
        return float((it or {}).get("prix_unit_ht") or 0) * float(
            (it or {}).get("quantite") or 0)
    return float(valeur)


def lignes_remisees(items):
    """AMOT45 (C-AMOT-057) — LE helper unique de la remise ligne par ligne
    (extrait du résidentiel) : pour chaque item, ``(item, pu_catalogue,
    pu_remise, total_catalogue, total_remise, remisee)``. Σ ``total_remise``
    = Total HT de la chaîne (répartition du noyau, QJRREM) ; ``remisee`` dit
    si le catalogue doit être barré."""
    sortie = []
    for it in items or []:
        pu_cat = float((it or {}).get("prix_unit_ht") or 0)
        qte = float((it or {}).get("quantite") or 0)
        pu_rem = pu_ht_remise(it)
        tot_rem = total_ht_remise(it)
        sortie.append((it, pu_cat, pu_rem, pu_cat * qte, tot_rem,
                       abs(pu_rem - pu_cat) > 0.004))
    return sortie

"""Formateur monétaire UNIQUE du moteur de devis (QJR613).

Stdlib seulement : importable par le moteur legacy vendorisé comme par les
paquets premium (résidentiel / commercial / industriel), qui ne peuvent pas
importer ``generate_devis_premium`` (matplotlib au chargement).
"""
import contextvars
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

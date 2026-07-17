"""Sélecteurs LECTURE SEULE du domaine Agriculture.

Les autres apps (et les vues de cette app) lisent via ces fonctions plutôt
que d'assembler des requêtes ad hoc — même patron que ``apps.stock.selectors``
(CLAUDE.md, frontière cross-app)."""
from decimal import Decimal


def cout_total_campagne(campagne):
    """NTAGR3 — Somme des coûts des étapes de campagne (``EtapeCampagne.cout_mad``).

    Les étapes sans coût renseigné (``cout_mad is None`` — ex. étapes
    prévisionnelles) sont ignorées, pas comptées comme zéro-conflictuel avec
    un coût réel."""
    total = Decimal('0')
    for cout in campagne.etapes.exclude(cout_mad__isnull=True).values_list(
            'cout_mad', flat=True):
        total += cout
    return total


def cout_main_oeuvre_campagne(campagne):
    """NTAGR9 — Coût total main d'œuvre d'une campagne.

    Somme de ``nombre_journees × taux_journalier_mad`` sur tous les
    pointages rattachés à la campagne."""
    total = Decimal('0')
    for journees, taux in campagne.pointages.values_list(
            'nombre_journees', 'taux_journalier_mad'):
        total += journees * taux
    return total

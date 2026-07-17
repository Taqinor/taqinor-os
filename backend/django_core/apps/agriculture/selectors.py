"""Sélecteurs LECTURE SEULE du domaine Agriculture.

Les autres apps (et les vues de cette app) lisent via ces fonctions plutôt
que d'assembler des requêtes ad hoc — même patron que ``apps.stock.selectors``
(CLAUDE.md, frontière cross-app)."""
from decimal import Decimal


def _releves_irrigation_fenetre(campagne):
    """NTAGR14 — Relevés des points d'irrigation de la parcelle de la
    campagne, restreints à sa FENÊTRE : du semis (si connu) à la récolte
    réelle si connue, sinon la récolte prévue si connue, sinon fenêtre
    ouverte côté fin. Une campagne sans aucune date ne filtre pas les
    relevés par date (comportement conservateur : mieux vaut tout compter
    qu'exclure à tort faute de dates saisies)."""
    from .models import RelevePointIrrigation

    releves = RelevePointIrrigation.objects.filter(
        point__parcelle_id=campagne.parcelle_id)
    if campagne.date_semis:
        releves = releves.filter(date__gte=campagne.date_semis)
    fin = campagne.date_recolte_reelle or campagne.date_recolte_prevue
    if fin:
        releves = releves.filter(date__lte=fin)
    return releves


def cout_irrigation_campagne(campagne):
    """NTAGR14 — Coût d'irrigation PAYANTE (réseau/gasoil) d'une campagne :
    somme des ``RelevePointIrrigation.cout_energie_mad`` de la fenêtre de la
    campagne. Les relevés SANS coût renseigné (pompage solaire — coût
    variable nul par nature — ou coût simplement non saisi) sont EXCLUS de
    la somme, jamais comptés comme zéro-conflictuel avec un coût réel (même
    garde que ``cout_total_campagne`` pour les étapes sans coût)."""
    total = Decimal('0')
    releves = _releves_irrigation_fenetre(campagne)
    for cout in releves.exclude(cout_energie_mad__isnull=True).values_list(
            'cout_energie_mad', flat=True):
        total += cout
    return total


def volume_irrigation_solaire_campagne(campagne):
    """NTAGR14 — Volume (m³) irrigué par pompage solaire sur la fenêtre de la
    campagne — irrigation GRATUITE (coût variable nul par construction,
    distincte de l'irrigation payante ci-dessus), affichée séparément comme
    « irrigation solaire : 0 MAD variable »."""
    from .models import PointIrrigation

    total = Decimal('0')
    releves = _releves_irrigation_fenetre(campagne).filter(
        point__type_source=PointIrrigation.TypeSource.POMPAGE_SOLAIRE)
    for volume in releves.values_list('volume_m3', flat=True):
        total += volume
    return total


def cout_total_campagne(campagne):
    """NTAGR3/NTAGR14 — Somme des coûts des étapes de campagne
    (``EtapeCampagne.cout_mad``) + le coût d'irrigation PAYANTE de sa
    fenêtre (``cout_irrigation_campagne`` — l'irrigation par pompage
    solaire reste explicitement à coût variable nul, jamais ajoutée ici).

    Les étapes sans coût renseigné (``cout_mad is None`` — ex. étapes
    prévisionnelles) sont ignorées, pas comptées comme zéro-conflictuel avec
    un coût réel."""
    total = Decimal('0')
    for cout in campagne.etapes.exclude(cout_mad__isnull=True).values_list(
            'cout_mad', flat=True):
        total += cout
    total += cout_irrigation_campagne(campagne)
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

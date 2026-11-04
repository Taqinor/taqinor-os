"""NTDATA35 — bibliothèque de DASHBOARDS MODÈLES bâtis sur les métriques nommées.

Trois tableaux de bord PARTAGÉS prêts à l'emploi (Direction, Commerce,
Finance), dont chaque widget référence une métrique nommée par sa CLÉ
(``{'type': 'metrique', 'metrique': <cle>}``, le format que
``core.dashboard_data.executer_dashboard`` résout via NTDATA34). Aucun widget
ne porte sa propre spec : corriger la définition d'une métrique met à jour les
trois modèles avec tous les autres écrans qui la référencent.

AUCUNE MÉTRIQUE INVENTÉE : les clés sont celles des 8 métriques cœur de
``seed_metriques`` (NTDATA11). « Relances » et « encours » n'ont pas (encore)
de métrique gouvernée : le modèle Commerce montre la conversion, le pipeline
pondéré et le panier moyen ; le modèle Finance le DSO, le CA TTC et la marge
brute. Une clé absente de la société (seed_metriques pas encore passé) rend
un widget « métrique inconnue » lisible, jamais un chiffre fabriqué.

IDEMPOTENT ET ADDITIF : le marqueur ``layout['modele']`` identifie un modèle
déjà posé ; il n'est alors JAMAIS réécrit — un dashboard modèle que la société
a édité (titre, widgets, filtres) reste tel quel. Supprimer un modèle puis
relancer le seeder le recrée, à l'état d'origine.
"""
from django.db import transaction

#: Les trois modèles. ``modele`` est la clé d'idempotence (par société).
DASHBOARDS_MODELES = [
    {
        'modele': 'direction',
        'titre': 'Direction — chiffre, marge, pipeline',
        'description': "Vue de direction : chiffre d'affaires, marge brute et "
                       'pipeline pondéré, sur les métriques gouvernées.',
        'metriques': [
            ('ca_ht', "Chiffre d'affaires HT"),
            ('marge_brute', 'Marge brute'),
            ('valeur_pipeline_ponderee', 'Pipeline pondéré'),
        ],
    },
    {
        'modele': 'commerce',
        'titre': 'Commerce — conversion et pipeline',
        'description': 'Vue commerciale : taux de conversion des pistes, '
                       'pipeline pondéré et panier moyen.',
        'metriques': [
            ('taux_conversion', 'Taux de conversion'),
            ('valeur_pipeline_ponderee', 'Pipeline pondéré'),
            ('panier_moyen', 'Panier moyen'),
        ],
    },
    {
        'modele': 'finance',
        'titre': 'Finance — DSO, chiffre, marge',
        'description': "Vue financière : délai moyen de règlement (DSO), "
                       "chiffre d'affaires TTC et marge brute.",
        'metriques': [
            ('dso', 'DSO (délai moyen de règlement)'),
            ('ca_ttc', "Chiffre d'affaires TTC"),
            ('marge_brute', 'Marge brute'),
        ],
    },
]


def layout_du_modele(spec):
    """Le ``layout`` d'un modèle : un widget-métrique par clé, en grille."""
    widgets = []
    for index, (cle, titre) in enumerate(spec['metriques']):
        widgets.append({
            'id': '%s-%s' % (spec['modele'], cle),
            'type': 'metrique',
            'metrique': cle,
            'titre': titre,
            'x': (index % 3) * 4, 'y': (index // 3) * 3, 'w': 4, 'h': 3,
        })
    return {'modele': spec['modele'], 'widgets': widgets}


@transaction.atomic
def semer_dashboards_modeles(company):
    """Pose les modèles manquants pour ``company``. Renvoie ``(créés, intacts)``.

    Un modèle déjà présent (même marqueur ``modele``, dashboard de société) —
    édité ou non — n'est JAMAIS touché.
    """
    from core.models import Dashboard

    deja = set(
        Dashboard.objects
        .filter(company=company, owner__isnull=True,
                layout__has_key='modele')
        .values_list('layout__modele', flat=True))
    crees = 0
    for spec in DASHBOARDS_MODELES:
        if spec['modele'] in deja:
            continue
        Dashboard.objects.create(
            company=company, owner=None, partage=True,
            titre=spec['titre'], description=spec['description'],
            layout=layout_du_modele(spec))
        crees += 1
    return crees, len(DASHBOARDS_MODELES) - crees

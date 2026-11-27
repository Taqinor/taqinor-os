"""ACAL695 — la cascade regroupée en cinq postes LISIBLES.

La cascade publie une étape par perte (``ORDRE_ETAPES``) ; un client lit
cinq postes : Ombres proches, Poussière, Chaleur, Câbles et onduleur, Autres
pertes (maquette ``Resultats.dc.html``). La table ci-dessous est une
DÉCLARATION (aucun nombre) : chaque étape de ``ORDRE_ETAPES`` a exactement un
poste, ce que ``test_calx148_ordre.py::PostesDePertesTest`` vérifie.

Les énergies sont celles déjà servies par la cascade : ``perte_kwh`` d'un
poste est la somme NETTE de ses étapes appliquées (un gain bifacial vient en
déduction), rapportée au ``kwh_avant`` de la première étape. Une étape omise
n'est jamais comptée à 0 : le poste dit « partiel » (et la nomme) ou « non
compté » (perte à ``null``).

Jumeau : ``chaine_pertes.POSTE_PAR_ETAPE`` (étape → poste du CATALOGUE saisi)
est une autre correspondance, inchangée.
"""
from __future__ import annotations

from .rapport.champs_lisibles import motif_lisible
from .valeurs import nombre as _nombre

#: Les cinq postes lisibles, dans l'ordre de lecture, et leurs étapes.
POSTES = (
    ('ombres_proches', 'Ombres proches',
     ('horizon', 'ombrage_proche', 'acces_module', 'ombrage_diffus',
      'inter_rangees', 'mismatch_ombrage')),
    ('poussiere', 'Poussière', ('salissure', 'neige')),
    ('chaleur', 'Chaleur', ('thermique',)),
    ('cables_et_onduleur', 'Câbles et onduleur',
     ('ohmique_dc', 'mppt', 'onduleur', 'ecretage', 'ohmique_ac',
      'transformateur')),
    ('autres', 'Autres pertes',
     ('bifacial', 'iam', 'spectral', 'niveau_irradiance', 'qualite_module',
      'lid', 'mismatch_fabricant', 'diodes', 'optimiseur', 'auxiliaires',
      'indisponibilite')),
)

#: Étape → poste, dérivée de :data:`POSTES` (une seule source).
POSTE_DE_L_ETAPE = {etape: poste for poste, _libelle, etapes in POSTES
                    for etape in etapes}

MOTIF_SANS_CASCADE = ('Aucune cascade de pertes publiée : les postes '
                      'lisibles ne peuvent pas être regroupés.')

__all__ = ['POSTES', 'POSTE_DE_L_ETAPE', 'MOTIF_SANS_CASCADE', 'cause_courte',
           'regrouper']


#: ACAL1616 — ce qui manque à une étape omise, en mots de métier : une table
#: FERMÉE ``étape -> cause``. Le motif servi reste au rapport d'étude
#: (document technique) ; la fiche client n'en recopie jamais le texte.
CAUSE_PAR_ETAPE = {
    'horizon': 'horizon du site', 'ombrage_proche': 'aucun obstacle saisi',
    'acces_module': 'ombre par panneau', 'ombrage_diffus': 'vue du ciel',
    'inter_rangees': 'géométrie des rangées',
    'mismatch_ombrage': 'ombre par panneau', 'salissure': 'salissure du site',
    'neige': 'neige du site', 'thermique': 'fiche du module',
    'ohmique_dc': 'câbles', 'mppt': 'température des cellules',
    'onduleur': "fiche de l'onduleur", 'ecretage': "fiche de l'onduleur",
    'ohmique_ac': "sortie de l'onduleur", 'transformateur': 'transformateur',
    'bifacial': 'face arrière du module', 'iam': 'heure du site',
    'spectral': 'modèle spectral', 'niveau_irradiance': 'fiche du module',
    'qualite_module': 'fiche du module', 'lid': 'perte de mise en service',
    'mismatch_fabricant': 'dispersion des modules',
    'diodes': 'fiche du module', 'optimiseur': 'optimiseurs',
    'auxiliaires': 'consommation des auxiliaires',
    'indisponibilite': "périodes d'arrêt",
}

#: Le mot court d'état, lu dans le motif servi : la PREMIÈRE famille gagne.
ETAT_PAR_CAUSE = (
    (('sans objet', 'aucune perte'), 'sans objet'),
    (('deux fois', 'déjà'), 'déjà compté'),
    (('non modélis',), 'non modélisé'),
    (('saisi', 'renseign', 'fiche', 'déclar'), 'non renseigné'),
)


def cause_courte(etape):
    """« <état> : <ce qui manque> » — jamais le motif servi recopié."""
    motif = str(etape.get('motif_omission') or '').lower()
    etat = next((mot for indices, mot in ETAT_PAR_CAUSE
                 if any(indice in motif for indice in indices)),
                'non calculé')
    cause = CAUSE_PAR_ETAPE.get(etape.get('etape'))
    if cause is None:  # étape neuve : son libellé, rendu lisible
        cause = motif_lisible(etape.get('libelle') or 'donnée manquante')
    return '%s : %s' % (etat, cause)


def _pct(kwh, depart):
    return round(100.0 * kwh / depart, 3)


def regrouper(cascade):
    """``cascade.postes_lisibles`` : cinq postes, ou ``postes: []`` motivé."""
    cascade = cascade or {}
    etapes = cascade.get('etapes') or []
    depart = _nombre(etapes[0].get('kwh_avant')) if etapes else None
    if not etapes or cascade.get('total_pct') is None or not depart:
        return {'depart_kwh': depart, 'arrivee_kwh': None,
                'arrivee_pct': None, 'total_pct': cascade.get('total_pct'),
                'postes': [], 'motif_absence': MOTIF_SANS_CASCADE}
    arrivee = next((_nombre(etape.get('kwh_apres')) for etape in reversed(etapes)
                    if _nombre(etape.get('kwh_apres')) is not None), depart)
    postes = []
    for poste, libelle, noms in POSTES:
        lignes = [etape for etape in etapes if etape.get('etape') in noms]
        omises = [{'etape': etape.get('etape'), 'libelle': etape.get('libelle'),
                   'motif_omission': etape.get('motif_omission')}
                  for etape in lignes if etape.get('motif_omission')]
        pertes = [_nombre(etape.get('perte_kwh')) for etape in lignes
                  if not etape.get('motif_omission')]
        pertes = [perte for perte in pertes if perte is not None]
        if not pertes:
            perte_kwh, perte_pct, statut = None, None, 'non_compte'
        else:
            perte_kwh = round(sum(pertes), 1)
            perte_pct = _pct(sum(pertes), depart)
            statut = 'partiel' if omises else 'compte'
        # ACAL1676 — la cause COURTE du poste (celle de la fiche PDF), sans doublon.
        causes = []
        for etape in omises:
            if cause_courte(etape) not in causes:
                causes.append(cause_courte(etape))
        postes.append({'poste': poste, 'libelle': libelle,
                       'perte_kwh': perte_kwh, 'perte_pct': perte_pct,
                       'statut': statut, 'cause': ' ; '.join(causes),
                       'etapes': omises})
    return {'depart_kwh': depart, 'arrivee_kwh': arrivee,
            'arrivee_pct': _pct(arrivee, depart),
            'total_pct': cascade.get('total_pct'), 'postes': postes,
            'motif_absence': ''}

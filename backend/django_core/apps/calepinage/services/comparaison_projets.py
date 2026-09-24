"""CALX341 — comparer jusqu'à CINQ calepinages DISTINCTS, à la lecture.

LE CONSTAT
----------
Le seul comparatif du module confronte les VARIANTES d'un calepinage
(``services/comparaison.py::colonnes_production``,
``selectors.py::comparer_variantes``) : il ne sort jamais du calepinage
courant. Deux toitures d'un même client, deux options d'un même bâtiment
dessinées comme deux calepinages, deux sites d'une même affaire : rien ne les
mettait côte à côte. Parité : PV*SOL compare jusqu'à 5 projets, y compris de
dossiers différents (https://help.valentin-software.com/pvsol/en/
project-comparison/ — « up to 5 projects can be compared »).

LES TROIS DISCIPLINES, REPRISES DU COMPARATIF DES VARIANTES
------------------------------------------------------------
1. **LECTURE PURE.** Aucune simulation n'est déclenchée, rien n'est écrit,
   aucun statut ne bouge : la production est LUE dans ``Calepinage.resultat``
   par le MÊME chemin que le comparatif des variantes (``colonnes_production``)
   — deux lectures du même bloc, ce seraient deux vérités.
2. **L'empreinte fait foi.** Une production calculée sur une AUTRE empreinte
   de layout que celle d'aujourd'hui est PÉRIMÉE (règle de
   ``comparaison.py::_empreinte_du_resultat``) : la ligne est publiée « non
   simulée », avec son motif.
3. **Non simulé ⇒ ``None``, jamais ``0``.** Un zéro se lirait « zéro kWh » là
   où personne n'a lancé de calcul ; ``modules``/``kwc`` valent aussi ``None``
   quand la conception ne les dit pas.

BORNÉ SOCIÉTÉ, SANS RIEN RÉVÉLER
--------------------------------
Un identifiant d'une AUTRE société — ou inexistant — n'est pas comparé : il
est listé dans ``refus`` avec le MÊME motif dans les deux cas (dire « il existe
ailleurs » confirmerait son existence). La société est TOUJOURS celle passée
par l'appelant (``request.user.company``), jamais lue d'un corps de requête.

La forme publiée est celle du contrat committé
``contract_samples/calepinage_comparaison_projets.json`` (CALX331). Aucun
montant n'y entre (D-CALX 5 : l'argent vit dans ``apps/ventes``).
"""
from __future__ import annotations

__all__ = [
    'BORNE_PROJETS', 'COLONNES', 'ComparaisonRefusee', 'MOTIF_INTROUVABLE',
    'MOTIF_NON_SIMULE', 'MOTIF_PERIME', 'comparer_calepinages',
]

#: La borne du comparatif : cinq calepinages. C'est celle de PV*SOL, citée
#: ci-dessus — pas un réglage, une largeur de tableau lisible.
BORNE_PROJETS = 5

#: Les grandeurs comparées, dans l'ordre des colonnes : ``(clé, libellé,
#: unité)``. SOURCE UNIQUE des en-têtes de l'écran ET de la feuille
#: « Comparatif » du classeur (``export_tableur._table_comparatif``). Les six
#: clés de production sont exactement ``comparaison.CLES_PRODUCTION``.
COLONNES = (
    ('modules', 'Modules posés', 'u'),
    ('kwc', 'Puissance crête', 'kWc'),
    ('p50_kwh', 'Production P50', 'kWh/an'),
    ('p75_kwh', 'Production P75', 'kWh/an'),
    ('p90_kwh', 'Production P90', 'kWh/an'),
    ('performance_ratio', 'Indice de performance (PR)', ''),
    ('specific_yield_kwh_kwc', 'Productible spécifique', 'kWh/kWc/an'),
    ('self_consumption_rate', 'Taux d’autoconsommation', ''),
)

MOTIF_NON_SIMULE = (
    "Ce calepinage n'a pas été simulé : aucune production n'est publiée "
    '(les colonnes restent vides, jamais à 0).')
MOTIF_PERIME = (
    'La conception de ce calepinage a changé depuis sa dernière simulation : '
    'la production affichée serait celle d’un autre toit. Elle est donc '
    'traitée comme non simulée — relancez la simulation.')
MOTIF_INTROUVABLE = (
    'Calepinage introuvable dans cette société : il est ignoré, jamais '
    'comparé.')


class ComparaisonRefusee(ValueError):
    """Refus métier, message français, champ fautif NOMMÉ (``ids``)."""

    def __init__(self, message, *, champ='ids'):
        super().__init__(message)
        self.champ = champ


def _morceaux(brut):
    """Aplatit ``[1, '2,3']`` / ``'1,2'`` en une liste de jetons bruts."""
    if brut is None:
        return []
    if isinstance(brut, (list, tuple)):
        elements = list(brut)
    else:
        elements = [brut]
    jetons = []
    for element in elements:
        if isinstance(element, str):
            jetons.extend(part.strip() for part in element.split(',')
                          if part.strip())
        else:
            jetons.append(element)
    return jetons


def _entier_positif(jeton):
    if isinstance(jeton, bool):
        return None
    if isinstance(jeton, int):
        return jeton if jeton > 0 else None
    if isinstance(jeton, str) and jeton.isdigit():
        valeur = int(jeton)
        return valeur if valeur > 0 else None
    return None


def _lire_ids(brut):
    """Les identifiants demandés, dédoublonnés, DANS L'ORDRE reçu.

    Accepte une liste d'entiers (corps JSON), une liste de chaînes, ou une
    chaîne « 1,2,3 » (paramètre de requête). Un identifiant répété n'est
    compté qu'une fois.

    Raises:
        ComparaisonRefusee: liste absente ou vide, jeton non entier, ou plus
            de ``BORNE_PROJETS`` identifiants distincts — le message NOMME le
            champ ``ids`` et, pour la borne, la dit.
    """
    jetons = _morceaux(brut)
    if not jetons:
        raise ComparaisonRefusee(
            'Indiquez au moins un calepinage à comparer (liste « ids » des '
            'identifiants).')
    ids = []
    for jeton in jetons:
        valeur = _entier_positif(jeton)
        if valeur is None:
            raise ComparaisonRefusee(
                'La liste « ids » ne contient que des identifiants entiers '
                'positifs (reçu : « %s »).' % (jeton,))
        if valeur not in ids:
            ids.append(valeur)
    if len(ids) > BORNE_PROJETS:
        raise ComparaisonRefusee(
            'Au plus %d calepinages peuvent être comparés à la fois '
            '(reçu : %d).' % (BORNE_PROJETS, len(ids)))
    return ids


def _colonnes():
    """Les colonnes du comparatif, à la forme du contrat."""
    return [{'cle': cle, 'libelle': libelle, 'unite': unite}
            for cle, libelle, unite in COLONNES]


def _dict(valeur):
    return valeur if isinstance(valeur, dict) else {}


def _nombre(valeur):
    """Un NOMBRE au sens strict (ni booléen, ni texte), sinon ``None``."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    if valeur != valeur:  # NaN
        return None
    return valeur


def _mesures_du_calepinage(calepinage, *, simule=False):
    """``(modules, kwc)`` LUS, jamais recalculés — ``None`` quand inconnus.

    Ordre de lecture : d'abord le résumé que l'atelier dépose dans la
    conception COURANTE (``roof_layout.result`` — mêmes clés que
    ``services/journal.py::_modules``), puis le bloc ``pose`` du résultat
    (moteur), puis — seulement pour une simulation À JOUR (``simule``) — le
    total de production (``production.total.kwc``). Une simulation périmée
    décrit un autre toit : son kWc n'est jamais repris. Aucune valeur n'est
    déduite d'une autre : un kWc sans modules reste un kWc sans modules.
    """
    resultat = _dict(getattr(calepinage, 'resultat', None))
    atelier = _dict(_dict(getattr(calepinage, 'roof_layout', None))
                    .get('result'))
    pose = _dict(resultat.get('pose'))
    total = (_dict(_dict(resultat.get('production')).get('total'))
             if simule else {})

    modules = None
    for source, cles in ((atelier, ('panels', 'count', 'nb_panneaux')),
                         (pose, ('total_modules',))):
        for cle in cles:
            modules = _nombre(source.get(cle))
            if modules is not None:
                break
        if modules is not None:
            break
    kwc = None
    for source in (atelier, pose, total):
        kwc = _nombre(source.get('kwc'))
        if kwc is not None:
            break
    return (int(modules) if modules is not None else None), kwc


def _ligne_de_comparaison(calepinage):
    """UNE ligne du comparatif, à la forme du contrat — fonction PURE.

    Toutes les clés sont TOUJOURS présentes ; non simulé (ou périmé) ⇒
    ``simule: False``, les six grandeurs de production à ``None`` et un
    ``motif`` qui dit pourquoi.
    """
    from .comparaison import (
        CLES_PRODUCTION, MOTIF_PERIMEE, colonnes_production,
    )

    empreinte = getattr(calepinage, 'layout_hash', '') or ''
    simule, production, motif_lu = colonnes_production(
        getattr(calepinage, 'resultat', None), layout_hash=empreinte or None)
    if simule:
        motif = ''
    elif motif_lu == MOTIF_PERIMEE:
        motif = MOTIF_PERIME
    else:
        motif = MOTIF_NON_SIMULE
    modules, kwc = _mesures_du_calepinage(calepinage, simule=simule)
    ligne = {
        'id': getattr(calepinage, 'pk', None),
        'titre': getattr(calepinage, 'titre', '') or '',
        'statut': getattr(calepinage, 'statut', '') or '',
        'layout_hash': empreinte,
        'modules': modules,
        'kwc': kwc,
        'simule': bool(simule),
        'motif': motif,
    }
    for cle in CLES_PRODUCTION:
        ligne[cle] = production.get(cle) if simule else None
    return ligne


def comparer_calepinages(company, ids):
    """Le comparatif de 1 à ``BORNE_PROJETS`` calepinages de ``company``.

    Args:
        company: la société de l'APPELANT — jamais lue d'un corps de requête.
            ``None`` ⇒ tous les identifiants sont refusés.
        ids: les identifiants demandés (liste, ou chaîne « 1,2,3 »).

    Returns:
        ``{colonnes, lignes, refus}`` — ``lignes`` dans l'ordre des ``ids``,
        ``refus`` pour chaque identifiant ignoré (autre société ou inexistant,
        même motif).

    Raises:
        ComparaisonRefusee: voir ``_lire_ids`` (le champ nommé est ``ids``).
    """
    demandes = _lire_ids(ids)
    trouves = {}
    if company is not None:
        from ..models import Calepinage

        trouves = {calepinage.pk: calepinage
                   for calepinage in Calepinage.objects.filter(
                       company=company, pk__in=demandes)}
    return {
        'colonnes': _colonnes(),
        'lignes': [_ligne_de_comparaison(trouves[pk])
                   for pk in demandes if pk in trouves],
        'refus': [{'id': pk, 'motif': MOTIF_INTROUVABLE}
                  for pk in demandes if pk not in trouves],
    }

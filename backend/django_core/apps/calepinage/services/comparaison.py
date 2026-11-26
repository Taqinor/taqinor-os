"""CAL145 — comparer les variantes sur la PRODUCTION, à la LECTURE.

LE CONSTAT
----------
``CalepinageVariante`` (CAL9) compare des COMPTAGES de modules, et
``compare_scenarios`` (``apps/ventes/solar_design.py``) compare des scénarios
de DEVIS : aucun des deux ne confronte deux plans de pose sur leur production
simulée. Le contrat committé ``contract_samples/variantes_comparer.json``
porte pourtant déjà les colonnes de production (PACT10 : elles ont été
écrites AVANT, pour que le comparatif ne dérive pas du contrat le jour où
elles arrivent) — elles restaient vides parce que rien ne savait les remplir.

LES TROIS DISCIPLINES TENUES ICI
--------------------------------
1. **Calculé À LA LECTURE, jamais stocké.** Ce module ne persiste RIEN et ne
   lance AUCUNE simulation : il LIT le résultat déposé par le moteur sur
   chaque variante et en extrait les colonnes. Même discipline que
   ``core/calepinage/etude.py`` — un comparatif figé en base serait faux le
   lendemain sans que personne ne le sache.
2. **L'empreinte d'entrée fait foi.** Si le résultat porte l'empreinte du
   layout qui l'a produit et qu'elle DIFFÈRE de celle de la variante
   d'aujourd'hui, la production est PÉRIMÉE : la variante est publiée « non
   simulée », avec son motif. Le comparatif suit donc l'empreinte sans qu'on
   ait besoin d'invalider quoi que ce soit à l'écriture.
3. **Non simulée ⇒ ``None`` partout, jamais ``0``.** Un zéro se lirait « zéro
   kWh » là où personne n'a lancé de simulation.

DEUX FORMES DE RÉSULTAT SONT LUES, ET C'EST VOULU
--------------------------------------------------
Le moteur de production du module (CAL138/CAL142) écrit un bloc IMBRIQUÉ
(``production.total.p50_kwh``) ; les résultats venus du parcours devis sont
PLATS (``production.p50_kwh``, forme d'``apps/ventes/etude._pr_block``). Les
deux sont acceptées et rendues dans la MÊME forme plate, celle du contrat :
le comparatif n'a pas à savoir quel chemin a produit le chiffre.

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations
from .valeurs import nombre as _nombre

__all__ = ['CLES_PRODUCTION', 'MOTIF_NON_SIMULEE', 'MOTIF_PERIMEE',
           'NOMBRE_PERTES_DOMINANTES', 'colonnes_production',
           'hypotheses_comparees', 'verdict_electrique_de_la_variante']


def verdict_electrique_de_la_variante(variante):
    """ACAL172 — ``{verdict, bloquants}`` de LA variante (codes des
    bloquants), évalué sur SON ``roof_layout`` par la lecture unique
    ``electrique.verdict_de_conception``. Lecture pure ; une variante sans
    conception, ou des entrées illisibles, rendent ``indetermine``."""
    from .electrique import TemperaturesInvalides, verdict_de_conception

    indetermine = {'verdict': 'indetermine', 'bloquants': []}
    calepinage = getattr(variante, 'calepinage', None)
    document = getattr(variante, 'roof_layout', None)
    if calepinage is None or not isinstance(document, dict) or not document:
        return indetermine
    try:
        verdict = verdict_de_conception(calepinage, layout=document)
    except TemperaturesInvalides:
        return indetermine
    return {'verdict': verdict['verdict'],
            'bloquants': [b['code'] for b in verdict['bloquants']]}


#: Les colonnes de production du contrat ``variantes_comparer.json`` —
#: ``pertes_dominantes`` est traitée à part (c'est une liste, jamais ``None``).
CLES_PRODUCTION = ('p50_kwh', 'p75_kwh', 'p90_kwh', 'performance_ratio',
                   'specific_yield_kwh_kwc', 'self_consumption_rate')

#: Combien de postes de perte on met en avant. Trois : de quoi nommer ce qui
#: sépare deux variantes sans transformer une colonne en tableau.
NOMBRE_PERTES_DOMINANTES = 3

MOTIF_NON_SIMULEE = (
    "Cette variante n'a pas été simulée : aucune production n'est publiée "
    '(les colonnes restent vides, jamais à 0).')
MOTIF_PERIMEE = (
    'La conception ou un réglage de votre société a changé depuis la dernière simulation de cette variante : '
    'la production affichée serait celle d’un autre toit. Elle est donc '
    'traitée comme non simulée — relancez la simulation.')


def _dict(valeur):
    return valeur if isinstance(valeur, dict) else {}


def _hash_de_simulation(resultat):
    """L'empreinte de simulation (``resultat['simulation']['hash_entree']``)
    sous laquelle ce résultat a été calculé, ou ``''`` si aucune n'est dite."""
    simulation = _dict(_dict(resultat).get('simulation'))
    valeur = simulation.get('hash_entree')
    return valeur if isinstance(valeur, str) else ''


def simulation_perimee_du_calepinage(calepinage):
    """ACAL111 — LE verdict de péremption d'un calepinage : celui que sert
    ``selectors.resultat_servi`` (``simulation_perimee``), jamais un second
    calcul. Sans simulation déposée (aucun ``hash_entree``) il n'y a rien à
    périmer : ``False`` — et aucune lecture de la base n'est faite."""
    if not _hash_de_simulation(getattr(calepinage, 'resultat', None)):
        return False
    from ..selectors import resultat_servi

    return bool(resultat_servi(calepinage).get('simulation_perimee'))


def simulation_perimee_de_la_variante(variante):
    """ACAL111 — le résultat déposé sur une variante décrit-il ENCORE son
    ``roof_layout`` ? Même empreinte de simulation que le calepinage
    (``simulation.empreinte_simulation``, C-ACAL-073) appliquée au document de
    la VARIANTE. Résultat sans empreinte ⇒ ``False`` (un doute ne rougit
    pas) ; entrées illisibles ⇒ ``False`` (le refus appartient à la
    simulation)."""
    attendue = _hash_de_simulation(getattr(variante, 'resultat', None))
    calepinage = getattr(variante, 'calepinage', None)
    if not attendue or calepinage is None:
        return False
    from .electrique import (
        TemperaturesInvalides, conception_du_calepinage, parametres_societe,
    )
    from .simulation import empreinte_simulation

    try:
        _, materiel, donnees, document = conception_du_calepinage(
            calepinage, layout=getattr(variante, 'roof_layout', None))
    except TemperaturesInvalides:
        return False
    actuelle = empreinte_simulation(
        calepinage, document=document, donnees=donnees, materiel=materiel,
        reglages=parametres_societe(calepinage))
    return actuelle != attendue


def _pertes_dominantes(resultat):
    """Les postes de perte les plus lourds, chacun AVEC SA SOURCE.

    Les pertes du module sont une LISTE de postes sourcés (CAL139) ; celles du
    parcours devis arrivent en ``loss_breakdown`` ``{poste: {pct}}`` sans
    source — dans ce cas la source est ``None`` (non sourcée), jamais
    inventée.
    """
    postes = resultat.get('pertes')
    lignes = []
    if isinstance(postes, list):
        for poste in postes:
            if not isinstance(poste, dict):
                continue
            pct = _nombre(poste.get('pct'))
            if pct is None:
                continue
            lignes.append({'poste': str(poste.get('poste') or ''),
                           'pct': pct, 'source': poste.get('source')})
    else:
        production = _dict(resultat.get('production'))
        detail = _dict(production.get('loss_breakdown')) \
            or _dict(_dict(production.get('total')).get('loss_breakdown'))
        for nom, valeur in detail.items():
            pct = _nombre(_dict(valeur).get('pct') if isinstance(valeur, dict)
                          else valeur)
            if pct is None:
                continue
            lignes.append({'poste': str(nom), 'pct': pct, 'source': None})
    lignes.sort(key=lambda ligne: (-ligne['pct'], ligne['poste']))
    return lignes[:NOMBRE_PERTES_DOMINANTES]


def colonnes_production(resultat, *, perimee=False):
    """Les colonnes de production d'UNE variante, à la forme du contrat.

    Args:
        resultat: le ``resultat`` DÉPOSÉ sur la variante par le moteur.
        perimee: le VERDICT de péremption, décidé par l'appelant (verdict
            servi du calepinage, ou empreinte de simulation de la variante) :
            vrai ⇒ la production est déclarée PÉRIMÉE (donc non simulée).

    Returns:
        ``(simulee, production, motif)`` — ``production`` porte TOUJOURS les
        mêmes clés ; non simulée ⇒ toutes à ``None`` et
        ``pertes_dominantes: []``.
    """
    resultat = _dict(resultat)
    production = _dict(resultat.get('production'))
    vide = ({cle: None for cle in CLES_PRODUCTION}
            | {'pertes_dominantes': []})

    if not production:
        return False, vide, MOTIF_NON_SIMULEE

    if perimee:
        return False, vide, MOTIF_PERIMEE

    # Forme imbriquée du module (CAL138/CAL142) ou forme plate du parcours
    # devis : on lit la première qui porte la clé, sans jamais additionner
    # les deux.
    total = _dict(production.get('total'))
    autoconso = (_dict(resultat.get('autoconsommation'))
                 | _dict(production.get('self_consumption')))

    def _lire(cle):
        for source in (total, production, autoconso):
            if cle in source:
                valeur = _nombre(source.get(cle))
                if valeur is not None:
                    return valeur
        return None

    colonnes = {cle: _lire(cle) for cle in CLES_PRODUCTION}
    if all(valeur is None for valeur in colonnes.values()):
        # Un bloc ``production`` présent mais entièrement vide n'est pas une
        # simulation : le dire vaut mieux que publier six ``null`` sous un
        # « simulée ».
        return False, vide, MOTIF_NON_SIMULEE

    colonnes['pertes_dominantes'] = _pertes_dominantes(resultat)
    return True, colonnes, ''


#: ACAL883 — les blocs ``resultat['meteo']`` comparés, et leur libellé.
_LIBELLES_METEO = (
    ('base_rayonnement', 'Base de rayonnement'),
    ('base_meteo', 'Base météo'),
    ('mode', 'Mode météo'),
    ('fenetre_annees', 'Fenêtre météo (années)'),
    ('point', 'Point météo'),
)


def _texte_hypothese(valeur):
    if isinstance(valeur, dict):
        return ', '.join(f'{cle} {valeur[cle]}' for cle in sorted(valeur)
                         if not isinstance(valeur[cle], (dict, list)))
    return str(valeur)


def _hypotheses_du_resultat(resultat):
    """``{cle: (libellé, texte)}`` — réglages utilisés (valeur et source) et
    météo, LUS dans le résultat déposé, jamais recalculés."""
    from .parametres_cles import SECTION_SIMULATION, registre

    libelles = registre(SECTION_SIMULATION)
    simulation = _dict(_dict(resultat).get('simulation'))
    lues = {}
    for cle, reglage in _dict(simulation.get('reglages_utilises')).items():
        reglage = _dict(reglage)
        libelle = (libelles.get(cle) or (cle,))[0]
        lues[cle] = (libelle, '%s (source : %s)' % (
            _texte_hypothese(reglage.get('valeur')),
            reglage.get('source') or 'non dite'))
    meteo = _dict(_dict(resultat).get('meteo'))
    for cle, libelle in _LIBELLES_METEO:
        if meteo.get(cle) is not None:
            lues['meteo.' + cle] = (libelle, _texte_hypothese(meteo[cle]))
    fichier = simulation.get('meteo_fichier')
    if fichier is not None:
        lues['meteo.fichier'] = ('Fichier météo déposé',
                                 _texte_hypothese(fichier))
    return lues


def hypotheses_comparees(resultats):
    """ACAL883 — les variantes comparées reposent-elles sur les MÊMES
    hypothèses de pertes et de météo ?

    Args:
        resultats: ``{variante_id: resultat}`` des seules variantes simulées
            et non périmées (l'appelant filtre : une variante non simulée
            n'est pas comparée).

    Returns:
        ``{identiques, comparees, differences}`` — ``identiques`` vaut
        ``None`` sous deux variantes comparées ; chaque différence porte
        ``cle``, ``libelle`` et ``valeurs`` (``{id: texte}``, « non saisi »
        quand un côté ne porte pas la clé). Rien n'est recalculé.
    """
    lues = {str(identifiant): _hypotheses_du_resultat(resultat)
            for identifiant, resultat in resultats.items()}
    if len(lues) < 2:
        return {'identiques': None, 'comparees': len(lues),
                'differences': []}
    cles = []
    for hypotheses in lues.values():
        cles.extend(cle for cle in hypotheses if cle not in cles)
    differences = []
    for cle in cles:
        valeurs = {identifiant: (hypotheses[cle][1] if cle in hypotheses
                                 else 'non saisi')
                   for identifiant, hypotheses in lues.items()}
        if len(set(valeurs.values())) > 1:
            libelle = next(h[cle][0] for h in lues.values() if cle in h)
            differences.append({'cle': cle, 'libelle': libelle,
                                'valeurs': valeurs})
    return {'identiques': not differences, 'comparees': len(lues),
            'differences': differences}

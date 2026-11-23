"""ACAL857 — « prêt à envoyer ? » : les contrôles de PORTE, sans lever.

La porte unique ``feu_vert.verifier_avant_publication`` (geste ``devis``)
LÈVE à la PREMIÈRE porte fermée : capter son erreur ne dit rien de
l'approbation quand le feu vert manque. Ce module l'APPELLE (aucune règle
recopiée) et traduit son verdict en contrôles de la forme du contrat
``contract_samples/calepinage_pret_a_envoyer.json`` — sans jamais lever,
sans rien écrire : lecture seule.

Codes produits ici (``codes_produits`` du contrat) : ``visite_validee``,
``approbation_a_jour``, ``conception_perimee``, ``simulation_fraiche``,
``kwh_declare``.
"""
from __future__ import annotations

import logging
import re
from contextvars import ContextVar

#: H3 (22/11) — la mémoire d'UNE lecture d'``agreger`` (par requête, jamais
#: globale) : le résultat servi, le rapport de publication et le matériel
#: qu'il a résolu sont calculés UNE fois et lus par chaque producteur qui en a
#: besoin. Posée et retirée par ``agreger`` ; hors de lui (un producteur appelé
#: seul), rien n'est gardé : aucune lecture ne peut servir un verdict périmé.
_LECTURE = ContextVar('pret_a_envoyer_lecture', default=None)


def _partage(calepinage, cle, calcul):
    """``calcul()`` une fois par lecture d'``agreger`` (clé : pk + ``cle``)."""
    memoire = _LECTURE.get()
    if memoire is None:
        return calcul()
    cle = (getattr(calepinage, 'pk', None), cle)
    if cle not in memoire:
        memoire[cle] = calcul()
    return memoire[cle]


def _empreinte_de_lecture(calepinage, cle):
    """H5 — la clé d'``une_fois_par_lecture`` : tout ce dont le calcul dépend.

    Le pk ET l'instance (une autre instance du même pk, relue ou modifiée en
    mémoire, ne reçoit pas le calcul d'une autre), le document et le
    ``resultat`` portés PAR CETTE instance (un document rebranché en mémoire
    change la clé), le devis lié et la société."""
    return (cle, getattr(calepinage, 'pk', None), id(calepinage),
            id(getattr(calepinage, 'roof_layout', None)),
            id(getattr(calepinage, 'resultat', None)),
            getattr(calepinage, 'devis_id', None),
            getattr(calepinage, 'company_id', None))


def une_fois_par_lecture(cle):
    """H5 — décorateur : ``fonction(calepinage)`` calculée UNE fois par lecture.

    Seulement pendant une lecture d'``agreger`` (``_LECTURE`` posée) ET pour
    l'appel SANS aucune option (pas d'``entree``/``layout``/``materiel``…, ni
    argument positionnel en plus) : un appel qui évalue autre chose que
    l'enregistré est toujours recalculé. Hors lecture : l'appel tel quel,
    rien n'est gardé. Un refus (exception) est gardé aussi : le calcul est
    déterministe le temps d'une lecture, le même refus est relevé à chaque
    appel, comme avant, sans être recalculé.
    Le résultat gardé est PARTAGÉ : les appelants le lisent sans le modifier.
    Le calcul passe par ``enveloppe.__wrapped__`` (posé par ``wraps``) : un
    test peut l'espionner pour compter les calculs réels.
    """
    import functools

    def decorer(fonction):
        @functools.wraps(fonction)
        def enveloppe(calepinage, *args, **options):
            calcul = enveloppe.__wrapped__
            memoire = _LECTURE.get()
            if (memoire is None or args
                    or any(v is not None for v in options.values())):
                return calcul(calepinage, *args, **options)
            empreinte = _empreinte_de_lecture(calepinage, cle)
            if empreinte not in memoire:
                try:
                    memoire[empreinte] = (True, calcul(calepinage))
                except Exception as refus:  # le MÊME refus, relevé à chaque appel
                    logging.getLogger(__name__).debug('refus gardé pour la lecture', exc_info=True)
                    memoire[empreinte] = (False, refus)
            reussi, valeur = memoire[empreinte]
            if not reussi:
                raise valeur
            return valeur
        return enveloppe
    return decorer


def _resultat(calepinage):
    """Le ``resultat`` servi (``GET resultat/``), une fois par lecture."""
    from .. import selectors

    return _partage(calepinage, 'resultat',
                    lambda: selectors.resultat_servi(calepinage) or {})


def _rapport(calepinage):
    """``(publication, conception, materiel)`` du verdict publiable, une fois."""
    from .electrique import _rapport_publication

    return _partage(calepinage, 'publication',
                    lambda: _rapport_publication(calepinage))


NON_EXIGE = 'Non exigé par votre société'
SANS_LEAD = 'Sans lead : non applicable'
A_LA_CREATION = 'Vérifié à la création du devis'

CIBLE_VISITE = {'etape': 'documents', 'onglet': 'releve', 'champ': ''}
CIBLE_DOCUMENTS = {'etape': 'documents', 'onglet': 'documents', 'champ': ''}
CIBLE_PRODUCTION = {'etape': 'resultats', 'onglet': 'production',
                    'champ': ''}
CIBLE_KWH = {'etape': 'resultats', 'onglet': 'production',
             'champ': 'conso_mensuelle_kwh'}


def _controle(code, libelle, etat, valeur_texte, *, cause='', geste='',
              cible=None):
    return {'code': code, 'libelle': libelle, 'etat': etat,
            'valeur_texte': valeur_texte, 'cause': cause, 'geste': geste,
            'cible': dict(cible or CIBLE_DOCUMENTS), 'seuil_source': None}


def _visite(etat, valeur, **autres):
    return _controle('visite_validee', 'Visite technique validée', etat,
                     valeur, cible=CIBLE_VISITE, **autres)


def _approbation(etat, valeur, **autres):
    return _controle('approbation_a_jour', 'Approbation à jour', etat,
                     valeur, **autres)


def _premier(detail, cle):
    valeurs = detail.get(cle) if isinstance(detail, dict) else None
    return str(valeurs[0]) if valeurs else ''


def _portes(calepinage):
    """Feu vert de la visite + approbation : LA porte, jamais recopiée."""
    from rest_framework.exceptions import ValidationError

    from .approbation import approbation_exigee
    from .feu_vert import (
        GESTE_DEVIS, _lead_id_de_reference, _option_active,
        verifier_avant_publication,
    )

    lead_id = _lead_id_de_reference(calepinage)
    if lead_id is None and getattr(calepinage, 'devis', None) is None:
        return [_visite('info', SANS_LEAD), _approbation('info', SANS_LEAD)]
    company = getattr(calepinage, 'company', None)
    option = _option_active(company)
    try:
        verifier_avant_publication(calepinage, geste=GESTE_DEVIS)
        refus = {}
    except ValidationError as erreur:
        refus = erreur.detail if isinstance(erreur.detail, dict) else {}
    if 'feu_vert' in refus:
        return [
            _visite('bloquant', 'Non validée',
                    cause=_premier(refus, 'feu_vert'),
                    geste='Faire valider la visite'),
            _approbation('info', "Non évaluée tant que la visite n'est pas "
                                 'validée')]
    if not option:
        visite = _visite('ok', NON_EXIGE)
    elif lead_id is None:
        visite = _visite('info', SANS_LEAD)
    else:
        visite = _visite('ok', 'Validée')
    if 'approbation' in refus:
        approbation = _approbation(
            'bloquant', 'Non approuvée ou périmée',
            cause=_premier(refus, 'approbation'),
            geste='Demander l’approbation de la conception')
    elif not approbation_exigee(company):
        approbation = _approbation('ok', NON_EXIGE)
    else:
        approbation = _approbation('ok', 'À jour')
    return [visite, approbation]


def _simulation(calepinage):
    from .comparaison import (
        _hash_de_simulation, simulation_perimee_du_calepinage,
    )

    libelle = 'Simulation à jour'
    if not _hash_de_simulation(getattr(calepinage, 'resultat', None)):
        return _controle('simulation_fraiche', libelle, 'a_regler',
                         'Jamais lancée', geste='Lancer la simulation',
                         cible=CIBLE_PRODUCTION)
    if simulation_perimee_du_calepinage(calepinage):
        return _controle(
            'simulation_fraiche', libelle, 'a_regler',
            'Lancée avant la dernière modification',
            cause='La production affichée ne correspond plus à la '
                  'conception.',
            geste='Relancer la simulation', cible=CIBLE_PRODUCTION)
    return _controle('simulation_fraiche', libelle, 'ok', 'À jour',
                     cible=CIBLE_PRODUCTION)


def _devis_lie(calepinage):
    libelle_conception = 'Devis à jour de la conception'
    libelle_kwh = 'Consommation déclarée cohérente avec les factures'
    devis = getattr(calepinage, 'devis', None)
    if devis is None:
        return [_controle('conception_perimee', libelle_conception, 'info',
                          A_LA_CREATION),
                _controle('kwh_declare', libelle_kwh, 'info', A_LA_CREATION,
                          cible=CIBLE_KWH)]
    from apps.ventes.selectors_calepinage import refus_kwh_declare_du_devis

    from ..serializers import peremption_du_calepinage

    if peremption_du_calepinage(devis, calepinage).get('layout_stale'):
        conception = _controle(
            'conception_perimee', libelle_conception, 'a_regler',
            'Le devis ne suit plus la conception',
            cause='La conception a changé depuis la dernière mise à jour '
                  'du devis.',
            geste='Resynchroniser le devis')
    else:
        conception = _controle('conception_perimee', libelle_conception,
                               'ok', 'À jour')
    refus = refus_kwh_declare_du_devis(devis)
    if refus is not None:
        kwh = _controle('kwh_declare', libelle_kwh, 'bloquant',
                        'Contredite par les factures',
                        cause=refus.get('detail') or '',
                        geste='Corriger la consommation du lead',
                        cible=CIBLE_KWH)
    else:
        kwh = _controle('kwh_declare', libelle_kwh, 'ok', 'Cohérente',
                        cible=CIBLE_KWH)
    return [conception, kwh]


def controles_de_porte(calepinage):
    """Les cinq contrôles de porte, dans l'ordre du contrat. Ne lève pas."""
    return [*_portes(calepinage), _simulation(calepinage),
            *_devis_lie(calepinage)]


# ── ACAL858 — les contrôles ÉLECTRIQUES : l'état d'ACAL934 et les lignes
# servies, LUS (aucun seuil, aucun message ni rangement électrique recopié).
CIBLE_MATERIEL = {'etape': 'electrique', 'onglet': 'materiel', 'champ': ''}
#: ACAL1506 — l'onglet qui RÈGLE chaque contrôle électrique (clés d'``ONGLETS``,
#: ``atelier/onglets.js``, toutes de l'étape Électrique) ; sans entrée : le Schéma.
_ONGLET_DU_CONTROLE = {'verdict_electrique': 'verdict-electrique',
                       'chutes_tension': 'cheminement-cables',
                       'terre_protections': 'decisions-electriques'}
#: Le statut d'un motif de publication (``_rapport_publication``) dit en
#: état de contrôle : bloquant reste bloquant, tout autre non-ok est à régler.
_ETAT_DU_MOTIF = {'bloquant': 'bloquant'}
_RANG = {'ok': 0, 'info': 1, 'a_regler': 2, 'bloquant': 3}


def _elec(code, libelle, etat, valeur, **autres):
    autres.setdefault('cible', {
        'etape': 'electrique',
        'onglet': _ONGLET_DU_CONTROLE.get(code, 'schema'), 'champ': ''})
    return _controle(code, libelle, etat, valeur, **autres)


def _depuis_motifs(code, libelle, motifs, *, geste):
    """La ligne qui résume des motifs servis : le pire statut, le 1er motif."""
    if not motifs:
        return _elec(code, libelle, 'ok', 'Aucun point relevé')
    from . import synthese_publication as _synthese

    etats = [_ETAT_DU_MOTIF.get(m['statut'], 'a_regler') for m in motifs]
    pire = max(etats, key=_RANG.get)
    return _elec(code, libelle, pire, _synthese._points(len(motifs)),
                 cause=motifs[0]['libelle'], geste=geste)


def _verdict_electrique(publication):
    from .etat_dossier_electrique import ETATS_DOSSIER

    etat, points = publication['etat'], publication['points']
    libelle = 'Dossier électrique'
    if etat == ETATS_DOSSIER[0]:
        return _elec('verdict_electrique', libelle, 'ok', 'Prêt')
    if etat == ETATS_DOSSIER[1]:
        # ACAL1539 — « À compléter » seul : les motifs sont détaillés au Verdict.
        return _elec('verdict_electrique', libelle, 'a_regler', 'À compléter',
                     geste='Compléter le dossier électrique')
    return _elec('verdict_electrique', libelle, 'bloquant',
                 'Bloquant : %d' % points,
                 geste='Corriger le dossier électrique')


def _tension_froid(verdicts):
    from core.electrique.types import fr

    libelle = 'Tension des chaînes par grand froid'
    ligne = next((v for v in verdicts
                  if v.get('code') == 'voc_cold_under_vmax'), None)
    if ligne is None:
        return _elec('tension_froid', libelle, 'info',
                     'Non évaluée : chaînes non calculées')
    if ligne.get('conforme') is None:
        etat = 'info'
    elif ligne.get('conforme'):
        etat = 'ok'
    else:
        etat = 'bloquant' if ligne.get('bloquant') else 'a_regler'
    valeur = ligne.get('detail') or ''
    if ligne.get('temperature_c') is not None:
        valeur = '%s à %s °C' % (valeur, fr(ligne['temperature_c'], 1))
    controle = _elec('tension_froid', libelle, etat, valeur,
                     cause=ligne.get('temperature_mention') or '',
                     geste='' if etat == 'ok' else 'Revoir les chaînes')
    controle['seuil_source'] = ligne.get('source')
    return controle


def _ratio_dc_ac(ratio):
    from core.electrique.types import fr

    from .electrique import RATIO_NON_JUGE

    libelle = 'Puissance des panneaux face à l’onduleur'
    valeur = (ratio or {}).get('valeur')
    if valeur is None:
        return _elec('ratio_dc_ac', libelle, 'info',
                     'Non calculé : onduleur non désigné')
    texte = fr(valeur, 2)
    # ACAL1538 — le verdict du bloc servi, LU : ``None`` = non jugé.
    if ratio.get('dans_bornes') is None:
        return _elec('ratio_dc_ac', libelle, 'info', texte,
                     cause=RATIO_NON_JUGE + '.',
                     geste='Saisir une fourchette dans les réglages')
    etat = 'ok' if ratio.get('dans_bornes') else 'a_regler'
    controle = _elec('ratio_dc_ac', libelle, etat, '%s pour %s au plus' % (
        texte, fr(ratio.get('borne'), 2)),
        geste='' if etat == 'ok' else 'Revoir le choix de l’onduleur')
    controle['seuil_source'] = ratio.get('borne_source')
    return controle


def _chutes(troncons):
    libelle = 'Chutes de tension des câbles'
    lignes = [{'statut': 'bloquant' if v.get('bloquant') else 'alerte',
               'libelle': v.get('detail') or v.get('libelle') or ''}
              for v in (troncons or {}).get('verdicts') or ()
              if not v.get('conforme')]
    lignes += [{'statut': 'omis', 'libelle': o.get('motif') or ''}
               for o in (troncons or {}).get('omissions') or ()]
    return _depuis_motifs('chutes_tension', libelle, lignes,
                          geste='Revoir les sections de câble')


def controles_electriques(calepinage):
    """ACAL858 — les sept contrôles électriques, LUS. Ne lève pas.

    Le verdict est celui de ``verdict_publiable`` (``_rapport_publication``
    en est le seul calcul : son matériel est gardé pour ACAL906)."""
    from .electrique import CODE_FICHE_INCOMPLETE, CODE_POLYSTRING
    from .troncons import troncons_du_calepinage

    publication = _rapport(calepinage)[0]
    motifs = publication['motifs']
    resultat = _resultat(calepinage)
    verdicts = ((resultat.get('electrique') or {}).get('verdicts')) or ()
    fiche = [m for m in motifs if m['code'] == CODE_FICHE_INCOMPLETE]
    materiel = (_controle('materiel_designe', 'Matériel électrique désigné',
                          'a_regler', 'Matériel non désigné',
                          cause=fiche[0]['libelle'],
                          geste='Choisir le module et l’onduleur',
                          cible=CIBLE_MATERIEL) if fiche else
                _controle('materiel_designe', 'Matériel électrique désigné',
                          'ok', 'Désigné', cible=CIBLE_MATERIEL))
    poly = [m for m in motifs if m['code'] in (
        CODE_POLYSTRING, 'CH_PANS_PARTAGENT_UNE_ENTREE')]
    terre = [m for m in motifs if str(m['code']).startswith('TERRE_')]
    return [
        _verdict_electrique(publication), materiel,
        _tension_froid(verdicts),
        _depuis_motifs('orientation_mppt', 'Une seule orientation par entrée',
                       poly, geste='Revoir l’affectation des chaînes'),
        _ratio_dc_ac(resultat.get('ratio_dc_ac')),
        _chutes(troncons_du_calepinage(calepinage)),
        _depuis_motifs('terre_protections', 'Terre et protections', terre,
                       geste='Compléter la check-list de terre'),
    ]


# ── ACAL859 — RÉSULTAT et DOSSIER : écart PVGIS, ombrage, pièces, hypothèses.
# Aucun seuil ici : la tolérance est celle que la société a saisie.
def _ecart_pvgis(validation):
    from core.electrique.types import fr

    from .validation import VERDICT_DANS_LA_TOLERANCE, VERDICT_HORS_TOLERANCE

    libelle = 'Écart avec PVGIS'
    validation = validation or {}
    ecart, verdict = validation.get('ecart_pct'), validation.get('verdict')
    if ecart is None:
        return _controle('ecart_pvgis', libelle, 'info', 'Non comparé',
                         cause=validation.get('motif') or '',
                         cible=CIBLE_PRODUCTION)
    texte = '%s %%' % fr(ecart, 2)
    if verdict not in (VERDICT_DANS_LA_TOLERANCE, VERDICT_HORS_TOLERANCE):
        return _controle('ecart_pvgis', libelle, 'info', texte,
                         cause='Écart publié sans verdict : aucune tolérance '
                               'saisie par votre société.',
                         geste='Saisir une tolérance dans les réglages',
                         cible=CIBLE_PRODUCTION)
    hors = verdict == VERDICT_HORS_TOLERANCE
    controle = _controle(
        'ecart_pvgis', libelle, 'a_regler' if hors else 'ok', '%s pour %s %% '
        'admis' % (texte, fr(validation.get('tolerance_pct'), 2)),
        cause=(validation.get('avertissement') or '') if hors else '',
        geste='Vérifier les pertes de la chaîne' if hors else '',
        cible=CIBLE_PRODUCTION)
    controle['seuil_source'] = validation.get('tolerance_source')
    return controle


def _lisible(motif):
    """Le motif servi, rendu sans nom interne (R3-19) : la donnée ne change pas."""
    from .rapport.champs_lisibles import motif_lisible

    return motif_lisible(motif)


def _ombrage_chiffre(cascade):
    from .etapes.ombrage_proche import POSTE

    libelle = "Ombrage proche chiffré"
    etape = next((e for e in (cascade or {}).get('etapes') or ()
                  if isinstance(e, dict) and e.get('etape') == POSTE), None)
    if etape is None:
        return _controle('ombrage_chiffre', libelle, 'info',
                         'Non simulé', cible=CIBLE_PRODUCTION)
    if etape.get('motif_omission'):
        return _controle('ombrage_chiffre', libelle, 'a_regler', 'Omis',
                         cause=_lisible(etape['motif_omission']),
                         geste='Compléter les obstacles et relancer',
                         cible=CIBLE_PRODUCTION)
    perte = etape.get('perte_pct')
    return _controle('ombrage_chiffre', libelle, 'ok', 'Calculé' + (
        '' if perte is None else ' : %s %%' % perte), cible=CIBLE_PRODUCTION)


def _dossier_pieces(calepinage):
    from .reglementaire import (
        ETAT_FOURNIE, STATUT_INCOMPLET, dossiers_du_calepinage,
    )

    libelle = 'Pièces du dossier réglementaire'
    pieces = [piece['intitule']
              for dossier in dossiers_du_calepinage(calepinage)['dossiers']
              if dossier.get('statut') == STATUT_INCOMPLET
              for piece in dossier.get('pieces') or ()
              if piece.get('obligatoire') and piece['etat'] != ETAT_FOURNIE]
    if not pieces:
        return _controle('dossier_pieces', libelle, 'ok', 'Complet')
    return _controle('dossier_pieces', libelle, 'a_regler',
                     '%d pièce(s) à fournir' % len(pieces),
                     cause=', '.join(pieces), geste='Joindre les pièces')


def _hypotheses_conso(consommation):
    libelle = 'Hypothèses de consommation'
    hypotheses = (consommation or {}).get('hypotheses') \
        if isinstance(consommation, dict) else None
    if not isinstance(hypotheses, list) or not hypotheses:
        return _controle('hypotheses_conso', libelle, 'info',
                         'Aucune hypothèse servie', cible=CIBLE_KWH)
    return _controle('hypotheses_conso', libelle, 'a_regler',
                     '%d hypothèse(s) à confirmer' % len(hypotheses),
                     cause=str(hypotheses[0]),
                     geste='Confirmer la consommation', cible=CIBLE_KWH)


def controles_du_resultat(calepinage):
    """ACAL859 — les quatre contrôles de résultat et de dossier. Ne lève pas."""
    resultat = _resultat(calepinage)
    return [_ecart_pvgis(resultat.get('validation')),
            _ombrage_chiffre(resultat.get('cascade')),
            _dossier_pieces(calepinage),
            _hypotheses_conso(resultat.get('consommation'))]


# ── ACAL863 — un obstacle qui dépasse de son pan (dedans ou dehors, aucune
# distance, aucune tolérance).
#: Points d'un disque testés sur son pourtour : un ÉCHANTILLONNAGE du cercle
#: (8 = un point tous les 45°), pas une règle métier.
POINTS_DU_CERCLE = 8
CIBLE_OBSTACLES = {'etape': 'toit', 'onglet': 'obstacles', 'champ': ''}


def _points_de_l_obstacle(obstacle, local):
    """Les points de l'obstacle en mètres, ou ``None`` si dimensions absentes."""
    import math

    from .planche import _points_geo
    from .valeurs import nombre

    if obstacle.get('forme') == 'polygone':
        points = _points_geo(obstacle.get('contour'), 'lnglat')
        return [local(lat, lng) for lat, lng in points] or None
    lat, lng = nombre(obstacle.get('centerLat')), nombre(
        obstacle.get('centerLng'))
    if lat is None or lng is None:
        return None
    est, nord = local(lat, lng)
    if obstacle.get('forme') == 'cercle':
        rayon = nombre(obstacle.get('rayonM'))
        if rayon is None:
            return None
        return [(est + rayon * math.cos(2 * math.pi * k / POINTS_DU_CERCLE),
                 nord + rayon * math.sin(2 * math.pi * k / POINTS_DU_CERCLE))
                for k in range(POINTS_DU_CERCLE)]
    # ``lengthM`` = étendue NORD-SUD, ``widthM`` = EST-OUEST (schéma v2).
    nord_sud, est_ouest = (nombre(obstacle.get('lengthM')),
                           nombre(obstacle.get('widthM')))
    if nord_sud is None or est_ouest is None:
        return None
    return [(est + de * est_ouest / 2.0, nord + dn * nord_sud / 2.0)
            for de in (-1, 1) for dn in (-1, 1)]


def _libelle_obstacle(type_obstacle):
    from .degagements import DEGAGEMENTS_ATELIER, TYPES_SANS_VALEUR_ATELIER

    libelles = {t: lib for t, *_v, lib in DEGAGEMENTS_ATELIER}
    libelles.update(TYPES_SANS_VALEUR_ATELIER)
    return libelles.get(type_obstacle) or 'Obstacle'


def controle_obstacle_hors_pan(calepinage):
    """ACAL863 — ``obstacle_hors_pan`` : un point hors du contour du pan."""
    from core.calepinage.geometrie import point_dans_polygone

    from .planche import _points_geo, _projection, _zones

    libelle = 'Obstacles dans leur pan'
    layout = getattr(calepinage, 'roof_layout', None) or {}
    projection = _projection(layout)
    hors, illisible, vus = [], False, 0
    for zone in _zones(layout):
        obstacles = [o for o in zone.get('obstacles') or ()
                     if isinstance(o, dict)]
        if not obstacles:
            continue
        contour = [projection.vers_local(lat, lng) for lat, lng in
                   _points_geo(zone.get('vertices'), 'lnglat')] \
            if projection is not None else []
        for obstacle in obstacles:
            vus += 1
            points = (_points_de_l_obstacle(obstacle, projection.vers_local)
                      if len(contour) >= 3 else None)
            if points is None:
                illisible = True
            elif not all(point_dans_polygone(p, contour) for p in points):
                hors.append('%s dépasse du pan %s' % (
                    _libelle_obstacle(obstacle.get('type')),
                    zone.get('label') or zone.get('id') or '—'))
    if hors:
        return _controle('obstacle_hors_pan', libelle, 'a_regler',
                         hors[0], cause=' ; '.join(hors),
                         geste="Déplacer l'obstacle", cible=CIBLE_OBSTACLES)
    if illisible:
        return _controle('obstacle_hors_pan', libelle, 'info',
                         'Non vérifiable : contour ou dimensions absents',
                         cible=CIBLE_OBSTACLES)
    return _controle('obstacle_hors_pan', libelle, 'ok',
                     'Tous dans leur pan' if vus else 'Aucun obstacle',
                     cible=CIBLE_OBSTACLES)


# ── ACAL864 — les pans laissés vides, nommés avec le motif servi.
CIBLE_PANNEAUX = {'etape': 'panneaux', 'onglet': '', 'champ': ''}


def controle_pans_vides(calepinage):
    """ACAL864 — ``pans_vides`` lu de ``mesures_du_document`` (aucun seuil)."""
    from .mesures import mesures_du_document

    libelle = 'Pans garnis de panneaux'
    pans = mesures_du_document(getattr(calepinage, 'roof_layout', None))['pans']
    if not pans:
        return _controle('pans_vides', libelle, 'info', 'Aucun pan dessiné',
                         cible=CIBLE_PANNEAUX)
    vides = ['le pan %s n’a aucun panneau : %s' % (pan['pan'], pan['motif'])
             for pan in pans if pan['motif']]
    if not vides:
        return _controle('pans_vides', libelle, 'ok', 'Tous garnis',
                         cible=CIBLE_PANNEAUX)
    return _controle('pans_vides', libelle, 'a_regler', ' ; '.join(vides),
                     geste='Remplir le pan', cible=CIBLE_PANNEAUX)


# ── ACAL862 — la puissance annoncée par le document = modules × Wc des fiches.
#: L'epsilon d'ÉGALITÉ des deux kWc : l'arrondi d'affichage à deux décimales
#: (0,01 kWc). Ce n'est pas un seuil métier : de l'arithmétique d'arrondi,
#: comme ``validation.EPSILON_PERTE_PCT``.
EPSILON_KWC = 0.01


def controle_kwc_coherent(calepinage):
    """ACAL862 — ``kwc_coherent`` : ``result.kwc`` contre la fiche des modules."""
    from core.electrique.types import fr

    from .mesures import mesures_du_document
    from .valeurs import nombre

    libelle = 'Puissance annoncée cohérente avec les modules'
    layout = getattr(calepinage, 'roof_layout', None) or {}
    annonce = nombre((layout.get('result') or {}).get('kwc')) \
        if isinstance(layout, dict) else None
    fiche = nombre(mesures_du_document(layout).get('kwc'))
    if annonce is None or fiche is None:
        return _controle('kwc_coherent', libelle, 'info', 'Non vérifiable',
                         cible=CIBLE_PANNEAUX)
    if abs(annonce - fiche) <= EPSILON_KWC + 1e-9:
        return _controle('kwc_coherent', libelle, 'ok',
                         '%s kWc' % fr(fiche, 2), cible=CIBLE_PANNEAUX)
    return _controle(
        'kwc_coherent', libelle, 'a_regler',
        'le document annonce %s kWc, la fiche des modules donne %s kWc'
        % (fr(annonce, 2), fr(fiche, 2)),
        geste='Enregistrer le calepinage', cible=CIBLE_PANNEAUX)


# ── ACAL861 — rien ne dimensionne le système : la MÊME condition que la porte
# d'ACAL922 (``devis.taille_non_dimensionnee``), aucun seuil de taille.
CIBLE_FACTURE = {'etape': 'toit', 'onglet': '', 'champ': 'facture'}


def controle_taille_sans_facture(calepinage):
    """ACAL861 — ``taille_sans_facture`` : avertit, ne bloque jamais."""
    from core.electrique.types import fr

    from .devis import lead_sans_facture_ni_taille, taille_non_dimensionnee
    from .mesures import mesures_du_document

    libelle = 'Taille dimensionnée sur la consommation'
    # ACAL1342 — ni facture ni taille souhaitée : la réponse est connue, aucun balayage.
    if not lead_sans_facture_ni_taille(calepinage) \
            and taille_non_dimensionnee(calepinage) is None:
        return _controle('taille_sans_facture', libelle, 'ok', 'Dimensionnée',
                         cible=CIBLE_FACTURE)
    kwc = mesures_du_document(getattr(calepinage, 'roof_layout', None)).get(
        'kwc')
    if not kwc:
        return _controle('taille_sans_facture', libelle, 'info',
                         'Puissance inconnue', cible=CIBLE_FACTURE)
    return _controle(
        'taille_sans_facture', libelle, 'a_regler',
        'le toit est rempli : %s kWc' % fr(kwc, 0),
        cause='aucune facture ni taille souhaitée : le système n’est pas '
              'dimensionné sur la consommation',
        geste='Saisir la facture', cible=CIBLE_FACTURE)


# ── ACAL1171 — le chiffre que le PDF du devis imprimera : la pose réelle ou la
# ville. La cause est celle du résolveur du devis (ventes), CLASSÉE ici en geste.
CIBLE_PERTES = {'etape': 'resultats', 'onglet': 'reglages', 'champ': ''}
#: Le motif du résolveur → (état, geste, cible), au premier mot trouvé ;
#: sans mot connu : la simulation est périmée.
_MOTIFS_UN_SEUL_CHIFFRE = (
    ('illisible', 'info', '', None),
    ('rangé', 'info', '', None),  # devis envoyé : sa base rangée, sans geste
    ('marché non', 'info', '', None),
    ('aucune simulation', 'a_regler', 'Lancer la simulation', CIBLE_PRODUCTION),
    ('aucun calepinage', 'a_regler', 'Lancer la simulation', CIBLE_PRODUCTION),
    ('incomplet', 'a_regler', 'Renseigner les pertes manquantes', CIBLE_PERTES),
    ('resynchronis', 'a_regler', 'Resynchroniser le devis', CIBLE_DOCUMENTS),
    ('différentes', 'a_regler', 'Resynchroniser le devis', CIBLE_DOCUMENTS),
)


def controle_un_seul_chiffre(calepinage):
    """ACAL1171 — ``un_seul_chiffre`` : le devis lié imprimera-t-il la
    production de cette pose ? Jamais bloquant, ne lève pas."""
    from apps.ventes.selectors_calepinage import production_annoncee_du_devis

    libelle = 'Un seul chiffre de production'
    devis = getattr(calepinage, 'devis', None)
    if devis is None:
        return _controle('un_seul_chiffre', libelle, 'info', A_LA_CREATION,
                         cible=CIBLE_PRODUCTION)
    lu = production_annoncee_du_devis(
        getattr(devis, 'pk', None), getattr(calepinage, 'company', None))
    if lu is None:
        return _controle('un_seul_chiffre', libelle, 'info', 'Non vérifiable',
                         cible=CIBLE_PRODUCTION)
    if not lu['regles_a_jour']:
        return _controle(
            'un_seul_chiffre', libelle, 'info',
            'Ce devis garde la production standard de la ville (règles '
            'd’avant le 21/11)', cible=CIBLE_PRODUCTION)
    if lu['servie']:
        return _controle('un_seul_chiffre', libelle, 'ok',
                         'Le devis imprimera la production de cette pose',
                         cible=CIBLE_PRODUCTION)
    motif = lu['motif']
    etat, geste, cible = next(
        ((e, g, c) for mot, e, g, c in _MOTIFS_UN_SEUL_CHIFFRE if mot in motif),
        ('a_regler', 'Relancer la simulation', CIBLE_PRODUCTION))
    pertes = re.search(r'(\d+) pertes?', motif)
    if pertes and geste.startswith('Renseigner'):
        geste = 'Renseigner les %s pertes manquantes' % pertes.group(1)
    return _controle('un_seul_chiffre', libelle, etat,
                     'Le devis retombera sur le standard de la ville',
                     cause=motif, geste=geste, cible=cible or CIBLE_PRODUCTION)


# ── ACAL906 — la compatibilité panneau ↔ onduleur et batterie ↔ onduleur : le
# verdict de ventes (ACAL901), RELAYÉ tel quel — aucune règle recalculée ici.
#: Verdict de ventes → (rang de gravité, état du contrôle, mot affiché).
_COMPATIBILITE = {'compatible': (0, 'ok', 'Compatible'),
                  'inconnu': (1, 'info', 'Non vérifiable'),
                  'reserve': (2, 'a_regler', 'Compatible sous réserve'),
                  'incompatible': (3, 'a_regler', 'Incompatible')}


def controle_compatibilite(calepinage):
    """ACAL906 — ``compatibilite_equipements`` : le pire des deux verdicts."""
    from apps.ventes.selectors import compatibilite_du_materiel

    from .electrique import entree_stockee, resoudre_materiel
    from .equipements import equipements_du_calepinage

    libelle = 'Compatibilité du matériel'
    company = getattr(calepinage, 'company', None)
    entree = entree_stockee(calepinage)
    # H3 — le matériel que le verdict électrique vient de résoudre (même
    # entrée stockée, même devis lié) quand cette lecture l'a déjà calculé.
    memoire = _LECTURE.get() or {}
    rapport = memoire.get((getattr(calepinage, 'pk', None), 'publication'))
    materiel = (rapport[2] if rapport and rapport[2] is not None else
                resoudre_materiel(company, entree, calepinage=calepinage))
    produits = materiel['produits']
    if not (produits.get('module') and produits.get('onduleur')):
        return _controle('compatibilite_equipements', libelle, 'info',
                         'Non vérifiable : matériel non désigné',
                         cause=' ; '.join(materiel['absents']),
                         geste='Choisir le module et l’onduleur',
                         cible=CIBLE_MATERIEL)
    batterie = (entree.get('batterie') or {}).get('produit')
    if batterie in (None, '') and getattr(calepinage, 'devis_id', None):
        batterie = ((equipements_du_calepinage(calepinage) or {})
                    .get('batterie') or {}).get('produit')
    servis = compatibilite_du_materiel(
        produits['module'], produits['onduleur'], company, batterie)
    lignes = [v for v in (servis['panneau_onduleur'],
                          servis['batterie_onduleur']) if v]
    rang = max(_COMPATIBILITE[v['statut']][0] for v in lignes)
    pires = [v for v in lignes if _COMPATIBILITE[v['statut']][0] == rang]
    _, etat, valeur = _COMPATIBILITE[pires[0]['statut']]
    return _controle(
        'compatibilite_equipements', libelle, etat, valeur,
        cause=' ; '.join(r for v in pires for r in v['raisons']),
        geste='Revoir le choix du matériel' if etat == 'a_regler' else '',
        cible=CIBLE_MATERIEL)


# ── ACAL860 — l'agrégat : tous les contrôles, rangés rouge, orange, info, vert.
CIBLE_PENTE = {'etape': 'toit', 'onglet': 'pente', 'champ': ''}
#: L'ordre d'affichage : le plus grave en tête (rangement, pas un seuil).
ORDRE_DES_ETATS = ('bloquant', 'a_regler', 'info', 'ok')


def controle_pentes_confirmees(calepinage):
    """ACAL860 — ``pentes_confirmees`` : les messages d'ACAL426, LUS."""
    from .hypotheses_toit import avertissements_hypotheses

    libelle = 'Pentes et faces confirmées'
    messages = avertissements_hypotheses(
        getattr(calepinage, 'roof_layout', None))
    if not messages:
        return _controle('pentes_confirmees', libelle, 'ok', 'Confirmées',
                         cible=CIBLE_PENTE)
    return _controle('pentes_confirmees', libelle, 'a_regler',
                     '%d hypothèse(s) à confirmer' % len(messages),
                     cause=' '.join(messages), geste='Confirmer la pente',
                     cible=CIBLE_PENTE)


def agreger(calepinage, producteurs, *, etape=None):
    """ACAL860 — la réponse de ``GET pret-a-envoyer/`` (lecture seule).

    ``producteurs`` : les fonctions de contrôle de ce module (la table vit
    dans ``views/pret_a_envoyer.py``) ; chacune rend un contrôle ou une liste.
    Tri STABLE : à état égal, l'ordre des producteurs est gardé.
    H3 — une mémoire de lecture (``_LECTURE``) vit le temps de cet appel ;
    ``etape`` (le filtre ``?etape=`` de la vue, ``None`` = tous) est rendu."""
    controles = []
    jeton = _LECTURE.set({})
    try:
        for producteur in producteurs:
            rendu = producteur(calepinage)
            controles.extend(rendu if isinstance(rendu, list) else [rendu])
    finally:
        _LECTURE.reset(jeton)
    controles.sort(key=lambda c: ORDRE_DES_ETATS.index(c['etat']))
    bloquants = sum(c['etat'] == 'bloquant' for c in controles)
    a_regler = sum(c['etat'] == 'a_regler' for c in controles)
    return {'calepinage': calepinage.pk, 'etape': etape,
            'pret': not (bloquants or a_regler),
            'nombre_bloquants': bloquants, 'nombre_a_regler': a_regler,
            'controles': controles}

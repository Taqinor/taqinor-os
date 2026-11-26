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
              cible=None, points=()):
    # T4-U4-007 — ``points`` : les points qui font l'état (servi vide ailleurs).
    return {'code': code, 'libelle': libelle, 'etat': etat,
            'valeur_texte': valeur_texte, 'cause': cause, 'geste': geste,
            'cible': dict(cible or CIBLE_DOCUMENTS), 'seuil_source': None,
            'points': list(points)}


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
        # La cause est celle que SERT ``GET resultat/`` (``motif``, ``electrique._simulation_servie`` : « un réglage
        # de la société a changé » seulement quand la trace figée le prouve) — jamais une cause devinée ici.
        motif = str(_resultat(calepinage).get('motif') or '').strip()
        if not motif:
            motif = ('simulation périmée : le document ou un réglage de la société a changé '
                     'depuis le calcul précédent')
        return _controle(
            'simulation_fraiche', libelle, 'a_regler', 'Périmée',
            cause=motif[:1].upper() + motif[1:] + '.',
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
        # T4-X7-006 : « cette version reprend les lignes de la V(n-1) » n'est PAS dite ici : aucun fait servi
        # par apps/ventes ne prouve que les lignes sont encore la copie (resynchronisée puis périmée de
        # nouveau, ou recomposée par reviser_sur_la_conception). Il faudra un marqueur servi par ventes.
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
#: ACAL1703 — chaque ``cible.onglet`` est une clé d'``ONGLETS`` (``atelier/onglets.js``)
#: ou la route nommée ``reglages`` : une clé inconnue retombait sur « Plan importé ».
CIBLE_MATERIEL = {'etape': 'electrique', 'onglet': 'materiel-electrique', 'champ': ''}
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


def _geste_et_onglet(code, libelle, defaut):
    """T4-U4-007 — ``(geste, onglet)`` d'un motif de publication : les gestes
    des contrôles de cette page, rangés par famille de code ; sinon ``defaut``
    sur l'onglet du Verdict."""
    code = str(code or '')
    if code == 'FICHE_INCOMPLETE':
        return ('Compléter la fiche%s' % _DU_ROLE.get(_role_et_champ(libelle)[0], ' du matériel'),
                CIBLE_MATERIEL['onglet'])
    if code.startswith('TERRE_'):
        return 'Compléter la check-list de terre', _ONGLET_DU_CONTROLE['terre_protections']
    if code.startswith(('TRONCON_', 'CHUTE_')):
        return 'Revoir les sections de câble', _ONGLET_DU_CONTROLE['chutes_tension']
    if code in ('POLYSTRING', 'CH_PANS_PARTAGENT_UNE_ENTREE', 'AFFECTATION_REFUSEE'):
        return 'Revoir l’affectation des chaînes', _ONGLET_DU_CONTROLE['verdict_electrique']
    if code == 'voc_cold_under_vmax':
        return 'Revoir les chaînes', _ONGLET_DU_CONTROLE['verdict_electrique']
    if code == 'vmp_hot_over_mppt_min':
        return GESTE_TENSION_CHAUD, _ONGLET_DU_CONTROLE['verdict_electrique']
    return defaut, _ONGLET_DU_CONTROLE['verdict_electrique']


def _points_du_dossier(motifs, defaut):
    """T4-U4-007 — les points que « Bloquant : N » / « À compléter » comptent :
    code, phrase du verdict (servie telle quelle), geste et onglet."""
    from .etat_dossier_electrique import motifs_comptes

    points = []
    for motif in motifs_comptes(motifs):
        geste, onglet = _geste_et_onglet(motif.get('code'), motif.get('libelle'), defaut)
        points.append({'code': motif.get('code'), 'phrase': motif.get('libelle') or '',
                       'geste': geste,
                       'cible': {'etape': 'electrique', 'onglet': onglet, 'champ': ''}})
    return points


def _verdict_electrique(publication):
    from .etat_dossier_electrique import ETATS_DOSSIER

    etat, points = publication['etat'], publication['points']
    libelle = 'Dossier électrique'
    if etat == ETATS_DOSSIER[0]:
        return _elec('verdict_electrique', libelle, 'ok', 'Prêt')
    geste = ('Compléter le dossier électrique' if etat == ETATS_DOSSIER[1]
             else 'Corriger le dossier électrique')
    detail = _points_du_dossier(publication.get('motifs'), geste)
    cause = detail[0]['phrase'] if detail else ''
    if etat == ETATS_DOSSIER[1]:
        # ACAL1539 — « À compléter » seul : les motifs sont détaillés au Verdict.
        return _elec('verdict_electrique', libelle, 'a_regler', 'À compléter',
                     geste=geste, cause=cause, points=detail)
    return _elec('verdict_electrique', libelle, 'bloquant',
                 'Bloquant : %d' % points, geste=geste, cause=cause,
                 points=detail)


def _phrase_du_verdict(ligne, repli):
    """R5C-N3 / T4-X9-002 — la phrase SERVIE d'un verdict refusé (``raison``, ``raisons_verdicts``) : elle dit
    de quoi on parle et ce que l'onduleur admet, là où ``detail`` (la mesure brute de l'installateur) parle de
    « borne de fiche ». Un verdict conforme, ou sans raison servie, garde ``repli``. UNE seule phrase par
    verdict : tous les écrans qui la disent la lisent ici ou dans ``verdicts[].raison``."""
    raison = ligne.get('raison') if not ligne.get('conforme') else None
    if not (isinstance(raison, str) and raison.strip()):
        return repli
    return raison[:1].upper() + raison[1:]


def _non_calcule(code, libelle, ligne, motif_fiche):
    """Le contrôle d'un verdict servi SANS jugement (``conforme`` None) : en régime micro-onduleurs le serveur sert
    ``detail = MOTIF_MICRO_SEUL`` (aucun onduleur de chaîne) — la fiche n'est PAS incomplète, on dit ce détail servi,
    sans geste (comme ``_tension_froid``) ; sinon la borne manque à la fiche de l'onduleur : ``motif_fiche`` + geste.
    UN seul helper pour la chaleur et le courant."""
    from .chaines import MOTIF_MICRO_SEUL

    if ligne.get('detail') == MOTIF_MICRO_SEUL:
        return _elec(code, libelle, 'info', MOTIF_MICRO_SEUL)
    return _elec(code, libelle, 'info', motif_fiche,
                 geste='Compléter la fiche de l’onduleur', cible=CIBLE_MATERIEL)


def _courant_entree(verdicts):
    """R5C-N3 — le courant des panneaux face à l'entrée de l'onduleur (verdict servi
    ``courant_par_entree_mppt``) : jusqu'ici absent des contrôles, « Contrôles · 7 bons » se taisait alors que
    le plan disait « à revoir ». Même rangement que la chaleur : non conforme ⇒ bloquant si le verdict l'est
    (Isc publié dépassé), sinon à régler (l'Imp dépassé fait écrêter, c'est une alerte par décision) ; borne
    absente ⇒ « non calculé », jamais vert."""
    libelle = 'Courant des panneaux face à l’entrée de l’onduleur'
    ligne = next((v for v in verdicts if v.get('code') == 'courant_par_entree_mppt'), None)
    if ligne is None:
        return _elec('courant_entree', libelle, 'info', 'Non évalué : chaînes non calculées')
    if ligne.get('conforme') is None:
        return _non_calcule('courant_entree', libelle, ligne,
                            'Non calculé : courant admissible manquant sur la fiche de l’onduleur')
    if ligne.get('conforme'):
        etat = 'ok'
    else:
        etat = 'bloquant' if ligne.get('bloquant') else 'a_regler'
    controle = _elec('courant_entree', libelle, etat, _phrase_du_verdict(ligne, ligne.get('detail') or ''),
                     geste='' if etat == 'ok' else 'Revoir les chaînes')
    controle['seuil_source'] = ligne.get('source')
    return controle


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
    valeur = _phrase_du_verdict(ligne, valeur)  # R5C — la phrase d'un refus se dit en mots du métier
    controle = _elec('tension_froid', libelle, etat, valeur,
                     cause=ligne.get('temperature_mention') or '',
                     geste='' if etat == 'ok' else 'Revoir les chaînes')
    controle['seuil_source'] = ligne.get('source')
    return controle


#: T4-U4-012 — le geste quand la chaîne tombe sous le bas de la plage MPPT à chaud.
GESTE_TENSION_CHAUD = ('Ajoutez des panneaux à la chaîne ou choisissez un onduleur '
                       'dont la plage commence plus bas')
CAUSE_TENSION_CHAUD = ('La chaîne est trop courte : quand les panneaux chauffent, sa '
                       'tension passe sous le bas de la plage de l’onduleur et la '
                       'production de ces heures est perdue.')


def _tension_chaud(verdicts):
    """T4-U4-012 — le jumeau de :func:`_tension_froid`, à la température chaude.

    Lit le verdict servi ``vmp_hot_over_mppt_min`` (``electrique._verdicts_electriques``) :
    une chaîne trop courte sort de la plage MPPT quand les modules chauffent, et la
    simulation retire ces heures (étape « Fenêtre MPPT », ``etapes/mppt.py``). Même
    rangement que le froid : non conforme ⇒ bloquant si le verdict l'est, sinon à
    régler ; borne absente de la fiche ⇒ « non calculé » qui NOMME le champ, jamais vert.
    """
    from core.electrique.types import fr

    libelle = 'Tension des chaînes par forte chaleur'
    ligne = next((v for v in verdicts
                  if v.get('code') == 'vmp_hot_over_mppt_min'), None)
    if ligne is None:
        return _elec('tension_chaud', libelle, 'info',
                     'Non évaluée : chaînes non calculées')
    if ligne.get('conforme') is None:
        return _non_calcule('tension_chaud', libelle, ligne,
                            'Non calculé : bas de la plage MPPT manquant sur la fiche '
                            'de l’onduleur')
    if ligne.get('conforme'):
        etat = 'ok'
    else:
        etat = 'bloquant' if ligne.get('bloquant') else 'a_regler'
    valeur = ligne.get('detail') or ''
    if ligne.get('temperature_c') is not None:
        valeur = '%s à %s °C' % (valeur, fr(ligne['temperature_c'], 1))
    valeur = _phrase_du_verdict(ligne, valeur)  # R5C — la phrase d'un refus se dit en mots du métier
    mention = ligne.get('temperature_mention') or ''
    cause = mention if etat == 'ok' else ' '.join(
        filter(None, (CAUSE_TENSION_CHAUD, mention)))
    controle = _elec('tension_chaud', libelle, etat, valeur, cause=cause,
                     geste='' if etat == 'ok' else GESTE_TENSION_CHAUD)
    controle['seuil_source'] = ligne.get('source')
    return controle


#: ACAL1704 — le complément d'un champ de fiche manquant (« module : Vmp » est
#: le libellé servi par ``chaines.concevoir`` : « <rôle> : <champ> »).
_DU_ROLE = {'module': ' du module', 'onduleur': ' de l’onduleur'}


def _role_et_champ(libelle):
    """``('module', 'tension … (Vmp)')`` d'un motif « module : tension … (Vmp) »."""
    role, separateur, champ = str(libelle or '').partition(' : ')
    return (role.strip().lower(), champ.strip()) if separateur else ('', str(libelle or ''))


def _ratio_dc_ac(ratio, *, pourquoi='onduleur non désigné', devis_recu=False, verdict=None):
    """Dossier d'APPEL D'OFFRES seulement (hors moteur unique) : le bloc servi du calepinage,
    jugé contre l'exigence de marché du dossier."""
    valeur = (ratio or {}).get('valeur')
    if valeur is None:
        return _elec('ratio_dc_ac', LIBELLE_RATIO, 'info', 'Non calculé : %s' % pourquoi)
    from core.electrique.types import fr

    from .ratio_devis import detail_ratio

    conforme = bool(ratio.get('dans_bornes'))
    texte = (verdict or {}).get('detail') or detail_ratio(fr(valeur, 2), conforme, (
        ratio.get('borne'), None, ratio.get('borne_source'), ratio.get('borne_reference')))
    return _ratio_juge(conforme, texte, ratio.get('borne_source'), devis_recu=devis_recu)


LIBELLE_RATIO = 'Puissance des panneaux face à l’onduleur'
#: ACAL2016 — sans conception rangée, le contrôle ne rejuge rien : il le dit.
MOTIF_SANS_CONCEPTION = 'Non calculé : conception non calculée'


def _ratio_juge(conforme, texte, source, *, devis_recu=False, cause=''):
    if conforme:
        controle = _elec('ratio_dc_ac', LIBELLE_RATIO, 'ok', texte)
    elif devis_recu:
        # Le client a déjà reçu ce devis : un écart avec lui s'INFORME, il ne bloque pas.
        controle = _elec('ratio_dc_ac', LIBELLE_RATIO, 'info', texte,
                         cause=' '.join(filter(None, ('Écart avec le devis déjà envoyé.', cause))))
    else:
        controle = _elec('ratio_dc_ac', LIBELLE_RATIO, 'a_regler', texte, cause=cause,
                         geste='Revoir le choix de l’onduleur')
    controle['seuil_source'] = source
    return controle


def _ratio_de_la_conception(jugement, *, devis_recu=False):
    """ACAL2016 (D-ACAL-97) — les verdicts RANGÉS par le moteur unique (``valeurs.verdicts``
    de l'option retenue, contrat ``conception_lead.json``), LUS tels quels : ratio panneaux /
    onduleur, capacité publiée d'un hybride (D-HYB-1), longueur de chaîne. Relecture E6 M4 :
    une pose d'un AUTRE nombre de panneaux est jugée par la MÊME règle, à la porte du moteur
    (``ventes.selectors_conception.verdicts_pour_le_calepinage``), et la ligne dit pour quoi.
    ``jugement`` = ``(verdicts | None, note, a_recalculer)``."""
    from apps.ventes.selectors_conception import MOTIF_A_RECALCULER

    verdicts, note, a_recalculer = jugement
    if a_recalculer:  # relecture E6 m3 : version d'avant les verdicts, relance en file
        return _elec('ratio_dc_ac', LIBELLE_RATIO, 'info', 'Non calculé : %s' % MOTIF_A_RECALCULER)
    if verdicts is None:
        return _elec('ratio_dc_ac', LIBELLE_RATIO, 'info', MOTIF_SANS_CONCEPTION)
    ratio = verdicts.get('ratio_dc_ac') or {}
    if ratio.get('conforme') is None:
        motif = verdicts.get('non_calcule') or 'onduleur non désigné par la conception'
        if 'autre option' in motif:  # relecture E6 m3 : rien à compléter, l'option servie est l'autre
            return _elec('ratio_dc_ac', LIBELLE_RATIO, 'info', 'Non calculé : %s' % motif)
        # Relecture E6 — jamais un « conforme » muet : le moteur DIT ce qui manque et où le remplir.
        return _elec('ratio_dc_ac', LIBELLE_RATIO, 'a_regler', 'Non calculé : %s' % motif,
                     geste='Compléter la fiche technique du produit', cible=CIBLE_MATERIEL)
    autres = [v for v in (verdicts.get('capacite_hybride'), verdicts.get('longueur_chaine')) if v]
    conforme = ratio['conforme'] and all(v.get('conforme') for v in autres)
    cause = ' ; '.join(v.get('detail') or '' for v in autres if not v.get('conforme'))
    texte = ratio.get('detail') or ''
    return _ratio_juge(conforme, '%s (%s)' % (texte, note) if note else texte, ratio.get('borne_source'),
                       devis_recu=devis_recu, cause=cause)


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


def _verdicts_de_la_conception(calepinage):
    """``(verdicts, note, a_recalculer)`` pour CETTE pose face à la conception COURANTE
    (relecture E6 M4, ``ventes.selectors_conception.verdicts_pour_le_calepinage``) ;
    ``(None, '', False)`` sans conception complète (ACAL2016)."""
    from apps.ventes.selectors_conception import verdicts_pour_le_calepinage

    from .devis_retenu import conception_du_calepinage

    conception = conception_du_calepinage(calepinage)
    if not conception or conception.get('etat') != 'complet':
        return None, '', False
    return verdicts_pour_le_calepinage(calepinage.company, conception, _pose_jugee(calepinage))


def _pose_jugee(calepinage):
    """La pose de ce calepinage telle que le contrôle la juge : compte et kWc posés, ratio et
    chaînes de SA conception électrique, onduleur résolu (lectures déjà faites par lecture)."""
    from .. import selectors

    mesures = selectors.mesures_du_calepinage(calepinage) or {}
    _publication, conception, resolu = _rapport(calepinage)
    return {'nb_panneaux': mesures.get('modules'), 'kwc': mesures.get('kwc'),
            'ratio': (_resultat(calepinage).get('ratio_dc_ac') or {}).get('valeur'),
            'onduleur_produit': ((resolu or {}).get('produits') or {}).get('onduleur'),
            'chaines': [{'nb_modules': c.nb_modules} for c in getattr(conception, 'chaines', None) or ()]}


def controles_electriques(calepinage):
    """ACAL858 — les neuf contrôles électriques (T4-U4-012 : la chaleur), LUS. Ne lève pas.

    Le verdict est celui de ``verdict_publiable`` (``_rapport_publication``
    en est le seul calcul : son matériel est gardé pour ACAL906)."""
    from .electrique import CODE_FICHE_INCOMPLETE, CODE_POLYSTRING
    from .devis_retenu import conception_du_devis_lie  # ACAL1954
    from .troncons import troncons_du_calepinage

    publication, _conception, resolu = _rapport(calepinage)
    motifs = publication['motifs']
    resultat = _resultat(calepinage)
    verdicts = ((resultat.get('electrique') or {}).get('verdicts')) or ()
    fiche = [m for m in motifs if m['code'] == CODE_FICHE_INCOMPLETE]
    # ACAL1704 — « Non désigné » (rien choisi : ``resoudre_materiel`` le nomme
    # dans ``absents``) n'est pas « Fiche incomplète » (choisi, fiche à compléter).
    absents = list((resolu or {}).get('absents') or ())
    if absents:
        materiel = _controle('materiel_designe', 'Matériel électrique désigné',
                             'a_regler', 'Non désigné', cause=' ; '.join(absents),
                             geste='Choisir le module et l’onduleur',
                             cible=CIBLE_MATERIEL)
    elif fiche:
        role, champ = _role_et_champ(fiche[0]['libelle'])
        materiel = _controle('materiel_designe', 'Matériel électrique désigné',
                             'a_regler', 'Fiche incomplète : %s%s' % (
                                 champ, _DU_ROLE.get(role, '')),
                             cause=' ; '.join(m['libelle'] for m in fiche),
                             geste='Compléter la fiche%s' % _DU_ROLE.get(role, ''),
                             cible=CIBLE_MATERIEL)
    else:
        materiel = _controle('materiel_designe', 'Matériel électrique désigné',
                             'ok', 'Désigné', cible=CIBLE_MATERIEL)
    if absents:
        pourquoi_ratio = absents[0].split(' — ')[0]
    elif fiche:
        pourquoi_ratio = 'fiche%s incomplète' % _DU_ROLE.get(_role_et_champ(fiche[0]['libelle'])[0], '')
    else:
        pourquoi_ratio = 'onduleur non désigné'
    devis_recu = bool((conception_du_devis_lie(calepinage) or {}).get('recu'))
    poly = [m for m in motifs if m['code'] in (
        CODE_POLYSTRING, 'CH_PANS_PARTAGENT_UNE_ENTREE')]
    terre = [m for m in motifs if str(m['code']).startswith('TERRE_')]
    return [
        _verdict_electrique(publication), materiel,
        _tension_froid(verdicts), _tension_chaud(verdicts), _courant_entree(verdicts),
        _depuis_motifs('orientation_mppt', 'Une seule orientation par entrée',
                       poly, geste='Revoir l’affectation des chaînes'),
        (_ratio_dc_ac(resultat.get('ratio_dc_ac'), pourquoi=pourquoi_ratio, devis_recu=devis_recu,
                      verdict=next((v for v in verdicts if v.get('code') == 'ratio_dc_ac'), None))
         if getattr(calepinage, 'appel_offre_id', None) else
         _ratio_de_la_conception(_verdicts_de_la_conception(calepinage), devis_recu=devis_recu)),
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
#: ACAL1703 — l'écran Toit (onglet essentiel ``pente``) porte la liste « Objets du site ».
CIBLE_OBSTACLES = {'etape': 'toit', 'onglet': 'pente', 'champ': ''}


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
    # ACAL1971 — l'`id` STABLE du premier obstacle fautif (jamais son rang dans la liste).
    premier_id = ''
    # T4-B4-012 — « du pan A », mais « du pan Sud » pour un pan nommé « Pan Sud »
    # (jamais « du pan Pan Sud »).

    def _nom_du_pan(zone):
        nom = str(zone.get('label') or zone.get('id') or '—').strip()
        if nom[:4].lower() == 'pan ':
            return 'pan ' + nom[4:].strip()
        return 'pan ' + nom
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
                if not hors:
                    premier_id = str(obstacle.get('id') or '')
                hors.append('%s dépasse du %s' % (
                    _libelle_obstacle(obstacle.get('type')),
                    _nom_du_pan(zone)))
    if hors:
        return _controle('obstacle_hors_pan', libelle, 'a_regler',
                         hors[0], cause=' ; '.join(hors),
                         geste="Déplacer l'obstacle",
                         cible=dict(CIBLE_OBSTACLES, champ=premier_id))
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
    vides = [pan for pan in pans if pan['motif']]
    if not vides:
        return _controle('pans_vides', libelle, 'ok', 'Tous garnis',
                         cible=CIBLE_PANNEAUX)
    if len(vides) < len(pans):
        # T4-X5-006 — un pan laissé vide à côté d'un pan garni (le mode guidé
        # laisse le pan nord vide) est permis : une information, hors du
        # compte des points à régler.
        return _controle('pans_vides', libelle, 'info', ' ; '.join(
            'le pan %s est laissé sans panneau : il n’est ni chiffré ni '
            'simulé' % pan['pan'] for pan in vides), cible=CIBLE_PANNEAUX)
    vides = ['le pan %s n’a aucun panneau : %s' % (pan['pan'], pan['motif'])
             for pan in vides]
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

    libelle = 'Facture ou taille souhaitée renseignée'  # ACAL1332 (D-ACAL-77)
    # ACAL1342 — ni facture ni taille souhaitée : la réponse est connue, aucun balayage.
    if not lead_sans_facture_ni_taille(calepinage) \
            and taille_non_dimensionnee(calepinage) is None:
        return _controle('taille_sans_facture', libelle, 'ok', 'Renseignée',
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
#: ``reglages`` = la route ``/calepinage/reglages`` (``lienManque.js``, ``PretAEnvoyer.jsx``).
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

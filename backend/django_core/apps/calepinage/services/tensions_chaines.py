"""ACAL618 — les tensions de CHAQUE chaîne, servies par ``evaluer-electrique``.

Le noyau ne juge que la plus longue et la plus courte chaîne ; l'atelier veut
lire, chaîne par chaîne (automatique ou imposée à la main), N modules, la
tension à froid et sa limite, la tension à chaud et la tension de démarrage.

Aucune règle neuve : la tension d'une chaîne = la somme des tensions UN module
de chacun de ses modules, lues sur les chaînes conçues du MÊME pan ; les tests
de conformité REPRENNENT ceux de ``electrique.bloquants_nommes`` (Voc à froid
au-dessus de ``v_max_abs``) et de ``core/electrique/chaines.py::
_verdicts_tension`` (Vmp à chaud sous le bas de plage MPPT ou sous la tension
de démarrage). Une borne de fiche à 0 n'est pas une limite : elle est omise.
"""
from collections import OrderedDict

_ARRONDI_V = 1
_TOLERANCE = 1e-9


def _tensions_unitaires(conception):
    """``{libellé de pan: (voc froid, vmp chaud, isc)}`` d'UN module du pan."""
    unitaires = {}
    for chaine in conception.chaines:
        if chaine.pan in unitaires or not chaine.nb_modules:
            continue
        unitaires[chaine.pan] = (chaine.voc_froid_v / chaine.nb_modules,
                                 chaine.vmp_chaud_v / chaine.nb_modules,
                                 chaine.isc_a)
    return unitaires


def _ligne(numero, modules, unitaires, onduleur, temperatures):
    from .chaines import SOURCE_MANUELLE

    pans = list(OrderedDict.fromkeys(m['pan'] for m in modules))
    sans_chaine = [pan for pan in pans if pan not in unitaires]
    indetermine = [
        "pan « %s » : aucune chaîne conçue, tension d'un module inconnue"
        % pan for pan in sans_chaine]
    limite = float(onduleur.v_max_abs or 0) or None
    demarrage_source = ('fiche' if onduleur.v_demarrage_v is not None
                        else 'bas_de_plage_mppt')
    ligne = {
        'chaine': numero, 'pan': ', '.join(pans),
        'mppt': modules[0]['mppt'], 'nombre_modules': len(modules),
        'source': (SOURCE_MANUELLE if any(
            m['source'] == SOURCE_MANUELLE for m in modules)
            else modules[0]['source']),
        'voc_froid_v': None, 'voc_froid_limite_v': limite,
        'voc_froid_conforme': None,
        'temperature_froide_c': getattr(temperatures, 'froid_c', None),
        'vmp_chaud_v': None,
        'temperature_chaude_c': getattr(temperatures, 'chaud_c', None),
        'demarrage_v': float(onduleur.tension_demarrage_v),
        'demarrage_source': demarrage_source,
        'vmp_chaud_conforme': None, 'isc_a': None,
        'temperature_source': getattr(temperatures, 'source', None),
        'indetermine': indetermine,
    }
    if sans_chaine:
        return ligne
    voc = sum(unitaires[m['pan']][0] for m in modules)
    vmp = sum(unitaires[m['pan']][1] for m in modules)
    ligne['voc_froid_v'] = round(voc, _ARRONDI_V)
    ligne['vmp_chaud_v'] = round(vmp, _ARRONDI_V)
    ligne['isc_a'] = max(unitaires[m['pan']][2] for m in modules)
    if limite is not None:
        ligne['voc_froid_conforme'] = not voc > limite + _TOLERANCE
    ligne['vmp_chaud_conforme'] = not (
        vmp < float(onduleur.mppt_v_min) - _TOLERANCE
        or vmp < float(onduleur.tension_demarrage_v) - _TOLERANCE)
    return ligne


def tensions_par_chaine(conception, imposee=()):
    """Une ligne par numéro de chaîne de l'affectation, triée par chaîne.

    Fiche incomplète ou rien de chaîné ⇒ ``[]`` (le silence, jamais un faux
    vert). ``imposee`` est l'affectation manuelle déjà normalisée.
    """
    from .chaines import affectation

    if conception.fiche_incomplete or conception.resultat is None:
        return []
    onduleur = conception.entree.onduleur
    unitaires = _tensions_unitaires(conception)
    par_chaine = {}
    for ligne in affectation(conception, imposee=imposee):
        if ligne['chaine'] is not None:
            par_chaine.setdefault(ligne['chaine'], []).append(ligne)
    return [_ligne(numero, modules, unitaires, onduleur,
                   conception.temperatures)
            for numero, modules in sorted(par_chaine.items())]


#: Les codes des verdicts du noyau qui jugent un CÂBLAGE (tensions et courants
#: des chaînes posées) : ceux de ``core.electrique.chaines._verdicts_tension``
#: et ``_verdicts_courant`` — la garde de test relit leur source.
CODES_DU_CABLAGE = (
    'CH_VOC_FROID_AU_DESSUS_V_MAX', 'CH_VMP_FROID_AU_DESSUS_MPPT',
    'CH_VMP_CHAUD_SOUS_MPPT', 'CH_VMP_CHAUD_SOUS_DEMARRAGE',
    'CH_ISC_CUMULE_HORS_SPECIFICATION', 'CH_IMP_CUMULE_ECRETAGE',
    'CH_ISC_CUMULE_SUR_BORNE_DE_REPLI',
)


def imposee_et_refus(brut):
    """``(affectation imposée normalisée, [refus])`` — jamais une exception :
    une proposition MALFORMÉE est un refus NOMMÉ, et rien n'est imposé."""
    from .chaines import AffectationInvalide, normaliser_affectation_imposee

    try:
        return normaliser_affectation_imposee(brut), []
    except AffectationInvalide as refus:
        return (), [str(refus)]


def _chaines_du_cablage(conception, imposee):
    """Les ``Chaine`` du câblage EFFECTIF (automatique + manuel), ou ``None``."""
    from core.electrique.types import Chaine

    from .chaines import SOURCE_MANUELLE, affectation

    table = affectation(conception, imposee=imposee)
    if not any(ligne['source'] == SOURCE_MANUELLE for ligne in table):
        return None
    unitaires = {}
    for chaine in conception.chaines:
        if chaine.nb_modules and chaine.pan not in unitaires:
            n = float(chaine.nb_modules)
            unitaires[chaine.pan] = (
                chaine.voc_froid_v / n, chaine.vmp_froid_v / n,
                chaine.vmp_chaud_v / n, chaine.vmp_stc_v / n,
                chaine.puissance_kwc / n, chaine.isc_a, chaine.imp_a)
    accepte = getattr(conception, 'nombre_onduleurs', None)
    par_onduleur = (max(1, conception.entree.onduleur.n_mppt // accepte)
                    if accepte else None)
    par_chaine = {}
    for ligne in table:
        if ligne['chaine'] is not None:
            par_chaine.setdefault(ligne['chaine'], []).append(ligne)
    chaines = []
    for numero, modules in sorted(par_chaine.items()):
        pans = list(OrderedDict.fromkeys(m['pan'] for m in modules))
        if any(pan not in unitaires for pan in pans):
            continue  # tension d'un module inconnue : ``tensions_par_chaine`` le dit
        mppt, onduleur = modules[0]['mppt'], modules[0]['onduleur']
        if mppt is not None and par_onduleur and onduleur:
            mppt += (onduleur - 1) * par_onduleur
        somme = [sum(unitaires[m['pan']][i] for m in modules) for i in range(5)]
        chaines.append(Chaine(
            repere='CH%d' % numero, pan=', '.join(pans),
            nb_modules=len(modules), mppt=mppt, voc_froid_v=somme[0],
            vmp_froid_v=somme[1], vmp_chaud_v=somme[2], vmp_stc_v=somme[3],
            isc_a=max(unitaires[p][5] for p in pans),
            imp_a=max(unitaires[p][6] for p in pans), puissance_kwc=somme[4]))
    return tuple(chaines)


def conception_cablee(conception, imposee):
    """La ``Conception`` jugée sur le câblage EFFECTIF, pas sur l'automatique.

    Sans affectation manuelle en vigueur : ``conception`` elle-même. Sinon ses
    chaînes sont celles de la table (une chaîne saisie sur l'entrée MPPT 2 y
    est sur l'entrée 2), et les verdicts de câblage du noyau (``CODES_DU_
    CABLAGE``) sont RECALCULÉS par les mêmes fonctions du noyau sur ces
    chaînes — les autres (fenêtre vide, pans…) restent tels quels. Lecture :
    rien n'est écrit, rien n'est stocké.
    """
    from dataclasses import replace

    from core.electrique.chaines import _verdicts_courant, _verdicts_tension
    from core.electrique.types import STATUT_BLOQUANT, STATUTS_ALERTANTS, libelles

    resultat = getattr(conception, 'resultat', None)
    if (not imposee or resultat is None or conception.fiche_incomplete
            or getattr(conception, 'entree', None) is None):
        return conception
    chaines = _chaines_du_cablage(conception, imposee)
    if chaines is None:
        return conception
    onduleur = conception.entree.onduleur
    neufs = []
    _verdicts_tension(chaines, onduleur, resultat.fenetre, [], neufs)
    _verdicts_courant(tuple(c for c in chaines if c.mppt is not None),
                      onduleur, [], neufs)
    anciens = {v.libelle for v in resultat.verdicts
               if v.code in CODES_DU_CABLAGE}
    bloquants = libelles(neufs, (STATUT_BLOQUANT,))
    alertes = libelles(neufs, STATUTS_ALERTANTS)

    def garder(messages, ajout):
        return tuple(m for m in messages if m not in anciens) + tuple(ajout)

    cable = replace(
        resultat, chaines=chaines,
        bloquants=garder(resultat.bloquants, bloquants),
        alertes=garder(resultat.alertes, alertes),
        verdicts=tuple(v for v in resultat.verdicts
                       if v.code not in CODES_DU_CABLAGE) + tuple(neufs))
    return replace(conception, resultat=cable,
                   bloquants=garder(conception.bloquants, bloquants),
                   alertes=garder(conception.alertes, alertes))


def chaines_servies(calepinage):
    """ACAL672 — ``{n° de chaîne: ligne servie}`` du calepinage ENREGISTRÉ.

    Les lignes sont celles de ``evaluer-electrique`` (``chaines[]``) : un
    document les LIT, il ne recalcule aucune tension.
    """
    from .electrique import evaluation_electrique

    return {ligne['chaine']: ligne
            for ligne in evaluation_electrique(calepinage)['chaines']}

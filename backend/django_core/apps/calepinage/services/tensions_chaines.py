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


def chaines_servies(calepinage):
    """ACAL672 — ``{n° de chaîne: ligne servie}`` du calepinage ENREGISTRÉ.

    Les lignes sont celles de ``evaluer-electrique`` (``chaines[]``) : un
    document les LIT, il ne recalcule aucune tension.
    """
    from .electrique import evaluation_electrique

    return {ligne['chaine']: ligne
            for ligne in evaluation_electrique(calepinage)['chaines']}

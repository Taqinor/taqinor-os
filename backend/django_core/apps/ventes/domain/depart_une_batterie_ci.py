"""« Démarrer avec une seule batterie » — la phrase client d'un devis C&I
(fondateur, 19/11/2026).

« also add an option that when ticked the client get a sentence showing the
price if he wants to start only with one battery and dont forget that the
number of pannels should be the number of just those pannels »

La case de l'écran (``etude_params.options.phrase_une_batterie``, entrée
ÉCRAN, brouillon seulement) demande au rafraîchisseur C&I
(``etude_ci.rafraichir_etude_ci_devis``) de poser dans ``etude_ci`` le bloc
``depart_une_batterie`` CALCULÉ ICI, côté serveur : le système que le
calculateur compose pour UNE batterie (D-HYB-4 : panneaux pour 1, onduleur
hybride gardé pour la banque calculée) et le prix exact que l'option « avec »
afficherait si le vendeur posait « Batteries au départ » = 1. Le calcul REJOUE
``recomposition_batteries_ci`` (``_etude`` puis ``_ecrire`` : mêmes lignes, même
écrivain, même échéancier) dans un point de sauvegarde ANNULÉ, puis lit les
totaux de l'option par ``utils.options.option_totaux`` (remise globale et
arrondi commercial compris) et les panneaux sur les lignes écrites. Le moteur
PDF ne fait que LIRE le bloc (règle #4) ; aucun statut, aucune ligne réelle
n'est touché.

Jamais périmé, jamais inventé — sinon le bloc est ABSENT et
``depart_une_batterie_refus`` (interne, écran du vendeur ; jamais au client)
dit pourquoi :

* option « avec » absente, ou une seule batterie au devis ;
* l'option « avec » des LIGNES n'est plus celle du calculateur : la même
  recomposition au nombre de batteries COURANT ne reproduit pas, au centime,
  le Total HT et le Total TTC de l'option (prix, quantité ou article retouché
  à la main, catalogue changé depuis) ;
* le calculateur refuse la composition à une batterie (prix manquant,
  étude refusée, échéancier incompatible…) ;
* devis non brouillon : le bloc calculé au brouillon est REPRIS tel quel
  (le client garde ce qu'il a reçu) tant que les totaux de l'option « avec »
  n'ont pas bougé, sinon retiré.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar

logger = logging.getLogger(__name__)

#: La case de l'écran (``etude_params.options``).
OPTION = 'phrase_une_batterie'
#: Le bloc servi dans ``etude_params.etude_ci`` et son refus nommé (interne).
CLE = 'depart_une_batterie'
CLE_REFUS = 'depart_une_batterie_refus'

_PREFIXE = 'Phrase « démarrer avec une seule batterie » non imprimée : '
MESSAGES = {
    'sans_option': _PREFIXE + "ce devis n'a pas d'option « avec batterie ».",
    'une_batterie': _PREFIXE + "l'option « avec batterie » ne compte qu'une batterie.",
    'sans_lead': _PREFIXE + "le devis n'est rattaché à aucun lead (le calculateur lit sa fiche).",
    'lignes_modifiees': _PREFIXE + (
        "les lignes de l'option « avec batterie » ne sont plus celles du calculateur "
        '(prix, quantité ou article retouché, ou catalogue changé depuis). Choisissez à '
        'nouveau le nombre de « Batteries au départ » pour recomposer l’option, ou '
        'décochez la case.'),
    'recomposition': _PREFIXE + 'le calculateur ne compose pas le système à une batterie — %s',
    'incomplet': _PREFIXE + 'le système à une batterie ne se lit pas entièrement (%s).',
    'non_brouillon': _PREFIXE + 'elle se calcule sur un brouillon ; utilisez « Réviser ».',
    'corrige_apres_envoi': _PREFIXE + (
        "les totaux de l'option « avec batterie » ont changé depuis son calcul ; "
        'utilisez « Réviser » pour la recalculer.'),
    'erreur': _PREFIXE + 'calcul impossible (erreur journalisée côté serveur).',
}
#: Changement de la case refusé hors brouillon (PATCH ``etude-params``).
MESSAGE_BASCULE_NON_BROUILLON = (
    'Devis « %s » : la phrase « démarrer avec une seule batterie » ne se coche ou '
    'ne se décoche que sur un brouillon. Utilisez « Réviser ».')

#: Garde de ré-entrée : une simulation n'appelle jamais ce calcul.
_EN_SIMULATION = ContextVar('depart_une_batterie_simulation', default=False)


class RefusDepart(Exception):
    """Refus nommé : ``code`` (clé de :data:`MESSAGES`) et ``message``."""

    def __init__(self, code, detail=None):
        message = MESSAGES[code] % detail if detail is not None else MESSAGES[code]
        super().__init__(message)
        self.code = code
        self.message = message


class _Annuler(Exception):
    """Porte la lecture hors du point de sauvegarde, qui est annulé."""

    def __init__(self, lecture):
        super().__init__('simulation annulée')
        self.lecture = lecture


def phrase_demandee(etude_params):
    """La case est-elle cochée (``options.phrase_une_batterie is True``) ?"""
    options = (etude_params or {}).get('options') if isinstance(etude_params, dict) else None
    return isinstance(options, dict) and options.get(OPTION) is True


def refus_bascule(devis, corps):
    """Message (409) quand ``corps`` (PATCH ``etude-params``) change la case
    d'un devis non brouillon, sinon ``None``."""
    if not isinstance(corps, dict) or 'options' not in corps:
        return None
    if phrase_demandee({'options': corps.get('options')}) == phrase_demandee(devis.etude_params):
        return None
    if devis.statut == 'brouillon':
        return None
    return MESSAGE_BASCULE_NON_BROUILLON % devis.get_statut_display()


def _totaux_avec(devis):
    """``(HT, TTC)`` nets (Decimal, centime) de l'option « avec » du devis."""
    from apps.ventes.utils.options import AVEC_BATTERIE, option_totaux
    totaux = option_totaux(devis, AVEC_BATTERIE)
    return totaux['ht'], totaux['ttc']


def empreinte_depart(devis, empreinte):
    """Case cochée : l'empreinte du rafraîchisseur porte aussi les totaux de
    l'option « avec » des LIGNES — une retouche de prix relance le calcul et
    sa vérification. Case décochée : l'empreinte d'hier, inchangée."""
    if not phrase_demandee(getattr(devis, 'etude_params', None)):
        return empreinte
    import hashlib
    ht, ttc = _totaux_avec(devis)
    charge = '%s|%s|%s|%s' % (empreinte, OPTION, ht, ttc)
    return hashlib.sha256(charge.encode('utf-8')).hexdigest()[:16]


def _entier(valeur):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _lecture_simulee(devis, avec):
    """Ce que l'option « avec » du devis RECOMPOSÉ montre : totaux, panneaux
    (articles ``panneau`` de la composition, quantités des LIGNES écrites),
    batteries, kWc des lignes (``etudes.puissances_etude_horaire``)."""
    from apps.ventes.models import Devis
    from apps.ventes.utils.options import AVEC_BATTERIE, option_lines

    from .etudes import puissances_etude_horaire
    relu = Devis.objects.get(pk=devis.pk)
    ht, ttc = _totaux_avec(relu)
    panneaux = {ligne.get('produit') for ligne in (avec.get('composition') or {}).get('lignes') or []
                if ligne.get('role') == 'panneau' and ligne.get('produit')}
    batterie = (avec.get('batterie') or {}).get('produit')
    lignes = option_lines(relu, AVEC_BATTERIE)
    return {'ht': ht, 'ttc': ttc,
            'nb_panneaux': sum(int(li.quantite or 0) for li in lignes if li.produit_id in panneaux),
            'nb_batteries': sum(int(li.quantite or 0) for li in lignes if li.produit_id == batterie),
            'kwc': puissances_etude_horaire(relu)[0],
            'capacite_utile_kwh': (avec.get('batterie') or {}).get('capacite_utile_kwh')}


def _simuler(devis, scenario, nombre):
    """La recomposition D-HYB-4 à ``nombre`` batteries, JOUÉE puis ANNULÉE :
    ``recomposition_batteries_ci._etude`` + ``_ecrire`` sur une copie fraîche
    du devis, dans un point de sauvegarde toujours défait. Rend
    :func:`_lecture_simulee` ; lève :class:`RefusDepart` (rien d'écrit)."""
    from django.db import transaction

    from apps.ventes.models import Devis

    from .recomposition_batteries_ci import RecompositionBatteriesError, _ecrire, _etude
    jeton = _EN_SIMULATION.set(True)
    try:
        with transaction.atomic():
            copie = Devis.objects.select_related('lead', 'company').get(pk=devis.pk)
            _etude_n, avec, maxi, lignes = _etude(copie, scenario, nombre)
            if not any(ligne['produit_id'] for ligne in lignes):
                raise RefusDepart('recomposition', 'aucun article chiffré.')
            _ecrire(copie, avec, nombre, maxi, lignes, None)
            raise _Annuler(_lecture_simulee(copie, avec))
    except _Annuler as fin:
        return fin.lecture
    except RecompositionBatteriesError as exc:
        raise RefusDepart('recomposition', exc.message)
    finally:
        _EN_SIMULATION.reset(jeton)


def _arrondi(valeur, chiffres=2):
    return None if valeur is None else round(float(valeur), chiffres)


def _calculer(devis, nombre, scenario):
    """Le bloc ``depart_une_batterie`` d'un brouillon dont l'option « avec »
    compte ``nombre`` (≥ 2) batteries."""
    reference = _totaux_avec(devis)
    courant = _simuler(devis, scenario, nombre)
    if (courant['ht'], courant['ttc']) != reference:
        raise RefusDepart('lignes_modifiees')
    une = _simuler(devis, scenario, 1)
    manque = [nom for nom, valeur in (('panneaux', une['nb_panneaux']), ('kWc', une['kwc']),
                                      ('capacité utile', une['capacite_utile_kwh']))
              if not valeur]
    if une['nb_batteries'] != 1:
        manque.append('%s batterie(s) écrite(s)' % une['nb_batteries'])
    if manque:
        raise RefusDepart('incomplet', ', '.join(manque))
    return {'nb_batteries': 1, 'batteries_ensuite': nombre - 1,
            'nb_panneaux': une['nb_panneaux'], 'kwc': _arrondi(une['kwc']),
            'capacite_utile_kwh': _arrondi(une['capacite_utile_kwh']),
            'total_ht': _arrondi(une['ht']), 'total_ttc': _arrondi(une['ttc']),
            'reference_option_avec': {'nb_batteries': nombre, 'total_ht': _arrondi(reference[0]),
                                      'total_ttc': _arrondi(reference[1])}}


def _repris(devis, existant):
    """Devis non brouillon : le bloc calculé au brouillon, repris tel quel
    tant que les totaux de l'option « avec » sont ceux de son calcul."""
    precedent = (existant or {}).get(CLE)
    if not isinstance(precedent, dict):
        raise RefusDepart('non_brouillon')
    ref = precedent.get('reference_option_avec') or {}
    ht, ttc = _totaux_avec(devis)
    if _arrondi(ht) != ref.get('total_ht') or _arrondi(ttc) != ref.get('total_ttc'):
        raise RefusDepart('corrige_apres_envoi')
    return precedent


def calculer_depart(devis, bloc, existant=None):
    """Le bloc ``depart_une_batterie`` (voir le module) ou :class:`RefusDepart`.
    ``bloc`` : l'``etude_ci`` que le rafraîchisseur va écrire (son
    ``option_avec`` = l'option des LIGNES) ; ``existant`` : l'``etude_ci``
    stocké avant ce calcul."""
    from .scenario import SCENARIO_AVEC_BATTERIE, SCENARIO_LES_DEUX
    from .etude_ci_batterie import CLE as CLE_OPTION_AVEC
    scenario = (devis.etude_params or {}).get('scenario')
    avec = (bloc or {}).get(CLE_OPTION_AVEC) or {}
    if scenario not in (SCENARIO_LES_DEUX, SCENARIO_AVEC_BATTERIE) or not avec:
        raise RefusDepart('sans_option')
    nombre = _entier((avec.get('batterie') or {}).get('quantite'))
    if not nombre or nombre < 2:
        raise RefusDepart('une_batterie')
    if devis.statut != 'brouillon':
        return _repris(devis, existant)
    if getattr(devis, 'lead', None) is None:
        raise RefusDepart('sans_lead')
    return _calculer(devis, nombre, scenario)


def poser_depart(devis, bloc, existant=None):
    """L'``etude_ci`` ``bloc`` complété : case décochée ⇒ ``bloc`` tel quel
    (aucune clé ajoutée : rendu d'hier) ; cochée ⇒ ``depart_une_batterie``
    OU ``depart_une_batterie_refus`` ``{code, message}``. Ne lève jamais (le
    rafraîchisseur n'écrirait plus l'étude)."""
    if _EN_SIMULATION.get() or not phrase_demandee(getattr(devis, 'etude_params', None)):
        return bloc
    try:
        return dict(bloc, **{CLE: calculer_depart(devis, bloc, existant)})
    except RefusDepart as refus:
        return dict(bloc, **{CLE_REFUS: {'code': refus.code, 'message': refus.message}})
    except Exception:  # noqa: BLE001 — jamais bloquant pour l'étude (D-ENF22-BLE001)
        logger.warning('Devis %s : prix « une seule batterie » non calculé',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return dict(bloc, **{CLE_REFUS: {'code': 'erreur', 'message': MESSAGES['erreur']}})

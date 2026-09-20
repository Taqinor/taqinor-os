"""NTAI27 (moitié ``core``) — seuils de scorer résolus PAR SOCIÉTÉ.

Les scorers de ``core`` (churn, probabilité de gain, retard de paiement,
réappro, anomalie) portent aujourd'hui leurs hyperparamètres en CONSTANTES de
module : les mêmes poids et les mêmes seuils pour toutes les sociétés. Ce
module ouvre le seul point d'entrée par lequel une société peut en activer une
version propre, SANS que ``core`` importe l'app qui les stocke.

Le mécanisme est le RÉSOLVEUR ENREGISTRÉ, exactement comme
``core.workflow.register_business_day_advance`` ou
``core.feature_flags.register_module_access_check`` : l'app registre appelle
``register_params_resolver(fn)`` depuis son ``AppConfig.ready()``, et ``core``
ne connaît qu'un callable opaque (contrat import-linter
``core-foundation-is-a-base-layer``).

Contrat du résolveur — ``fn(company, nom) -> mapping`` :
  * ``nom``  est l'un des noms de scorer de :data:`NOMS_SCORERS` ;
  * il rend les hyperparamètres ACTIFS de cette société pour ce scorer, ou un
    mapping vide s'il n'y en a pas.

Politique, strictement non régressive :
  * aucun résolveur enregistré, ``company`` absente, résolveur qui lève, ou
    société sans version active  → les DÉFAUTS DU CODE s'appliquent, à
    l'identique du comportement d'avant NTAI27 ;
  * seules les clés DÉJÀ présentes dans les défauts sont acceptées (liste
    blanche : un ``params_json`` mal rempli ne peut pas injecter un paramètre
    inconnu) et chaque valeur est convertie au TYPE du défaut — sinon elle est
    ignorée, jamais propagée en l'état.

Cette moitié ne crée AUCUN modèle : le registre ``ModeleML`` et son
``selectors.params_actifs`` appartiennent à ``apps/mlops``, construit hors de
``core``. Ici on livre la couture et la lecture.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Noms de scorer (vocabulaire PARTAGÉ avec le registre de modèles) ─────────
NOM_CHURN = 'churn'
NOM_WIN_PROBA = 'win_proba'
NOM_RETARD_PAIEMENT = 'retard_paiement'
NOM_REAPPRO = 'reappro'
NOM_ANOMALIE = 'anomalie'

#: Les cinq scorers versionnables. Un ``nom`` hors de cette liste n'est pas
#: refusé (``core`` ne juge pas le catalogue de l'app registre) mais il ne
#: correspond à aucun scorer de cette couche.
NOMS_SCORERS = (
    NOM_CHURN,
    NOM_WIN_PROBA,
    NOM_RETARD_PAIEMENT,
    NOM_REAPPRO,
    NOM_ANOMALIE,
)

_resolveur_params = None

__all__ = [
    'NOM_CHURN',
    'NOM_WIN_PROBA',
    'NOM_RETARD_PAIEMENT',
    'NOM_REAPPRO',
    'NOM_ANOMALIE',
    'NOMS_SCORERS',
    'register_params_resolver',
    'registered_params_resolver',
    'clear_params_resolver',
    'params_actifs',
    'resoudre',
    'valeur',
]


def register_params_resolver(fn):
    """Enregistre le résolveur d'hyperparamètres par société (NTAI27).

    Appelé une fois, depuis le ``ready()`` de l'app qui tient le registre de
    modèles, avec son ``selectors.params_actifs``. Un second appel REMPLACE le
    résolveur (les tests s'en servent pour isoler leur cas)."""
    if not callable(fn):
        raise ValueError('register_params_resolver : callable requis.')
    global _resolveur_params
    _resolveur_params = fn


def registered_params_resolver():
    """Le résolveur enregistré, ou ``None`` (introspection / tests)."""
    return _resolveur_params


def clear_params_resolver():
    """Retire le résolveur — remet la couche sur les défauts du code."""
    global _resolveur_params
    _resolveur_params = None


def params_actifs(company, nom):
    """Hyperparamètres actifs de ``company`` pour le scorer ``nom``.

    Toujours un ``dict`` : vide si aucun résolveur n'est enregistré, si
    ``company`` est absente, ou si le résolveur échoue (best-effort — un
    registre en panne ne doit JAMAIS empêcher un score de sortir).
    """
    if company is None or not nom or _resolveur_params is None:
        return {}
    try:
        brut = _resolveur_params(company, nom)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception(
            'params_actifs : résolveur en échec pour le scorer %s', nom)
        return {}
    if not brut:
        return {}
    try:
        return dict(brut)
    except (TypeError, ValueError):
        logger.warning(
            'params_actifs : le résolveur a rendu une valeur non mappable '
            'pour le scorer %s', nom)
        return {}


def _convertir(defaut, brut):
    """Convertit ``brut`` au type de ``defaut``, ou ``None`` si impossible.

    ``None`` signifie « valeur inutilisable, garder le défaut » — on ne
    propage jamais une valeur de configuration qu'on n'a pas su typer."""
    if isinstance(defaut, bool):
        if isinstance(brut, bool):
            return brut
        if isinstance(brut, (int, float)):
            return bool(brut)
        if isinstance(brut, str):
            bas = brut.strip().lower()
            if bas in ('true', '1', 'oui'):
                return True
            if bas in ('false', '0', 'non'):
                return False
        return None
    if isinstance(defaut, int):
        try:
            return int(brut)
        except (TypeError, ValueError):
            return None
    if isinstance(defaut, float):
        try:
            return float(brut)
        except (TypeError, ValueError):
            return None
    if isinstance(defaut, dict):
        # Table de paramètres (ex. la base par étape) : on n'accepte que les
        # clés DÉJÀ connues, chacune convertie comme sa propre valeur défaut.
        if not isinstance(brut, dict):
            return None
        fusion = dict(defaut)
        for cle, val in brut.items():
            if cle not in fusion:
                continue
            converti = _convertir(fusion[cle], val)
            if converti is not None:
                fusion[cle] = converti
        return fusion
    if isinstance(defaut, str):
        return str(brut)
    return None


def resoudre(company, nom, defauts):
    """Les hyperparamètres effectifs du scorer ``nom`` pour ``company``.

    Part des ``defauts`` du CODE et n'écrase que les clés que la société a
    réellement versionnées (liste blanche + conversion de type). Rendre un
    ``dict`` neuf à chaque appel est voulu : un scorer ne doit jamais pouvoir
    muter la table de défauts partagée.
    """
    effectifs = dict(defauts or {})
    for cle, brut in params_actifs(company, nom).items():
        if cle not in effectifs:
            continue
        converti = _convertir(effectifs[cle], brut)
        if converti is not None:
            effectifs[cle] = converti
    return effectifs


def valeur(company, nom, cle, defaut):
    """Un seul hyperparamètre — raccourci pour les scorers qui n'en lisent qu'un."""
    return resoudre(company, nom, {cle: defaut})[cle]

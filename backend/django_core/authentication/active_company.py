"""XPLT19 — Société ACTIVE d'un utilisateur multi-sociétés.

Un utilisateur peut être membre de PLUSIEURS sociétés (``societes_autorisees``,
M2M additive). À un instant donné, une SEULE société est « active » : c'est
elle qui borne TOUT le scoping (``request.user.company``, ``core.scoping``,
``perform_create``…). La société active est portée par un claim JWT
(``active_company_id``) et changée via ``POST /auth/switch-company/`` (autorisé
uniquement si l'utilisateur en est membre).

Principe de conception (aucune réécriture des 1200+ lectures ``user.company``)
----------------------------------------------------------------------------
Le champ FK ``CustomUser.company`` reste la société « d'attache » (home) et
n'est JAMAIS modifié en base. Un middleware léger
(``ActiveCompanyMiddleware``) résout la société active de la REQUÊTE depuis le
claim JWT, vérifie l'appartenance, puis pose ``request.user.company`` sur
l'INSTANCE utilisateur de cette requête (jamais un ``save()``). Comme
``request.user`` est une instance fraîche par requête (voir
``CookieJWTAuthentication`` / DRF), muter ``.company`` n'affecte QUE cette
requête : toutes les lectures existantes voient donc transparentement la
société active, et aucune requête ne mélange jamais deux sociétés.

Byte-identique pour l'existant : un utilisateur mono-société (backfill =
``societes_autorisees`` = {sa société}) sans claim actif garde exactement sa
``company`` d'attache — comportement inchangé.

Couche de FONDATION : ce module ne dépend d'AUCUNE app métier (uniquement les
modèles ``authentication``, résolus paresseusement).
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_state = threading.local()

# Claim JWT portant l'id de la société active choisie par l'utilisateur.
ACTIVE_COMPANY_CLAIM = 'active_company_id'


def set_active_company_id(company_id):
    """Pose l'id de société active pour le thread/requête courant (ou None)."""
    _state.active_company_id = company_id


def get_active_company_id():
    """Id de société active du thread courant, ou None si aucun switch actif."""
    return getattr(_state, 'active_company_id', None)


def clear_active_company():
    """Efface l'état de société active (fin de requête)."""
    _state.active_company_id = None


def companies_for_user(user):
    """Sociétés que ``user`` peut opérer : union de sa société d'attache
    (``company``) et de ``societes_autorisees``. Rendu dédupliqué, jamais None.

    Un utilisateur mono-société (backfill) renvoie exactement {sa société}."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return []
    ids = {}
    home = getattr(user, 'company', None)
    if home is not None:
        ids[home.id] = home
    try:
        for c in user.societes_autorisees.all():
            ids[c.id] = c
    except Exception:  # noqa: BLE001 — relation absente (instance non sauvée) (D-ENF22-BLE001)
        logger.debug("active_company : sociétés autorisées illisibles (instance non sauvée)", exc_info=True)
    return list(ids.values())


def user_can_operate(user, company_id):
    """True si ``user`` est membre de la société ``company_id`` (home OU M2M).

    Le superuser peut opérer n'importe quelle société (accès console/support)."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if company_id is None:
        return False
    try:
        company_id = int(company_id)
    except (TypeError, ValueError):
        return False
    from authentication.permissions import est_operateur_plateforme

    if est_operateur_plateforme(user):  # APFS61 — superuser SANS société
        from authentication.models import Company
        return Company.objects.filter(pk=company_id).exists()
    return any(c.id == company_id for c in companies_for_user(user))


def role_dans_societe(user, company_id):
    """APFS66 (D-APFS-3) — ``(autorisé, rôle)`` dans ``company_id`` : rôle d'attache chez soi (ou
    opérateur plateforme), sinon celui de l'appartenance s'il est de cette société ; sinon refus."""
    from authentication.permissions import est_operateur_plateforme
    attache = getattr(user, '_company_id_attache', getattr(user, 'company_id', None))
    if est_operateur_plateforme(user) or (attache is not None and int(company_id) == attache):
        return True, getattr(user, 'role', None)
    from authentication.models import AppartenanceSociete
    lien = (AppartenanceSociete.objects.select_related('role')
            .filter(user_id=user.pk, company_id=int(company_id), role__company_id=int(company_id)).first())
    return (True, lien.role) if lien is not None else (False, None)


def resolve_active_company(user, claimed_id):
    """Résout la société active à appliquer à la requête.

    Renvoie l'objet ``Company`` à poser sur ``request.user.company`` :

    * la société revendiquée (``claimed_id``) SI l'utilisateur en est membre ;
    * sinon la société d'attache (``user.company``) — jamais une fuite vers une
      société non autorisée (défaut sûr).
    """
    home = getattr(user, 'company', None)
    if claimed_id is None:
        return home
    if not user_can_operate(user, claimed_id):
        return home
    if home is not None and home.id == int(claimed_id):
        return home
    autorise, role = role_dans_societe(user, claimed_id)
    if not autorise:  # APFS66 — membre sans rôle dans cette société : repli
        return home
    from authentication.models import Company
    active = Company.objects.filter(pk=int(claimed_id)).first()
    if active is not None:
        user.role = role  # APFS66 — rôle de la société ACTIVE, sur l'instance (jamais save())
    return active or home

"""Services (écriture/orchestration) du module Immobilier.

Toute lecture/écriture vers un autre domaine (``crm``/``ventes``) passe
exclusivement par ses ``selectors.py``/``services.py`` (imports FONCTION-LOCAL,
jamais ``apps.crm.models``/``apps.ventes.models`` importés en tête de module) —
frontière cross-app de CLAUDE.md.
"""


def resolve_client_ventes_for_locataire(locataire):
    """NTPRO2 — Relie ``locataire`` à un ``crm.Client`` EXISTANT sans jamais en
    créer un nouveau (pas de point d'entrée d'écriture sanctionné pour créer un
    client hors lead dans ce périmètre) : même esprit que
    ``crm.services.resolve_client_for_lead``, mais strictement LECTURE — un
    locataire sans client ventes correspondant reste simplement délié
    (``client_ventes_id`` = None), jamais de doublon créé.

    Recherche par email d'abord, puis par téléphone (repli), via
    ``apps.crm.selectors`` (jamais un import de ``apps.crm.models``). Idempotent
    : si ``locataire.client_ventes_id`` est déjà posé, ne fait rien et renvoie
    l'id existant.
    """
    if locataire.client_ventes_id:
        return locataire.client_ventes_id

    from apps.crm.selectors import find_client_by_email, find_client_by_phone

    client = None
    if locataire.email:
        client = find_client_by_email(locataire.email, company=locataire.company)
    if client is None and locataire.telephone:
        client = find_client_by_phone(locataire.company, locataire.telephone)

    if client is None:
        return None

    locataire.client_ventes_id = client.id
    locataire.save(update_fields=['client_ventes_id'])
    return client.id

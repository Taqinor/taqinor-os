"""NTPLT1 — Contexte tenant PAR REQUÊTE (fondation RLS Postgres).

Défense en profondeur multi-tenant : en plus du scoping applicatif
(``request.user.company`` filtre chaque queryset — CLAUDE.md), on pose au niveau
de la BASE un « paramètre de configuration » Postgres (GUC)
``app.current_company`` égal à l'id de la société de l'appelant. Les politiques
RLS (NTPLT2, générées par introspection) s'y appuieront
(``current_setting('app.current_company', true)``) pour que même une requête SQL
brute ne puisse PHYSIQUEMENT pas lire les lignes d'un autre tenant.

Ce module ne fait qu'UNE chose ici (NTPLT1) : offrir un helper réutilisable
``set_current_company(company_id)`` et un middleware ``TenantContextMiddleware``
qui pose le GUC en début de chaque requête authentifiée.

État par défaut : **OFF**. Tant que le flag d'environnement
``POSTGRES_RLS_ENABLED`` est absent (ou ≠ ``1``), le helper ET le middleware sont
un NO-OP TOTAL — aucune requête SQL supplémentaire n'est émise (prouvé par un
test au budget de requêtes). Activer RLS est une bascule d'infrastructure
délibérée (rôle non-BYPASSRLS, policies posées) : NTPLT1 ne l'active jamais tout
seul.

Contrainte de conception RLS × pooling (docs/scale-runway.md § SCA14 — Étape 1,
OBLIGATOIRE) : le GUC est posé via ``SET LOCAL`` **scopé à la transaction**,
JAMAIS via un ``SET`` de session. En mode pooling transaction (pgbouncer), une
connexion physique est partagée entre plusieurs transactions logiques
successives ; un ``SET`` de session ferait FUITER le ``company_id`` d'un tenant
vers la transaction du tenant suivant sur la même connexion — une fuite
multi-tenant critique. ``SET LOCAL`` s'efface à la fin de la transaction, ce qui
est exactement le comportement voulu.

Ce module NE DÉPEND DE RIEN d'une app domaine (couche fondation ``core`` —
contrat import-linter) : il lit seulement ``request.user.company`` et parle à la
connexion Django.
"""
from __future__ import annotations

import os
from typing import Optional

from django.db import connection


def rls_enabled() -> bool:
    """Vrai si la défense RLS est activée par l'environnement.

    Défaut OFF : sans ``POSTGRES_RLS_ENABLED=1`` dans l'environnement, tout le
    module est un no-op (aucun SQL supplémentaire).
    """
    return os.environ.get('POSTGRES_RLS_ENABLED', '0') == '1'


def set_current_company(company_id: Optional[int]) -> bool:
    """Pose le GUC Postgres ``app.current_company`` pour la transaction courante.

    Helper réutilisable (middleware HTTP NTPLT1, décorateur de tâche Celery
    NTPLT4, SQL-agent FastAPI NTPLT4). Retourne ``True`` si le GUC a été posé,
    ``False`` si l'appel a été un no-op.

    No-op (retourne ``False``, ZÉRO requête SQL) quand :
      * ``POSTGRES_RLS_ENABLED`` est absent/≠1 (défaut) ; OU
      * ``company_id`` est ``None`` (appelant système/superuser sans société —
        les surfaces cross-company légitimes sont couvertes par une policy
        dédiée en NTPLT3, jamais par un GUC vide ici) ; OU
      * le backend de base n'est pas PostgreSQL (SQLite de test → no-op propre).

    Utilise ``SET LOCAL`` (transaction-scopé) impérativement — voir le docstring
    du module (contrainte SCA14 × pooling). ``set_config(..., true)`` est
    l'équivalent SQL fonctionnel de ``SET LOCAL`` (3ᵉ argument ``is_local=true``)
    et se paramètre proprement.
    """
    if not rls_enabled():
        return False
    if company_id is None:
        return False
    # NTPLT46 — le contexte tenant est résolu ici : en profiter pour tagger la
    # société sur les futurs événements Sentry (no-op si Sentry non initialisé).
    try:
        from . import monitoring
        monitoring.bind_company(company_id)
    except Exception:  # noqa: BLE001 — un tag ne doit jamais casser une requête
        pass
    if connection.vendor != 'postgresql':
        return False
    with connection.cursor() as cursor:
        # set_config('app.current_company', <val>, true) == SET LOCAL :
        # is_local=true ⇒ effacé à la fin de la transaction (jamais de fuite
        # inter-transactions sur une connexion poolée).
        cursor.execute(
            "SELECT set_config('app.current_company', %s, true)",
            [str(int(company_id))],
        )
    return True


def clear_current_company() -> None:
    """Efface le GUC ``app.current_company`` pour la transaction courante.

    Rarement nécessaire (``SET LOCAL`` s'efface seul à la fin de la
    transaction), mais utile pour un reset explicite dans un même bloc
    transactionnel long. No-op si RLS est désactivé ou hors PostgreSQL.
    """
    if not rls_enabled() or connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_company', '', true)")


def _company_id_from_request(request) -> Optional[int]:
    """Résout l'id de société de l'appelant, best-effort (jamais d'exception).

    L'auth API est portée par DRF (JWT via cookie/Bearer) et n'est pas encore
    résolue au niveau middleware pour les requêtes API — on réutilise donc
    ``CookieJWTAuthentication`` silencieusement (même pattern que
    ``DisabledModuleMiddleware``). Jeton absent/invalide ⇒ aucune société ⇒
    no-op (défaut sûr).
    """
    user = getattr(request, 'user', None)
    company = getattr(user, 'company', None)
    if company is not None:
        return getattr(company, 'pk', None)
    try:
        from authentication.cookie_auth import CookieJWTAuthentication
        result = CookieJWTAuthentication().authenticate(request)
    except Exception:  # noqa: BLE001 - jeton invalide ⇒ pas de blocage
        return None
    if result is None:
        return None
    return getattr(getattr(result[0], 'company', None), 'pk', None)


class TenantContextMiddleware:
    """Pose ``app.current_company`` au début de chaque requête authentifiée.

    Se place APRÈS l'authentification Django. No-op total quand RLS est
    désactivé (défaut) : le flag est vérifié EN PREMIER, donc aucune résolution
    de société ni requête SQL n'a lieu — le chemin par défaut est byte-identique
    à l'absence de ce middleware (prouvé par un test au budget de requêtes).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if rls_enabled():
            company_id = _company_id_from_request(request)
            if company_id is not None:
                # Pose le GUC ; le SET LOCAL sera visible pour toute la
                # transaction ouverte par ATOMIC_REQUESTS/les vues.
                set_current_company(company_id)
        return self.get_response(request)


# ── NTPLT4 — GUC tenant dans les tâches Celery ───────────────────────────────
def tenant_task(func):
    """Décorateur : pose ``app.current_company`` au début d'une tâche à effet.

    Convention (NTPLT4) : les tâches Celery à effets tenant reçoivent un kwarg
    ``company_id``. Ce décorateur, appliqué SOUS ``@shared_task`` (donc au plus
    près de la fonction), ouvre une transaction et y pose le GUC via
    ``set_current_company`` AVANT d'exécuter le corps — de sorte que, RLS actif,
    la tâche ne voit/écrit que les lignes de CE tenant, même via SQL brut.

        @shared_task(name=...)   # ex. nom explicite « crm.relancer »
        @tenant_task
        def relancer(*, company_id, lead_id):
            ...

    Sûreté et rétro-compatibilité :
      * No-op total quand RLS est désactivé (défaut) : ``set_current_company``
        court-circuite, et on n'ouvre PAS de transaction supplémentaire — le
        corps s'exécute exactement comme avant (comportement historique).
      * ``company_id`` absent/None : aucune erreur, aucun GUC — utile pour les
        tâches VOLONTAIREMENT cross-company (beat système) qui tournent sous le
        rôle owner/BYPASSRLS (NTPLT3) et ne doivent JAMAIS poser de GUC.
      * ``SET LOCAL`` est transaction-scopé : il s'efface à la fin de la
        transaction ouverte ici (jamais de fuite vers la tâche suivante sur le
        même worker/connexion — contrainte SCA14 × pooling).
    """
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        company_id = kwargs.get('company_id')
        if not rls_enabled() or company_id is None:
            # Chemin par défaut (RLS off) OU tâche cross-company : aucun GUC,
            # aucune transaction ajoutée — comportement inchangé.
            return func(*args, **kwargs)
        from django.db import transaction
        with transaction.atomic():
            set_current_company(company_id)
            return func(*args, **kwargs)

    return wrapper

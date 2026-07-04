"""Mixins de sérialiseur réutilisables (fondation ``core``).

YRBAC7 — ``SensitiveFieldMaskMixin``
------------------------------------

Généralise le masquage champ-sensible aujourd'hui codé cas par cas (stock/crm/
rh). Un sérialiseur déclare ``sensitive_fields = {'prix_achat': 'prix_achat_voir',
'marge_pct': 'marge_voir'}`` et le mixin RETIRE (pas met à ``null``) chaque champ
quand l'utilisateur de la requête n'a pas la permission associée. L'utilisateur
est lu depuis le ``context['request']`` — JAMAIS depuis le body.

Comportement de repli conservé (comme ``HasPermissionOrLegacy`` /
``can_view_buy_prices``) : un compte SANS rôle fin (légacy) garde l'accès
historique et n'est donc PAS masqué. Le superuser voit tout.

YRBAC8 — ``ServerControlledFieldsMixin``
----------------------------------------

Garde anti-mass-assignment : retire du body entrant les champs de gouvernance
(``company``, ``created_by``, ``is_*``, ``role``…) avant validation, pour qu'un
client ne puisse jamais forcer la société, le propriétaire ou un flag privilège.

``core`` reste FONDATION : ces mixins ne dépendent d'aucune app métier.
"""
from __future__ import annotations


def _user_may_see(user, permission_code) -> bool:
    """Vrai si ``user`` peut voir un champ gardé par ``permission_code``.

    * pas d'utilisateur / non authentifié → masqué (False) ;
    * superuser → True ;
    * compte SANS rôle fin (``role`` absent) → repli historique True (on ne
      retire jamais un accès existant à un compte légacy) ;
    * sinon → l'utilisateur doit porter la permission ERP ``permission_code``.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if getattr(user, "role_id", None) is None and getattr(user, "role", None) is None:
        return True  # compte légacy sans rôle fin → comportement historique
    checker = getattr(user, "has_erp_permission", None)
    if callable(checker):
        return bool(checker(permission_code))
    return False


class SensitiveFieldMaskMixin:
    """Retire du payload les champs sensibles non autorisés (YRBAC7).

    Déclarez ``sensitive_fields`` = ``{nom_champ: codename_permission}`` sur le
    sérialiseur. À la sérialisation, tout champ dont l'utilisateur de la requête
    n'a pas la permission est ABSENT de la représentation (pas ``None``).

    Le mixin surcharge ``to_representation`` : il ne modifie jamais l'instance
    ni la base, seulement la sortie. Sans ``context['request']`` (ex. rendu
    interne/serveur), rien n'est masqué (comportement inchangé).
    """

    sensitive_fields: dict = {}

    def _request_user(self):
        request = self.context.get("request") if hasattr(self, "context") else None
        return getattr(request, "user", None) if request is not None else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.sensitive_fields:
            return data
        user = self._request_user()
        if user is None:
            # Pas de requête (rendu serveur/interne) → ne rien masquer.
            return data
        for field_name, permission_code in self.sensitive_fields.items():
            if field_name in data and not _user_may_see(user, permission_code):
                data.pop(field_name, None)
        return data


# ─────────────────────────────────────────────────────────────────────────────
# YRBAC8 — Champs pilotés serveur : jamais posés par le body
# ─────────────────────────────────────────────────────────────────────────────

# Champs de gouvernance qu'un client ne doit JAMAIS pouvoir poser via le body
# d'un POST/PATCH : ils sont toujours dérivés côté serveur. Un sérialiseur peut
# étendre cette liste via ``server_controlled_fields``.
DEFAULT_SERVER_CONTROLLED_FIELDS = frozenset({
    "company",
    "company_id",
    "created_by",
    "created_by_id",
    "updated_by",
    "owner",
    "role",
    "role_id",
    "is_staff",
    "is_superuser",
    "is_active",
})


class ServerControlledFieldsMixin:
    """Ignore les champs de gouvernance présents dans le body (YRBAC8).

    Anti-mass-assignment transversal : avant validation, retire du payload
    entrant tout champ de ``DEFAULT_SERVER_CONTROLLED_FIELDS`` (étendu par
    ``server_controlled_fields`` sur le sérialiseur). La valeur de ces champs
    vient TOUJOURS du serveur (``perform_create``/``TenantMixin``/défaut modèle),
    jamais du client — injecter ``company=<autre>`` ou ``is_superuser=true`` dans
    un POST/PATCH est simplement ignoré.

    ``core`` reste FONDATION : aucune dépendance app métier.
    """

    server_controlled_fields: frozenset = frozenset()

    def _server_controlled(self) -> frozenset:
        return DEFAULT_SERVER_CONTROLLED_FIELDS | frozenset(
            self.server_controlled_fields)

    def to_internal_value(self, data):
        blocked = self._server_controlled()
        if hasattr(data, "keys") and any(k in blocked for k in list(data.keys())):
            # Copie mutable (QueryDict est immuable) puis purge les champs.
            try:
                data = data.copy()
            except AttributeError:
                data = dict(data)
            if hasattr(data, "_mutable"):
                data._mutable = True
            for key in list(data.keys()):
                if key in blocked:
                    data.pop(key, None)
        return super().to_internal_value(data)

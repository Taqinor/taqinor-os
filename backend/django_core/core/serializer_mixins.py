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

``core`` reste FONDATION : ce mixin ne dépend d'aucune app métier.
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

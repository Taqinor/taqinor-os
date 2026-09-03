"""AUD185 — scope société pour l'administration Django (`/admin/`).

Constat F10 de l'audit L3 : AUCUN `admin.py` du dépôt ne surchargeait
`get_queryset`, alors que la quasi-totalité des modèles métier portent un FK
`company` et que tous les ViewSets DRF, eux, filtrent sur
`request.user.company` (`core.viewsets.CompanyScopedModelViewSet`). Un compte
`is_staff`/`is_superuser` d'une société y listait donc les factures, écritures
et comptes de trésorerie de TOUTES les autres.

Ce mixin est la contrepartie admin de ce filtre. Il est volontairement
DÉFENSIF pour pouvoir être appliqué en bloc à un `admin.py` entier :

* modèle sans champ `company`, ou champ non relationnel → aucun filtre
  (comportement historique strictement inchangé) ;
* utilisateur sans société (opérateur plateforme, `company` NULL) → aucun
  filtre : c'est le seul compte censé voir le parc entier, et le lui retirer
  aurait cassé l'exploitation sans rien protéger.

Il vit dans `core` (couche fondation) et non dans une app métier : les
administrations de `ventes`, `compta` — et `stock` (AUD215) — doivent partager
LE MÊME mixin sans qu'une app en importe une autre.
"""
from django.core.exceptions import FieldDoesNotExist


class CompanyScopedAdminMixin:
    """Filtre le queryset d'un `ModelAdmin` sur la société de l'utilisateur.

    À placer AVANT `admin.ModelAdmin` dans les bases de la classe pour que son
    `get_queryset` s'applique (`class FactureAdmin(CompanyScopedAdminMixin,
    admin.ModelAdmin)`).
    """

    #: nom du champ portant la société sur le modèle administré.
    company_scope_field = 'company'

    def _scope_company_id(self, request):
        """Id de la société de l'utilisateur, ou None (= pas de filtre)."""
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return None
        return getattr(user, 'company_id', None)

    def _scope_field_is_relation(self):
        """Vrai si le modèle administré porte bien un FK société filtrable."""
        try:
            champ = self.model._meta.get_field(self.company_scope_field)
        except (FieldDoesNotExist, AttributeError):
            return False
        return bool(getattr(champ, 'is_relation', False))

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        company_id = self._scope_company_id(request)
        if company_id is None or not self._scope_field_is_relation():
            return qs
        return qs.filter(**{self.company_scope_field: company_id})

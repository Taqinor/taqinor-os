"""SPL76 — briques PARTAGÉES par ``views.py`` et les modules de vues de la
scission crm (``*_views.py``) : les listes d'actions ``READ_ACTIONS`` /
``WRITE_ACTIONS`` et le mixin de portée des viewsets enfants
(``_PorteeEnfantsMixin``, ACRM9), déplacés de ``views.py`` à l'identique.

Un module de propriétaire ne peut pas importer ``views.py`` : ce module
neutre (qui n'importe aucune vue) porte donc ce que plusieurs d'entre eux
lisent.
"""
from authentication.scoping import scope_client_queryset

from .models import Client


READ_ACTIONS = ['list', 'retrieve']


class _PorteeEnfantsMixin:
    """ACRM9 (C-ACRM-005) — les LECTURES d'un viewset ENFANT d'un lead ou
    d'un client sont bornées à la portée du rôle : une ligne dont le lead
    (``portee_leads``) sort de ``selectors.leads_en_portee(user)``, ou dont
    le client (``portee_clients``) sort de ``scope_client_queryset``, est
    ABSENTE — liste vide sur ``?lead=<hors portée>``, 404 en détail. Une
    relation vide (``NULL``) ne masque rien. Un admin (portée « all ») voit
    tout, comme avant."""

    portee_leads = ()
    portee_clients = ()

    def get_queryset(self):
        from django.db.models import Q

        from .selectors import leads_en_portee

        qs = super().get_queryset()
        user = self.request.user
        if self.portee_leads:
            leads = leads_en_portee(user).values('pk')
            for champ in self.portee_leads:
                qs = qs.filter(Q(**{f'{champ}__isnull': True})
                               | Q(**{f'{champ}__in': leads}))
        if self.portee_clients:
            clients = scope_client_queryset(
                Client.objects.filter(company_id=user.company_id),
                user).values('pk')
            for champ in self.portee_clients:
                qs = qs.filter(Q(**{f'{champ}__isnull': True})
                               | Q(**{f'{champ}__in': clients}))
        return qs


WRITE_ACTIONS = ['create', 'update', 'partial_update']

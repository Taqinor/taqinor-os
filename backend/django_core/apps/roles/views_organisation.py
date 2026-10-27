"""Organigramme (fondateur, 27/10/2026) — CRUD des départements, des
fonctions (postes) et des équipes génériques.

Lecture : tout rôle (``IsAnyRole``) ; écriture : palier ADMIN
(``IsAdminRole``, comme ``crm.EquipeCommercialeViewSet``). Société forcée côté
serveur. Chaque écriture recalcule la hiérarchie (``supervisor``) DANS la même
transaction : une boucle de supervision refusée annule tout."""
from django.db import transaction
from rest_framework.parsers import JSONParser

from authentication.equipes_structure import (
    enregistrer_equipe, recalculer_hierarchie, supprimer_equipe)
from authentication.permissions import IsAdminRole, IsAnyRole
from core.viewsets import CompanyScopedModelViewSet

from .models import Departement, EquipeOrg, Poste, Role
from .serializers_organisation import (
    DepartementSerializer, EquipeOrgSerializer, PosteSerializer)

READ_ACTIONS = ('list', 'retrieve')


class _StructureViewSet(CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF6 — aucun upload sur ces vues

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def _enregistrer(self, serializer):
        company = self.request.user.company
        with transaction.atomic():
            instance = serializer.save(company=company)
            recalculer_hierarchie(company.pk)
        return instance

    def perform_create(self, serializer):
        self._enregistrer(serializer)

    def perform_update(self, serializer):
        self._enregistrer(serializer)

    def perform_destroy(self, instance):
        company_id = instance.company_id
        with transaction.atomic():
            instance.delete()
            recalculer_hierarchie(company_id)


class DepartementViewSet(_StructureViewSet):
    """Départements (Direction comprise, une seule par société)."""
    queryset = Departement.objects.select_related('responsable').all()
    serializer_class = DepartementSerializer


class PosteViewSet(_StructureViewSet):
    """Fonctions : changer le rôle par défaut d'une fonction le propage aux
    titulaires qui portaient encore l'ancien ; changer l'intitulé le recopie
    dans leur ``poste`` (texte d'affichage)."""
    queryset = Poste.objects.select_related('departement', 'role').all()
    serializer_class = PosteSerializer

    def perform_update(self, serializer):
        from .services import propager_poste
        ancien_role_id = serializer.instance.role_id
        company = self.request.user.company
        with transaction.atomic():
            poste = serializer.save(company=company)
            changes = propager_poste(poste, ancien_role_id)
            recalculer_hierarchie(company.pk)
        # FG18 — un rôle changé par la fonction laisse une trace au journal
        # d'audit, comme un changement fait depuis la fiche du compte.
        from apps.parametres.models import SettingsAuditLog
        ancien = Role.objects.filter(pk=ancien_role_id).first()
        for user in changes:
            SettingsAuditLog.log_change(
                company=company, user=self.request.user,
                section='utilisateurs', field=f'user:{user.username}:role',
                field_label=f'Rôle de {user.username} (fonction '
                            f'« {poste.intitule} »)',
                old=ancien.nom if ancien else '—', new=poste.role.nom)


class EquipeOrgViewSet(_StructureViewSet):
    """Équipes génériques : une personne = une seule équipe active (les trois
    types confondus) ; le chef devient le superviseur des membres."""
    queryset = EquipeOrg.objects.select_related(
        'departement', 'chef').prefetch_related('membres').all()
    serializer_class = EquipeOrgSerializer

    def perform_create(self, serializer):
        enregistrer_equipe(
            serializer, 'chef', company=self.request.user.company)

    def perform_update(self, serializer):
        enregistrer_equipe(
            serializer, 'chef', company=self.request.user.company)

    def perform_destroy(self, instance):
        supprimer_equipe(instance, 'chef', instance.delete)

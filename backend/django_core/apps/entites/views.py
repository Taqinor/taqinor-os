from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core.viewsets import CompanyScopedModelViewSet

from . import import_service, selectors, services
from .models import Entite
from .permissions import IsAdministrateur
from .serializers import EntiteSerializer

# Jetons acceptés comme booléen "vrai" dans un corps de requête (form-data ou
# JSON) : parse STRICTE — seul un jeton explicite active le mode, jamais une
# troncature implicite d'une chaîne quelconque (une valeur absente, `'0'`,
# `'false'`, etc. restent "faux").
_JETONS_VRAI = ('1', 'true', 'True', 'oui', 'Oui', True)


def _est_vrai(valeur):
    return valeur in _JETONS_VRAI


class EntiteViewSet(CompanyScopedModelViewSet):
    """NTADM1 — CRUD `Entite` (Administrateur only) + arbre (`?tree=1`) +
    chatter générique (NTADM47) via `records`."""

    serializer_class = EntiteSerializer
    permission_classes = [IsAdministrateur]
    queryset = Entite.objects.all()

    def get_queryset(self):
        return Entite.objects.filter(
            company=self.request.user.company).select_related('parent')

    def initial(self, request, *args, **kwargs):
        # NTADM39 — permission fine `adminops_entites_gerer` sur toute
        # ÉCRITURE (le palier IsAdministrateur reste acquis en amont ; ce
        # contrôle RESSERRE pour les rôles custom, rétrocompat es_systeme).
        # Contrôle EXPLICITE ici, jamais via get_permissions (bug-class #25).
        super().initial(request, *args, **kwargs)
        if (request.method in ('POST', 'PUT', 'PATCH', 'DELETE')
                and getattr(self, 'action', None) != 'noter'):
            # `noter` = note de chatter (records), pas une édition d'Entité —
            # hors du champ de la clé fine.
            from apps.adminops.permissions import (
                ADMINOPS_ENTITES_GERER, a_permission_fine)
            if not a_permission_fine(request.user, ADMINOPS_ENTITES_GERER):
                raise PermissionDenied(
                    "Permission 'adminops_entites_gerer' requise.")

    def list(self, request, *args, **kwargs):
        if request.query_params.get('tree') == '1':
            return Response(selectors.entite_tree(request.user.company))
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        entite = services.creer_entite(
            self.request.user.company,
            nom=serializer.validated_data['nom'],
            code=serializer.validated_data['code'],
            parent=serializer.validated_data.get('parent'),
            user=self.request.user)
        serializer.instance = entite

    def perform_update(self, serializer):
        entite = serializer.instance
        ancien_nom = entite.nom
        ancien_parent = entite.parent

        nouveau_parent = serializer.validated_data.get('parent', ancien_parent)
        if nouveau_parent != ancien_parent:
            services.valider_non_cycle(entite, nouveau_parent)

        instance = serializer.save()

        from apps.records.services import log_field_change
        if instance.nom != ancien_nom:
            log_field_change(
                instance, 'nom', ancien_nom, instance.nom,
                user=self.request.user, field_label='Nom')
        if instance.parent_id != (ancien_parent.id if ancien_parent else None):
            log_field_change(
                instance, 'parent',
                ancien_parent.nom if ancien_parent else '',
                instance.parent.nom if instance.parent else '',
                user=self.request.user, field_label='Entité parente')

    def perform_destroy(self, instance):
        # NTADM1/11 — jamais de suppression dure : DELETE == désactivation.
        services.desactiver_entite(instance, user=self.request.user)

    @action(detail=True, methods=['post'])
    def desactiver(self, request, pk=None):
        entite = self.get_object()
        services.desactiver_entite(entite, user=request.user)
        return Response(EntiteSerializer(entite).data)

    @action(detail=True, methods=['get'])
    def historique(self, request, pk=None):
        """NTADM47 — fil d'activité (chatter générique `records`)."""
        entite = self.get_object()
        from apps.records.services import chatter_qs
        activites = chatter_qs(entite, company=request.user.company)
        data = [{
            'id': a.id,
            'kind': a.kind,
            'field_label': a.field_label,
            'old_value': a.old_value,
            'new_value': a.new_value,
            'body': a.body,
            'created_by': getattr(a.created_by, 'username', None),
            'created_at': a.created_at,
        } for a in activites]
        return Response(data)

    @action(detail=True, methods=['post'])
    def noter(self, request, pk=None):
        """NTADM47 — note manuelle de chatter."""
        entite = self.get_object()
        body = request.data.get('body', '')
        from apps.records.services import log_note
        log_note(entite, request.user, body)
        return Response({'ok': True})

    @action(detail=False, methods=['get'], url_path='mes-entites',
            permission_classes=[IsAnyRole])
    def mes_entites(self, request):
        """NTADM26 — entités ACTIVES accessibles à l'appelant (id/code/nom).

        Alimente la bascule d'entité de l'en-tête, donc ouverte à TOUT
        collaborateur interne (le reste du viewset reste Administrateur).
        Lecture minimale et scopée : société de la requête + périmètre de rôle
        NTADM3. Ce n'est PAS une garde — la bascule n'est qu'un filtre
        d'affichage ; chaque endpoint refait son propre scoping.
        """
        return Response(selectors.entites_accessibles(
            request.user, request.user.company))

    @action(detail=False, methods=['get'], permission_classes=[IsAdministrateur])
    def groupe(self, request):
        """NTADM25 — vue consolidée « Groupe », LECTURE SEULE (Administrateur).

        Une colonne de KPI par entité ACTIVE + une colonne Total. Pure lecture
        cross-app via les sélecteurs de ventes/crm/stock filtrés sur le champ
        ``entite`` de NTADM2 — aucun calcul nouveau, aucune écriture, et ce
        n'est PAS une consolidation comptable. ``disponible`` reste False tant
        que la société compte moins de deux entités actives.
        """
        return Response(selectors.consolidation_groupe(request.user.company))

    @action(detail=False, methods=['get'], permission_classes=[IsAdministrateur])
    def export(self, request):
        """NTADM28 — export xlsx du référentiel (code/nom/parent/actif).

        Les colonnes nb_devis_rattaches/nb_leads_rattaches restent à 0 tant que
        NTADM2 (FK `entite` sur crm.Lead/ventes.Devis) n'est pas livré — cette
        tâche est DIFFÉRÉE (migration foreign app, hors périmètre NTADM lane).
        """
        from apps.records.xlsx import build_xlsx_response

        company = request.user.company
        entites = Entite.objects.filter(company=company).select_related('parent').order_by('code')
        headers = ['Code', 'Nom', 'Parent', 'Actif',
                   'Nb devis rattachés', 'Nb leads rattachés']
        rows = [
            [e.code, e.nom, e.parent.code if e.parent else '',
             'Oui' if e.actif else 'Non', 0, 0]
            for e in entites
        ]
        return build_xlsx_response('entites', headers, rows, sheet_title='Entités')

    @action(detail=False, methods=['post'], permission_classes=[IsAdministrateur])
    def importer(self, request):
        """NTADM43 — import CSV en masse (dry-run par défaut ; `commit=1` écrit).

        Colonnes CSV : code, nom, code_parent (optionnel). Résolution des
        parents par code en 2 passes.

        GARDE-FOU ÉCRASEMENT — `commit=0`/absent reste l'APERÇU : il ne
        touche jamais la base et signale (`conflits`) ce qu'un commit
        écraserait sur des fiches existantes. `commit=1` écrit en mode
        REMPLISSAGE SEUL par défaut (un champ déjà rempli n'est jamais
        remplacé) ; `ecraser=1` est l'opt-in explicite qui autorise aussi les
        remplacements. `company` vient TOUJOURS de `request.user.company` —
        jamais du corps de la requête (isolation multi-tenant).
        """
        fichier = request.FILES.get('fichier')
        if fichier is None:
            return Response({'detail': 'Fichier requis.'}, status=400)
        file_bytes = fichier.read()
        filename = fichier.name
        commit = _est_vrai(request.data.get('commit'))
        ecraser = _est_vrai(request.data.get('ecraser'))
        try:
            if commit:
                result = import_service.commit(
                    file_bytes, filename, request.user.company,
                    user=request.user, ecraser=ecraser)
            else:
                result = import_service.dry_run(file_bytes, filename, request.user.company)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(result)

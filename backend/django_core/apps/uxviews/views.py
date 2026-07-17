import json

from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import SavedView
from .serializers import SavedViewSerializer


def _is_valid_configuration(configuration):
    """NTUX34 — validation STRUCTURELLE de `configuration` (aucun registre de
    champs par écran n'existe côté serveur — `SavedView.configuration` est un
    blob JSON opaque au backend, cf. models.py — donc on vérifie sa FORME,
    pas la validité métier de chaque champ). `colonnes_visibles`, si présent,
    doit être une liste ; `filtres`, si présent, doit respecter le contrat
    `{op, conditions: [...]}`  de `filterLogic.js` (`isGroup`)."""
    if not isinstance(configuration, dict):
        return False
    colonnes = configuration.get('colonnes_visibles')
    if colonnes is not None and not isinstance(colonnes, list):
        return False
    filtres = configuration.get('filtres')
    if filtres is not None:
        if not isinstance(filtres, dict) or not isinstance(filtres.get('conditions'), list):
            return False
    return True


class SavedViewViewSet(CompanyScopedModelViewSet):
    """NTUX1/2 — CRUD des vues sauvegardées, filtré par `?ecran=`. Une vue est
    visible si l'appelant en est le propriétaire, OU si elle est partagée à
    l'équipe (`visibilite=EQUIPE`) — la société est déjà bornée par
    `TenantMixin.get_queryset`. Lecture ouverte à tout rôle authentifié ;
    écriture limitée au propriétaire (une vue d'un autre utilisateur n'est
    modifiable/supprimable que si elle est la vue par défaut d'un rôle ET que
    l'appelant a le droit de la définir — cf. `IsResponsableOrAdmin`)."""
    queryset = SavedView.objects.select_related('owner', 'role').all()
    serializer_class = SavedViewSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ecran = self.request.query_params.get('ecran')
        if ecran:
            qs = qs.filter(ecran=ecran)
        user = self.request.user
        return qs.filter(
            Q(owner=user) | Q(visibilite=SavedView.Visibilite.EQUIPE),
        )

    def get_permissions(self):
        # NTUX23/34 — les actions de gouvernance de l'écran `/parametres/vues`
        # (liste TOUTE la company, export xlsx, import CSV) sont réservées
        # Directeur/Admin, comme `definir_par_defaut_role` (NTUX2).
        if self.action in ('definir_par_defaut_role', 'toutes_company', 'export_xlsx', 'importer'):
            return [IsResponsableOrAdmin()]
        return [IsAnyRole()]

    def perform_create(self, serializer):
        # NTUX28 (limites anti-abus) reste hors périmètre de ce lot — posé ici
        # comme garde-fou de base minimal : owner/company toujours serveur.
        serializer.save(company=self.request.user.company, owner=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        # Garde-fou NTUX2 : une vue par défaut de rôle n'est modifiable que par
        # son propriétaire OU par qui a le droit de la (re)définir.
        if instance.owner_id != self.request.user.id and not (
            instance.est_defaut_role and IsResponsableOrAdmin().has_permission(self.request, self)
        ):
            raise PermissionDenied("Vous ne pouvez modifier que vos propres vues.")
        serializer.save()

    def perform_destroy(self, instance):
        # Garde-fou NTUX2 : une vue par défaut de rôle ne peut être supprimée
        # que par qui a le droit de la définir (jamais un simple propriétaire
        # accidentel — la vue peut appartenir à quelqu'un d'autre après un
        # transfert de portefeuille).
        if instance.est_defaut_role and not IsResponsableOrAdmin().has_permission(self.request, self):
            raise PermissionDenied(
                "Seul un Directeur/Admin peut supprimer une vue par défaut de rôle.",
            )
        if instance.owner_id != self.request.user.id and not instance.est_defaut_role:
            raise PermissionDenied("Vous ne pouvez supprimer que vos propres vues.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='definir-par-defaut-role')
    def definir_par_defaut_role(self, request, pk=None):
        """NTUX2 — Directeur/Admin uniquement. Définit CETTE vue comme vue par
        défaut du rôle (celui déjà porté par la vue, ou fourni dans le corps
        `{role: <id>}`). Un seul défaut actif par (company, ecran, role) : les
        autres vues du même rôle+écran perdent `est_defaut_role`."""
        instance = self.get_object()
        role_id = request.data.get('role', instance.role_id)
        if not role_id:
            raise ValidationError({'role': 'Un rôle est requis pour définir une vue par défaut.'})
        SavedView.objects.filter(
            company=instance.company, ecran=instance.ecran, role_id=role_id,
            est_defaut_role=True,
        ).exclude(pk=instance.pk).update(est_defaut_role=False)
        instance.role_id = role_id
        instance.est_defaut_role = True
        instance.visibilite = SavedView.Visibilite.EQUIPE
        instance.save(update_fields=['role', 'est_defaut_role', 'visibilite', 'updated_at'])
        return Response(SavedViewSerializer(instance).data)

    @action(detail=False, methods=['get'], url_path='toutes-company')
    def toutes_company(self, request):
        """NTUX23 — Rapport « configuration des vues actives » : liste ADMIN
        de TOUTES les `SavedView` de la company (au-delà du filtre perso/
        équipe de `list()`/`get_queryset` ci-dessus), pour l'écran de
        gouvernance `/parametres/vues`. Directeur/Admin uniquement — sert de
        base à l'audit avant un contrôle qualité ou un onboarding commercial."""
        views = SavedView.objects.filter(
            company=request.user.company,
        ).select_related('owner', 'role').order_by('ecran', 'nom')
        return Response(SavedViewSerializer(views, many=True).data)

    @action(detail=False, methods=['get'], url_path='export-xlsx')
    def export_xlsx(self, request):
        """NTUX23 — export .xlsx du même rapport de gouvernance (colonnes :
        écran, nom, propriétaire, visibilité, rôle par défaut, dernière
        modification) — moteur .xlsx PARTAGÉ `apps.records.xlsx` (foundation
        app, exempte de la frontière inter-apps), jamais le moteur
        `quote_engine` (rule #4, hors périmètre — les vues n'ont rien à voir
        avec les devis)."""
        from apps.records.xlsx import build_xlsx_response

        views = SavedView.objects.filter(
            company=request.user.company,
        ).select_related('owner', 'role').order_by('ecran', 'nom')
        headers = ['Écran', 'Nom', 'Propriétaire', 'Visibilité', 'Rôle par défaut', 'Dernière modification']
        rows = []
        for v in views:
            owner = v.owner
            owner_nom = ''
            if owner:
                full = f'{getattr(owner, "first_name", "")} {getattr(owner, "last_name", "")}'.strip()
                owner_nom = full or getattr(owner, 'username', '') or getattr(owner, 'email', '') or ''
            rows.append([
                v.ecran,
                v.nom,
                owner_nom,
                v.get_visibilite_display(),
                v.role.nom if v.est_defaut_role and v.role_id else '',
                v.updated_at,
            ])
        return build_xlsx_response(
            'vues-sauvegardees.xlsx', headers, rows, sheet_title='Vues sauvegardées')

    @action(detail=False, methods=['post'], url_path='importer', parser_classes=[MultiPartParser])
    def importer(self, request):
        """NTUX34 — import CSV/XLSX de `SavedView` entre environnements (ex.
        staging → prod, ou d'une company sœur), depuis `/parametres/vues`
        (NTUX23). Colonnes attendues : `ecran`, `nom`, `configuration` (JSON
        sérialisé). Directeur/Admin uniquement.

        Validation STRICTE ligne par ligne (numérotée à partir de 1 = 1re
        ligne de données, après l'en-tête) : JSON invalide ou structure
        `configuration` invalide (cf. `_is_valid_configuration`) → ligne
        REJETÉE avec un message, les autres lignes valides sont importées
        quand même — jamais un import tout-ou-rien.

        Jamais d'écrasement silencieux : une vue existante du même
        (owner, écran, nom) est renommée `<nom> (import)` plutôt que
        remplacée. La vue importée devient TOUJOURS personnelle (owner =
        l'utilisateur qui importe, jamais une visibilité équipe automatique —
        le partage reste un acte explicite, cf. `definir_par_defaut_role`)."""
        from apps.dataimport.parsing import iter_rows, normalize_header

        fichier = request.FILES.get('fichier')
        if not fichier:
            raise ValidationError({'fichier': 'Un fichier CSV ou XLSX est requis.'})

        _headers, raw_rows = iter_rows(fichier.read(), fichier.name)
        rows = [
            {normalize_header(k): v for k, v in row.items()}
            for row in raw_rows
        ]

        created = []
        erreurs = []
        for i, row in enumerate(rows, start=1):
            ecran = str(row.get('ecran') or '').strip()
            nom = str(row.get('nom') or '').strip()
            config_raw = row.get('configuration')
            if not ecran or not nom:
                erreurs.append({'ligne': i, 'message': "colonnes 'ecran' et 'nom' requises."})
                continue
            try:
                configuration = json.loads(config_raw) if config_raw else {}
            except (TypeError, ValueError):
                erreurs.append({'ligne': i, 'message': 'JSON de configuration invalide.'})
                continue
            if not _is_valid_configuration(configuration):
                erreurs.append({
                    'ligne': i,
                    'message': "configuration invalide : 'colonnes_visibles' doit être une liste et "
                               "'filtres' doit être un groupe {op, conditions}.",
                })
                continue

            final_nom = nom
            if SavedView.objects.filter(
                company=request.user.company, owner=request.user, ecran=ecran, nom=nom,
            ).exists():
                final_nom = f'{nom} (import)'

            view = SavedView.objects.create(
                company=request.user.company, owner=request.user,
                ecran=ecran, nom=final_nom, configuration=configuration,
                visibilite=SavedView.Visibilite.PERSONNELLE,
            )
            created.append(SavedViewSerializer(view).data)

        return Response({'created': created, 'erreurs': erreurs})

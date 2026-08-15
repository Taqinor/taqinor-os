import json

from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminOrResponsableTier, IsAnyRole, IsResponsableOrAdmin,
)
from core.permissions import declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet

from .models import FavoriUtilisateur, SavedView, UxParametres
from .serializers import (
    FavoriUtilisateurSerializer, SavedViewSerializer, UxParametresSerializer,
)


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

    def _verifier_partage_autorise(self, serializer, instance=None):
        """NTUX27 — refuse de PARTAGER une vue à l'équipe quand la société a
        désactivé `permettre_vues_partagees_equipe`.

        Ne fire QUE sur une bascule vers EQUIPE : une vue DÉJÀ partagée éditée
        pour une autre raison garde sa visibilité (le réglage repasse les vues
        existantes en lecture seule, il n'en supprime ni n'en départage aucune).
        """
        if serializer.validated_data.get('visibilite') != SavedView.Visibilite.EQUIPE:
            return
        if instance is not None and instance.visibilite == SavedView.Visibilite.EQUIPE:
            return
        parametres = UxParametres.get_or_default(self.request.user.company)
        if not parametres.permettre_vues_partagees_equipe:
            raise ValidationError({'visibilite': (
                "Le partage de vues à l'équipe est désactivé pour votre société."
            )})

    def perform_create(self, serializer):
        self._verifier_partage_autorise(serializer)
        self._verifier_limite_vues()
        serializer.save(company=self.request.user.company, owner=self.request.user)

    def _verifier_limite_vues(self):
        """NTUX28 — refuse la création au-delà de `max_vues_par_utilisateur`
        (réglage société, NTUX27) ; jamais de suppression automatique
        silencieuse d'une vue existante."""
        parametres = UxParametres.get_or_default(self.request.user.company)
        limite = parametres.max_vues_par_utilisateur
        actuel = SavedView.objects.filter(
            company=self.request.user.company, owner=self.request.user,
        ).count()
        if actuel >= limite:
            raise ValidationError({'detail': (
                f'Limite de {limite} vues personnelles atteinte. '
                'Supprimez-en une avant d\'en créer une nouvelle.'
            )})

    def perform_update(self, serializer):
        instance = self.get_object()
        # Garde-fou NTUX2 : une vue par défaut de rôle n'est modifiable que par
        # son propriétaire OU par qui a le droit de la (re)définir.
        if instance.owner_id != self.request.user.id and not (
            instance.est_defaut_role and IsResponsableOrAdmin().has_permission(self.request, self)
        ):
            raise PermissionDenied("Vous ne pouvez modifier que vos propres vues.")
        self._verifier_partage_autorise(serializer, instance=instance)
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
        # NTUX27 — une vue par défaut de rôle EST une vue partagée : si la
        # société a désactivé le partage d'équipe, on ne peut plus en poser.
        parametres = UxParametres.get_or_default(request.user.company)
        if not parametres.permettre_vues_partagees_equipe:
            raise ValidationError({'detail': (
                "Le partage de vues à l'équipe est désactivé pour votre société."
            )})
        # NTUX27 — restriction FINE optionnelle : quand la société a nommé des
        # rôles autorisés, le Directeur/Admin ne suffit plus, il faut porter
        # l'un de ces rôles. Liste VIDE = comportement historique inchangé.
        autorises = list(
            parametres.roles_autorises_definir_defaut.values_list('id', flat=True))
        if autorises and request.user.role_id not in autorises:
            raise PermissionDenied(
                "Votre rôle n'est pas autorisé à définir une vue par défaut.")
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


class FavoriUtilisateurViewSet(CompanyScopedModelViewSet):
    """NTUX12 — CRUD des favoris épinglés + réordonnancement.

    STRICTEMENT PERSONNEL : `get_queryset` restreint à `owner=request.user`
    PAR-DESSUS le scoping société de `TenantMixin`. Un favori d'un collègue est
    donc invisible (404 en détail), même pour un Directeur — c'est une
    préférence d'affichage, pas une donnée de gouvernance.
    """

    queryset = FavoriUtilisateur.objects.select_related('content_type').all()
    serializer_class = FavoriUtilisateurSerializer

    def get_permissions(self):
        # Une garde déclarée par l'@action PRIME (sinon le `permission_classes=`
        # du décorateur serait silencieusement jeté — cf. core.permissions).
        declared = declared_action_permissions(self)
        if declared is not None:
            return declared
        return [IsAnyRole()]

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)

    def perform_create(self, serializer):
        # `company` ET `owner` posés côté serveur — jamais lus du corps. Un
        # favori sans `ordre` explicite s'ajoute EN FIN de liste (le
        # glisser-déposer de NTUX21 le remontera ensuite).
        self._verifier_limite_favoris(serializer)
        extra = {'company': self.request.user.company, 'owner': self.request.user}
        if serializer.validated_data.get('ordre') is None:
            extra['ordre'] = self._prochain_ordre()
        serializer.save(**extra)

    def _verifier_limite_favoris(self, serializer):
        """NTUX28 — refuse l'épinglage au-delà de `max_favoris_par_utilisateur`
        (réglage société, NTUX27). Épingler deux fois la MÊME cible est un
        no-op géré par `FavoriUtilisateurSerializer.create` : on ne bloque donc
        jamais ce cas, seule une VRAIE nouvelle cible compte contre la limite."""
        content_type = getattr(serializer, '_content_type', None)
        object_id = serializer.validated_data.get('object_id')
        if content_type is not None and object_id is not None:
            deja_epingle = self.get_queryset().filter(
                content_type=content_type, object_id=object_id).exists()
            if deja_epingle:
                return
        parametres = UxParametres.get_or_default(self.request.user.company)
        limite = parametres.max_favoris_par_utilisateur
        actuel = self.get_queryset().count()
        if actuel >= limite:
            raise ValidationError({'detail': (
                f'Limite de {limite} favoris atteinte. '
                'Supprimez-en un avant d\'en épingler un nouveau.'
            )})

    def perform_update(self, serializer):
        serializer.save(company=self.request.user.company, owner=self.request.user)

    def _prochain_ordre(self):
        dernier = (FavoriUtilisateur.objects
                   .filter(company=self.request.user.company, owner=self.request.user)
                   .order_by('-ordre').values_list('ordre', flat=True).first())
        return 0 if dernier is None else dernier + 1

    @action(detail=True, methods=['post'], url_path='reordonner',
            permission_classes=[IsAnyRole])
    def reordonner(self, request, pk=None):
        """NTUX21 — déplace CE favori à la position `ordre` (0 = en tête) et
        renumérote la liste de l'utilisateur de façon contiguë.

        Renvoie la liste complète déjà ordonnée : l'écran n'a pas à recharger."""
        favori = self.get_object()
        try:
            cible = int(request.data.get('ordre'))
        except (TypeError, ValueError):
            raise ValidationError({'ordre': 'Un entier est requis.'})
        if cible < 0:
            raise ValidationError({'ordre': 'La position ne peut pas être négative.'})

        autres = list(self.get_queryset().exclude(pk=favori.pk))
        cible = min(cible, len(autres))
        autres.insert(cible, favori)
        for position, element in enumerate(autres):
            if element.ordre != position:
                element.ordre = position
                element.save(update_fields=['ordre', 'updated_at'])
        return Response(
            FavoriUtilisateurSerializer(self.get_queryset(), many=True).data)


class UxParametresView(generics.RetrieveUpdateAPIView):
    """NTUX27 — réglages UX de la société (écran `/parametres/ux`).

    SINGLETON par société : il n'y a rien à lister ni à créer, la ressource est
    résolue depuis `request.user.company` (jamais depuis une URL ni un corps —
    aucune fuite inter-société possible) et créée au défaut à la première
    lecture. D'où une vue de DÉTAIL sans identifiant plutôt qu'un ModelViewSet.

    LECTURE ouverte à tout collaborateur interne : `duree_hover_peek_ms` et
    `duree_undo_toast_s` pilotent l'UI de CHAQUE utilisateur, ils doivent donc
    être lisibles par tous. ÉCRITURE réservée Directeur/Admin (le palier limité
    n'entre pas dans `/parametres/*`).
    """

    serializer_class = UxParametresSerializer
    # Pas de PUT : un réglage se modifie champ par champ (PATCH), jamais par
    # remplacement complet (qui réinitialiserait silencieusement les autres).
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsAnyRole()]
        return [IsAdminOrResponsableTier()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Sert au garde « pas de rôle d'une autre société » du serializer.
        context['company'] = self.request.user.company
        return context

    def get_object(self):
        return UxParametres.get_or_default(self.request.user.company)

    def perform_update(self, serializer):
        # La société est TOUJOURS celle de l'appelant — jamais lue du corps.
        serializer.save(company=self.request.user.company)

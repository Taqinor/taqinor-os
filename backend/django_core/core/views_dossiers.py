"""NTWFL17 — API du dossier transverse (``core.Dossier``).

CRUD scopé société par ``CompanyScopedModelViewSet`` (``company`` FORCÉE côté
serveur, jamais lue du corps), plus trois actions de détail :

  * ``POST {id}/lier/``     — rattache un objet métier au dossier ;
  * ``POST {id}/delier/``   — détache cet objet ;
  * ``GET/POST {id}/checklist/`` — lit la checklist ou y ajoute/coche une étape.

NTWFL18 ajoute le chatter (``core.DossierActivity``) :

  * ``GET  {id}/historique/`` — le fil d'activité du dossier ;
  * ``POST {id}/noter/``      — une note manuelle ;
  * les changements de statut et les rattachements/détachements écrivent une
    entrée AUTOMATIQUE — l'auteur vient toujours de la requête, jamais du
    corps.

La cible d'un lien est désignée par sa CHAÎNE ``app_label.model`` +
``object_id`` : ``core`` reste une couche de fondation et n'importe aucune app
métier (contrat import-linter ``core-foundation-is-a-base-layer``) — la
résolution passe par ``ContentType``, qui est de la fondation Django.
"""
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from . import dossiers as dossiers_service
from .models import (
    Dossier, DossierActivity, DossierChecklistItem, DossierLien,
)
from .viewsets import CompanyScopedModelViewSet

#: NTWFL18 — champs dont un changement écrit une entrée de chatter AUTOMATIQUE.
CHAMPS_SUIVIS = [
    ('statut', 'Statut'),
    ('priorite', 'Priorité'),
    ('proprietaire_id', 'Propriétaire'),
    ('echeance', 'Échéance'),
    ('type_dossier', 'Type de dossier'),
]


class DossierActivitySerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(
        source='get_kind_display', read_only=True)
    user_username = serializers.CharField(
        source='user.username', read_only=True, default='')

    class Meta:
        model = DossierActivity
        fields = ['id', 'kind', 'kind_label', 'field', 'field_label',
                  'old_value', 'new_value', 'body', 'user_username',
                  'created_at']
        read_only_fields = fields


class DossierLienSerializer(serializers.ModelSerializer):
    cle_modele = serializers.CharField(read_only=True)

    class Meta:
        model = DossierLien
        fields = ['id', 'cle_modele', 'object_id', 'libelle', 'created_at']
        read_only_fields = fields


class DossierChecklistItemSerializer(serializers.ModelSerializer):
    fait_par_username = serializers.CharField(
        source='fait_par.username', read_only=True, default='')

    class Meta:
        model = DossierChecklistItem
        fields = ['id', 'libelle', 'ordre', 'fait', 'fait_par_username',
                  'fait_le', 'created_at', 'updated_at']
        read_only_fields = ['id', 'fait_par_username', 'fait_le',
                            'created_at', 'updated_at']


class DossierSerializer(serializers.ModelSerializer):
    type_dossier_label = serializers.CharField(
        source='get_type_dossier_display', read_only=True)
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)
    priorite_label = serializers.CharField(
        source='get_priorite_display', read_only=True)
    proprietaire_username = serializers.CharField(
        source='proprietaire.username', read_only=True, default='')
    liens = DossierLienSerializer(many=True, read_only=True)
    checklist = DossierChecklistItemSerializer(many=True, read_only=True)
    # NTWFL20 — l'étape courante du processus attaché, telle que l'écran
    # dossier l'affiche. ``None`` si le dossier n'a pas de processus (cas par
    # défaut) ou si celui-ci est terminé.
    etape_courante = serializers.SerializerMethodField()

    class Meta:
        model = Dossier
        # ``company`` est posée CÔTÉ SERVEUR — jamais lue du corps.
        # ``workflow_instance`` est posée par le moteur (NTWFL20), jamais par
        # le client : un dossier ne « choisit » pas son processus au POST.
        fields = ['id', 'type_dossier', 'type_dossier_label', 'titre',
                  'description', 'statut', 'statut_label', 'priorite',
                  'priorite_label', 'proprietaire', 'proprietaire_username',
                  'echeance', 'liens', 'checklist', 'workflow_instance',
                  'etape_courante', 'created_at', 'updated_at']
        read_only_fields = ['id', 'type_dossier_label', 'statut_label',
                            'priorite_label', 'proprietaire_username',
                            'liens', 'checklist', 'workflow_instance',
                            'etape_courante', 'created_at', 'updated_at']

    def get_etape_courante(self, obj):
        etape = dossiers_service.etape_courante_du_dossier(obj)
        if etape is None:
            return None
        return {
            'id': etape.pk,
            'ordre': etape.ordre,
            'nom': etape.step_def.nom,
            'statut': etape.statut,
            'statut_label': etape.get_statut_display(),
            'sla_echeance': etape.sla_echeance,
        }


def resoudre_content_type(cle_modele):
    """``'crm.lead'`` → le ``ContentType`` correspondant, ou ``None``.

    Fonction PURE (aucun état de requête) : la chaîne vient du client, elle
    est donc validée ici plutôt que crue sur parole."""
    morceaux = (cle_modele or '').strip().lower().split('.')
    if len(morceaux) != 2 or not all(morceaux):
        return None
    app_label, model = morceaux
    try:
        return ContentType.objects.get(app_label=app_label, model=model)
    except ContentType.DoesNotExist:
        return None


class DossierViewSet(CompanyScopedModelViewSet):
    """CRUD des dossiers transverses + rattachement/checklist (NTWFL17)."""

    serializer_class = DossierSerializer
    queryset = Dossier.objects.all()

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related('liens', 'checklist')
        params = self.request.query_params
        statut = (params.get('statut') or '').strip()
        if statut:
            qs = qs.filter(statut=statut)
        type_dossier = (params.get('type_dossier') or '').strip()
        if type_dossier:
            qs = qs.filter(type_dossier=type_dossier)
        return qs

    def perform_create(self, serializer):
        """Ouvre le chatter (NTWFL18) puis, si un modèle de processus est
        configuré pour ce ``type_dossier``, démarre le workflow (NTWFL20)."""
        super().perform_create(serializer)
        dossiers_service.journaliser_creation(
            serializer.instance, user=self.request.user)
        dossiers_service.demarrer_processus_si_configure(
            serializer.instance, user=self.request.user)

    def perform_update(self, serializer):
        """NTWFL18 — journalise les champs suivis qui ont réellement bougé."""
        avant = {
            champ: getattr(serializer.instance, champ)
            for champ, _ in CHAMPS_SUIVIS
        }
        super().perform_update(serializer)
        dossier = serializer.instance
        for champ, libelle in CHAMPS_SUIVIS:
            dossiers_service.journaliser_changement(
                dossier, champ, libelle, avant[champ], getattr(dossier, champ),
                user=self.request.user)

    @action(detail=True, methods=['get'])
    def historique(self, request, pk=None):
        """Le chatter du dossier, du plus récent au plus ancien."""
        dossier = self.get_object()
        return Response(DossierActivitySerializer(
            dossiers_service.historique(dossier), many=True).data)

    @action(detail=True, methods=['post'])
    def noter(self, request, pk=None):
        """Ajoute une note MANUELLE au chatter (``{body}``)."""
        dossier = self.get_object()
        activite = dossiers_service.noter(
            dossier, request.data.get('body'), user=request.user)
        if activite is None:
            return Response(
                {'body': 'Une note ne peut pas être vide.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(DossierActivitySerializer(activite).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def lier(self, request, pk=None):
        """Rattache ``{cle_modele, object_id, libelle?}`` au dossier."""
        dossier = self.get_object()
        ct = resoudre_content_type(request.data.get('cle_modele'))
        if ct is None:
            return Response(
                {'cle_modele': 'Type d\'objet inconnu — attendu '
                               '« app_label.model » (ex. « crm.lead »).'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            object_id = int(request.data.get('object_id'))
        except (TypeError, ValueError):
            return Response(
                {'object_id': 'Identifiant de cible manquant ou invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        if object_id <= 0:
            return Response(
                {'object_id': 'Identifiant de cible manquant ou invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        lien, cree = DossierLien.objects.get_or_create(
            dossier=dossier, content_type=ct, object_id=object_id,
            defaults={
                'company': dossier.company,
                'libelle': (request.data.get('libelle') or '')[:200],
            })
        if cree:
            dossiers_service.journaliser_lien(
                dossier, lien.cle_modele, object_id,
                libelle=lien.libelle, user=request.user)
        return Response(
            DossierLienSerializer(lien).data,
            status=status.HTTP_201_CREATED if cree else status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def delier(self, request, pk=None):
        """Détache ``{cle_modele, object_id}`` du dossier."""
        dossier = self.get_object()
        ct = resoudre_content_type(request.data.get('cle_modele'))
        try:
            object_id = int(request.data.get('object_id'))
        except (TypeError, ValueError):
            object_id = None
        if ct is None or object_id is None:
            return Response(
                {'detail': 'Cible introuvable : « cle_modele » et '
                           '« object_id » sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        supprimes, _ = DossierLien.objects.filter(
            dossier=dossier, content_type=ct, object_id=object_id).delete()
        if supprimes:
            dossiers_service.journaliser_lien(
                dossier, f'{ct.app_label}.{ct.model}', object_id,
                action='detache', user=request.user)
        return Response({'detache': bool(supprimes)})

    @action(detail=True, methods=['get', 'post'])
    def checklist(self, request, pk=None):
        """Lit la checklist, ou ajoute/coche une étape.

        ``POST {libelle, ordre?}`` ajoute une étape ;
        ``POST {item_id, fait}`` coche/décoche une étape existante — l'auteur
        et l'horodatage sont TOUJOURS posés côté serveur.
        """
        dossier = self.get_object()
        if request.method.lower() == 'get':
            items = dossier.checklist.all()
            return Response(DossierChecklistItemSerializer(
                items, many=True).data)

        item_id = request.data.get('item_id')
        if item_id is not None:
            item = dossier.checklist.filter(pk=item_id).first()
            if item is None:
                return Response(
                    {'item_id': 'Étape de checklist introuvable sur ce '
                                'dossier.'},
                    status=status.HTTP_404_NOT_FOUND)
            item.fait = bool(request.data.get('fait', True))
            item.fait_par = request.user if item.fait else None
            item.fait_le = timezone.now() if item.fait else None
            item.save(update_fields=['fait', 'fait_par', 'fait_le',
                                     'updated_at'])
            return Response(DossierChecklistItemSerializer(item).data)

        libelle = (request.data.get('libelle') or '').strip()
        if not libelle:
            return Response(
                {'libelle': 'Le libellé de l\'étape est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ordre = int(request.data.get('ordre') or 0)
        except (TypeError, ValueError):
            ordre = 0
        item = DossierChecklistItem.objects.create(
            company=dossier.company, dossier=dossier,
            libelle=libelle[:200], ordre=max(ordre, 0))
        return Response(DossierChecklistItemSerializer(item).data,
                        status=status.HTTP_201_CREATED)

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
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, PolymorphicProxySerializer, extend_schema,
    extend_schema_field, extend_schema_view, inline_serializer,
)
from rest_framework.parsers import JSONParser
from rest_framework import serializers, status
from core.serializers import CompanyScopedRelationsMixin
from rest_framework.decorators import action
from rest_framework.response import Response

from . import dossiers as dossiers_service
from .champs_stricts import BooleenStrict, ChaineStricte
from .mixins import SameCompanyFKSerializerMixin
from .parseurs import corps_valide
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


class DossierActivitySerializer(CompanyScopedRelationsMixin, serializers.ModelSerializer):
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


class DossierLienSerializer(CompanyScopedRelationsMixin, serializers.ModelSerializer):
    cle_modele = serializers.CharField(read_only=True)

    class Meta:
        model = DossierLien
        fields = ['id', 'cle_modele', 'object_id', 'libelle', 'created_at']
        read_only_fields = fields


# YAPIC6 — nommé `...Workflow...` (pas juste `DossierChecklistItemSerializer`) :
# apps.ventes.serializers_regulatory porte DÉJÀ un ``DossierChecklistItemSerializer``
# distinct (FG268, un AUTRE modèle ``DossierChecklistItem``) ; deux classes de
# même nom auraient produit le même composant OpenAPI "DossierChecklistItem"
# pour deux formes différentes — collision de nom, jamais de comportement.
class DossierWorkflowChecklistItemSerializer(CompanyScopedRelationsMixin, serializers.ModelSerializer):
    fait_par_username = serializers.CharField(
        source='fait_par.username', read_only=True, default='')

    class Meta:
        model = DossierChecklistItem
        fields = ['id', 'libelle', 'ordre', 'fait', 'fait_par_username',
                  'fait_le', 'created_at', 'updated_at']
        read_only_fields = ['id', 'fait_par_username', 'fait_le',
                            'created_at', 'updated_at']


class DossierSerializer(SameCompanyFKSerializerMixin,
                        serializers.ModelSerializer):
    # ASEC18 — le propriétaire est un utilisateur de LA société de la requête :
    # l'id d'un utilisateur voisin échoue comme un id absent (POST et PATCH).
    same_company_fields = ('proprietaire',)
    type_dossier_label = serializers.CharField(
        source='get_type_dossier_display', read_only=True)
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)
    priorite_label = serializers.CharField(
        source='get_priorite_display', read_only=True)
    # ERR-ENF11-FUZZ-CORE — toujours présent : avec ``source`` traversant un
    # propriétaire nul, DRF OMETTAIT le champ sur un PATCH (partial) alors que
    # le schéma le déclare requis (« Response violates schema »).
    proprietaire_username = serializers.SerializerMethodField()
    liens = DossierLienSerializer(many=True, read_only=True)
    checklist = DossierWorkflowChecklistItemSerializer(many=True, read_only=True)
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

    def get_proprietaire_username(self, obj) -> str:
        return getattr(obj.proprietaire, 'username', '') or ''

    @extend_schema_field(inline_serializer('DossierEtapeCourante', {
        'id': serializers.IntegerField(),
        'ordre': serializers.IntegerField(),
        'nom': serializers.CharField(),
        'statut': serializers.CharField(),
        'statut_label': serializers.CharField(),
        'sla_echeance': serializers.DateTimeField(allow_null=True),
    }, required=False, allow_null=True))
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


# ERR-ENF11-FUZZ-CORE — ``cle_modele`` publié avec sa forme
# (« app_label.model ») ; une forme valide mais un type inexistant est une
# cible introuvable : 404 documenté (400 avant, sur une requête conforme).
_CIBLE_LIEN = inline_serializer('DossierCibleLien', {
    'cle_modele': serializers.RegexField(
        r'^[A-Za-z_]\w*\.[A-Za-z_]\w*$',
        help_text='« app_label.model », ex. crm.lead.'),
    'object_id': serializers.IntegerField(min_value=1),
    'libelle': ChaineStricte(required=False, allow_blank=True),
})
_TYPE_INCONNU = ("Type d'objet introuvable — attendu « app_label.model » "
                 "(ex. « crm.lead »).")
# ERR-ENF11-FUZZ-CORE — POST checklist : DEUX formes exclusives (ajout d'une
# étape OU coche d'une étape) ; ``{}`` était conforme puis refusé.
_CHECKLIST_AJOUT = inline_serializer('DossierChecklistAjout', {
    'libelle': ChaineStricte(max_length=200),
    'ordre': serializers.IntegerField(required=False, min_value=0),
})
_NOTE = inline_serializer('DossierNoterRequest', {'body': ChaineStricte()})
_CHECKLIST_COCHE = inline_serializer('DossierChecklistCoche', {
    'item_id': serializers.IntegerField(),
    'fait': BooleenStrict(required=False, default=True),
})


@extend_schema_view(list=extend_schema(parameters=[
    OpenApiParameter(
        'statut', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False,
        description='Ne garder que ce statut.'),
    OpenApiParameter(
        'type_dossier', OpenApiTypes.STR, OpenApiParameter.QUERY,
        required=False, description='Ne garder que ce type de dossier.'),
]))
class DossierViewSet(CompanyScopedModelViewSet):
    """CRUD des dossiers transverses + rattachement/checklist (NTWFL17)."""

    serializer_class = DossierSerializer
    queryset = Dossier.objects.all()
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload

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

    @extend_schema(responses=DossierActivitySerializer(many=True))
    # ERR-ENF11-FUZZ-CORE — liste À PLAT : le schéma la publiait paginée.
    @action(detail=True, methods=['get'], pagination_class=None)
    def historique(self, request, pk=None):
        """Le chatter du dossier, du plus récent au plus ancien."""
        dossier = self.get_object()
        return Response(DossierActivitySerializer(
            dossiers_service.historique(dossier), many=True).data)

    @extend_schema(
        request=_NOTE,
        responses={201: DossierActivitySerializer})
    @action(detail=True, methods=['post'])
    def noter(self, request, pk=None):
        """Ajoute une note MANUELLE au chatter (``{body}``)."""
        dossier = self.get_object()
        # ERR-ENF11-FUZZ-CORE — `{"body": [null, null]}` ou un corps tableau
        # levaient AttributeError (500) : corps validé par le serializer publié.
        corps = corps_valide(request, _NOTE)
        activite = dossiers_service.noter(
            dossier, corps['body'], user=request.user)
        if activite is None:
            return Response(
                {'body': 'Une note ne peut pas être vide.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(DossierActivitySerializer(activite).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(
        request=_CIBLE_LIEN,
        responses={200: DossierLienSerializer, 201: DossierLienSerializer})
    @action(detail=True, methods=['post'])
    def lier(self, request, pk=None):
        """Rattache ``{cle_modele, object_id, libelle?}`` au dossier."""
        dossier = self.get_object()
        cible = corps_valide(request, _CIBLE_LIEN)
        ct = resoudre_content_type(cible['cle_modele'])
        if ct is None:
            return Response({'cle_modele': _TYPE_INCONNU},
                            status=status.HTTP_404_NOT_FOUND)
        object_id = cible['object_id']

        lien, cree = DossierLien.objects.get_or_create(
            dossier=dossier, content_type=ct, object_id=object_id,
            defaults={
                'company': dossier.company,
                'libelle': (cible.get('libelle') or '')[:200],
            })
        if cree:
            dossiers_service.journaliser_lien(
                dossier, lien.cle_modele, object_id,
                libelle=lien.libelle, user=request.user)
        return Response(
            DossierLienSerializer(lien).data,
            status=status.HTTP_201_CREATED if cree else status.HTTP_200_OK)

    @extend_schema(
        request=_CIBLE_LIEN,
        responses=inline_serializer('DossierDelierReponse', {
            'detache': serializers.BooleanField()}))
    @action(detail=True, methods=['post'])
    def delier(self, request, pk=None):
        """Détache ``{cle_modele, object_id}`` du dossier."""
        dossier = self.get_object()
        cible = corps_valide(request, _CIBLE_LIEN)
        ct = resoudre_content_type(cible['cle_modele'])
        object_id = cible['object_id']
        if ct is None:
            return Response({'detail': _TYPE_INCONNU},
                            status=status.HTTP_404_NOT_FOUND)
        supprimes, _ = DossierLien.objects.filter(
            dossier=dossier, content_type=ct, object_id=object_id).delete()
        if supprimes:
            dossiers_service.journaliser_lien(
                dossier, f'{ct.app_label}.{ct.model}', object_id,
                action='detache', user=request.user)
        return Response({'detache': bool(supprimes)})

    @extend_schema(
        methods=['GET'],
        responses=DossierWorkflowChecklistItemSerializer(many=True))
    @extend_schema(
        methods=['POST'],
        request=PolymorphicProxySerializer(
            component_name='DossierChecklistRequete',
            serializers=[_CHECKLIST_AJOUT, _CHECKLIST_COCHE],
            resource_type_field_name=None),
        responses={
            200: DossierWorkflowChecklistItemSerializer,
            201: DossierWorkflowChecklistItemSerializer,
        })
    @action(detail=True, methods=['get', 'post'], pagination_class=None)
    def checklist(self, request, pk=None):
        """Lit la checklist, ou ajoute/coche une étape.

        ``POST {libelle, ordre?}`` ajoute une étape ;
        ``POST {item_id, fait}`` coche/décoche une étape existante — l'auteur
        et l'horodatage sont TOUJOURS posés côté serveur.
        """
        dossier = self.get_object()
        if request.method.lower() == 'get':
            items = dossier.checklist.all()
            return Response(DossierWorkflowChecklistItemSerializer(
                items, many=True).data)

        coche = isinstance(request.data, dict) and 'item_id' in request.data
        donnees = corps_valide(
            request, _CHECKLIST_COCHE if coche else _CHECKLIST_AJOUT)
        if coche:
            item = dossier.checklist.filter(pk=donnees['item_id']).first()
            if item is None:
                return Response(
                    {'item_id': 'Étape de checklist introuvable sur ce '
                                'dossier.'},
                    status=status.HTTP_404_NOT_FOUND)
            item.fait = donnees['fait']
            item.fait_par = request.user if item.fait else None
            item.fait_le = timezone.now() if item.fait else None
            item.save(update_fields=['fait', 'fait_par', 'fait_le',
                                     'updated_at'])
            return Response(DossierWorkflowChecklistItemSerializer(item).data)

        item = DossierChecklistItem.objects.create(
            company=dossier.company, dossier=dossier,
            libelle=donnees['libelle'], ordre=donnees.get('ordre', 0))
        return Response(DossierWorkflowChecklistItemSerializer(item).data,
                        status=status.HTTP_201_CREATED)

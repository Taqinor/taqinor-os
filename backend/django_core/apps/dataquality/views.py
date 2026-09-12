"""NTDATA14/15 — surface HTTP de la qualité de données.

* ``/dataquality/regles/``   — CRUD des règles (company forcée serveur) ;
* ``/dataquality/rapport/``  — dernier taux de conformité par règle
  (``?entite=`` pour restreindre à un dataset ; ``?evaluer=1`` recalcule
  maintenant plutôt que d'attendre le job quotidien).

Toutes les lectures sont bornées à ``request.user.company`` par ``TenantMixin``
et par le queryset DÉJÀ scopé des datasets. Réservé au palier
responsable/admin : un rapport de qualité expose des identifiants de fiches
non conformes.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsResponsableOrAdmin
from core.mixins import TenantMixin

from . import selectors, services
from .models import (
    GoldenRecord, PropositionFusion, RegleQualite, ResultatQualite,
)


class RegleQualiteSerializer(serializers.ModelSerializer):
    type_regle_label = serializers.CharField(
        source='get_type_regle_display', read_only=True)
    severite_label = serializers.CharField(
        source='get_severite_display', read_only=True)

    class Meta:
        model = RegleQualite
        # `company` posée côté serveur — jamais lue du corps.
        fields = [
            'id', 'libelle', 'entite', 'champ', 'type_regle',
            'type_regle_label', 'parametres', 'severite', 'severite_label',
            'actif', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'type_regle_label', 'severite_label',
                            'created_at', 'updated_at']

    def validate(self, attrs):
        """Fait remonter la validation du modèle AU CHAMP fautif."""
        from django.core.exceptions import ValidationError as DjangoValidation

        instance = self.instance or RegleQualite()
        for champ, valeur in attrs.items():
            setattr(instance, champ, valeur)
        try:
            instance.clean()
        except DjangoValidation as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


class ResultatQualiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultatQualite
        fields = ['id', 'regle', 'entite', 'nb_lignes', 'nb_violations',
                  'taux_conformite', 'echantillon', 'evalue_le']
        read_only_fields = fields


class RegleQualiteViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des règles de qualité, bornées à la société."""
    serializer_class = RegleQualiteSerializer
    permission_classes = [IsResponsableOrAdmin]
    queryset = RegleQualite.objects.all()


class RapportQualiteView(APIView):
    """NTDATA15 — taux de conformité par règle (dernière évaluation).

    ``?entite=<dataset>`` restreint à une entité. ``?evaluer=1`` lance
    l'évaluation MAINTENANT (utile après avoir créé une règle) au lieu
    d'attendre le job quotidien ``dataquality.evaluer_qualite_donnees``.
    """

    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(
        responses=inline_serializer('RapportQualiteReponse', {
            'entite': serializers.CharField(allow_null=True),
            'regles': serializers.JSONField(),
        }))
    def get(self, request):
        entite = request.query_params.get('entite') or None
        if request.query_params.get('evaluer') in ('1', 'true', 'True'):
            services.evaluer_regles(request.user.company, entite,
                                    user=request.user)
        return Response({
            'entite': entite,
            'regles': services.rapport_qualite(request.user.company, entite),
        })


class CompletudeView(APIView):
    """NTDATA16 — part des champs CRITIQUES renseignés, par entité métier.

    ``GET /dataquality/completude/`` rend un score par entité (clients,
    pistes, produits, factures) + le détail champ par champ, et la moyenne
    des entités réellement mesurables. Une entité sans fiche n'a pas de score
    (jamais 100 %) et n'entre pas dans la moyenne.
    """

    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(
        responses=inline_serializer('CompletudeReponse', {
            'entites': serializers.JSONField(),
            'score_global': serializers.FloatField(allow_null=True),
        }))
    def get(self, request):
        return Response(selectors.completude_module(
            request.user.company, request.user))


class SanteDonneesView(APIView):
    """NTDATA21 — la carte « Santé des données » : 3 indicateurs, tous réels.

    ``GET /dataquality/sante/`` rend le taux de complétude global, le nombre
    de règles BLOQUANTES en violation et le nombre de doublons en attente de
    décision. ``disponible=false`` (société sans aucune règle de qualité) =
    carte MASQUÉE côté écran : trois zéros ressembleraient à un bon bulletin.
    """

    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(
        responses=inline_serializer('SanteDonneesReponse', {
            'disponible': serializers.BooleanField(),
            'completude_globale_pct': serializers.FloatField(allow_null=True),
            'regles_bloquantes_en_violation': serializers.IntegerField(
                allow_null=True),
            'bloquantes_non_evaluees': serializers.IntegerField(
                allow_null=True),
            'doublons_en_attente': serializers.IntegerField(allow_null=True),
        }))
    def get(self, request):
        return Response(selectors.sante_donnees(request.user.company,
                                                request.user))


class DoublonsView(APIView):
    """NTDATA17/19 — groupes de fiches qui désignent probablement la même
    entité (``/dataquality/doublons/<entite>/``).

    Entités : ``clients``, ``fournisseurs``, ``produits``. LECTURE SEULE —
    rien n'est fusionné ici : la fusion est une décision humaine, exposée
    séparément.
    """

    permission_classes = [IsResponsableOrAdmin]

    #: Entité d'URL → détecteur. Une entité inconnue est un 404 explicite.
    DETECTEURS = {
        'clients': 'doublons_clients',
        'fournisseurs': 'doublons_fournisseurs',
        'produits': 'doublons_produits',
    }

    @extend_schema(
        responses=inline_serializer('DoublonsReponse', {
            'entite': serializers.CharField(),
            'nb_groupes': serializers.IntegerField(),
            'groupes': serializers.JSONField(),
        }))
    def get(self, request, entite=None):
        nom_detecteur = self.DETECTEURS.get(entite)
        detecteur = getattr(services, nom_detecteur or '', None)
        if detecteur is None:
            return Response(
                {'detail': "Entité inconnue : « %s ». Entités disponibles : "
                           '%s.' % (entite, ', '.join(sorted(
                               self.DETECTEURS)))},
                status=status.HTTP_404_NOT_FOUND)
        groupes = detecteur(request.user.company, request.user)
        return Response({'entite': entite, 'nb_groupes': len(groupes),
                         'groupes': groupes})

    #: Entité d'URL → fonction de fusion supervisée (NTDATA18/19). Une entité
    #: SANS fusion câblée refuse explicitement plutôt que de faire semblant.
    FUSIONS = {
        'clients': 'fusionner_clients',
        'fournisseurs': 'fusionner_fournisseurs',
        'produits': 'fusionner_produits',
    }

    @extend_schema(
        request=inline_serializer('FusionRequete', {
            'survivant': serializers.IntegerField(),
            'doublons': serializers.ListField(
                child=serializers.IntegerField()),
        }),
        responses=inline_serializer('FusionReponse', {
            'survivant': serializers.IntegerField(),
            'absorbes': serializers.JSONField(),
            'repointes': serializers.JSONField(),
            'non_repointes': serializers.JSONField(),
        }))
    def post(self, request, entite=None):
        """NTDATA18/19 — FUSION supervisée d'un groupe (décision humaine).

        Corps : ``{"survivant": <id>, "doublons": [<id>, …]}``. Les doublons
        sont NEUTRALISÉS, jamais supprimés, et tout ce qui les référençait
        pointe désormais le survivant. La réponse NOMME ce qui n'a pas pu
        être repointé (contrainte d'unicité déjà occupée) au lieu de le taire.
        """
        nom_fusion = self.FUSIONS.get(entite)
        fusion = getattr(services, nom_fusion or '', None)
        if fusion is None:
            return Response(
                {'detail': "Aucune fusion supervisée pour l'entité "
                           '« %s ».' % entite},
                status=status.HTTP_404_NOT_FOUND)
        corps = request.data or {}
        survivant = corps.get('survivant')
        if not survivant:
            return Response({'survivant': 'Indiquez la fiche à conserver.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            rapport = fusion(request.user.company, request.user,
                             int(survivant), corps.get('doublons') or [])
        except (TypeError, ValueError) as exc:
            return Response({'doublons': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'survivant': rapport['survivant'].pk,
            'absorbes': rapport['absorbes'],
            'repointes': rapport['repointes'],
            'non_repointes': rapport['non_repointes'],
        })


# ── NTDATA20 — file de revue des doublons ──────────────────────────────────

class PropositionFusionSerializer(serializers.ModelSerializer):
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)
    decideur_username = serializers.CharField(
        source='decideur.username', read_only=True, default='')

    class Meta:
        model = PropositionFusion
        fields = [
            'id', 'entite', 'ids_groupe', 'empreinte', 'score', 'motifs',
            'libelles', 'statut', 'statut_label', 'decideur',
            'decideur_username', 'decide_le', 'detail_decision',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class PropositionFusionViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """NTDATA20 — la file de revue : on consulte, puis on TRANCHE.

    LECTURE SEULE côté CRUD : une proposition est produite par le détecteur,
    jamais saisie à la main. Trois actions, et trois seulement :

      * ``POST …/fusions/scanner/``           — (re)peuple la file depuis les
        détecteurs (``?entite=`` pour n'en scanner qu'une) ;
      * ``POST …/fusions/{id}/ignorer/``      — « ce ne sont pas des
        doublons » : décision DÉFINITIVE, le groupe n'est plus reproposé ;
      * ``POST …/fusions/{id}/fusionner/``    — applique la fusion supervisée
        existante (NTDATA18/19) vers le survivant choisi.

    Le ``statut`` n'est écrit que par ces actions : aucun PATCH brut ne peut
    faire passer une proposition en « fusionné » sans qu'une fusion ait eu
    lieu.
    """

    serializer_class = PropositionFusionSerializer
    permission_classes = [IsResponsableOrAdmin]
    queryset = PropositionFusion.objects.all()

    def get_queryset(self):
        qs = super().get_queryset().select_related('decideur')
        entite = self.request.query_params.get('entite')
        if entite:
            qs = qs.filter(entite=entite)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @extend_schema(
        request=None,
        responses=inline_serializer('ScanFusionsReponse', {
            'entites': serializers.JSONField(),
            'nouvelles': serializers.IntegerField(),
            'en_attente': serializers.IntegerField(),
        }))
    @action(detail=False, methods=['post'])
    def scanner(self, request):
        """Repeuple la file depuis les détecteurs (jamais de fusion)."""
        company = request.user.company
        demandee = request.query_params.get('entite')
        entites = ([demandee] if demandee
                   else sorted(services.CONSOLIDATION))
        nouvelles = 0
        scannees = []
        for entite in entites:
            try:
                creees = services.scanner_propositions(
                    company, entite, request.user)
            except ValueError as exc:
                return Response({'entite': str(exc)},
                                status=status.HTTP_400_BAD_REQUEST)
            nouvelles += len(creees)
            scannees.append({'entite': entite, 'nouvelles': len(creees)})
        return Response({
            'entites': scannees,
            'nouvelles': nouvelles,
            'en_attente': services.propositions_en_attente(company).count(),
        })

    @extend_schema(
        request=None,
        responses=PropositionFusionSerializer)
    @action(detail=True, methods=['post'])
    def ignorer(self, request, pk=None):
        """« Ce ne sont pas des doublons » — rien n'est modifié dans les fiches."""
        proposition = self.get_object()
        try:
            services.ignorer_proposition(proposition, request.user)
        except ValueError as exc:
            return Response({'statut': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(proposition).data)

    @extend_schema(
        request=inline_serializer('FusionnerPropositionRequete', {
            'survivant': serializers.IntegerField(),
        }),
        responses=PropositionFusionSerializer)
    @action(detail=True, methods=['post'])
    def fusionner(self, request, pk=None):
        """Applique la fusion supervisée vers la fiche à CONSERVER."""
        proposition = self.get_object()
        survivant = (request.data or {}).get('survivant')
        if not survivant:
            return Response({'survivant': 'Indiquez la fiche à conserver.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            services.fusionner_proposition(
                proposition, request.user, int(survivant))
        except (TypeError, ValueError) as exc:
            return Response({'survivant': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(proposition).data)


# ── NTDATA24 — consultation & rafraîchissement des golden records ──────────

class GoldenRecordSerializer(serializers.ModelSerializer):
    entite_label = serializers.CharField(
        source='get_entite_display', read_only=True)
    nb_sources = serializers.IntegerField(read_only=True)

    class Meta:
        model = GoldenRecord
        fields = [
            'id', 'entite', 'entite_label', 'cle_metier', 'source_ids',
            'nb_sources', 'attributs', 'derniere_consolidation_le',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class GoldenRecordViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """NTDATA24 — la fiche consolidée : on la LIT, on la RECALCULE, jamais plus.

    LECTURE SEULE par construction : un golden record est le RÉSULTAT d'un
    calcul sur des fiches sources ; le modifier à la main produirait une
    quatrième version de la vérité, exactement ce que la consolidation existe
    pour supprimer.

      * ``GET  …/golden-records/?entite=``      — les fiches consolidées ;
      * ``POST …/golden-records/consolider/``   — recalcule MAINTENANT
        (``?entite=`` pour n'en recalculer qu'une) au lieu d'attendre le job
        hebdomadaire ``dataquality.consolider_golden_records``.

    LA CONSOLIDATION NE MUTE AUCUNE SOURCE. Modifier un client puis
    recalculer met à jour l'attribut golden ; la fiche client, elle, n'est pas
    touchée d'un octet.
    """

    serializer_class = GoldenRecordSerializer
    permission_classes = [IsResponsableOrAdmin]
    queryset = GoldenRecord.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        entite = self.request.query_params.get('entite')
        if entite:
            qs = qs.filter(entite=entite)
        return qs

    @extend_schema(
        request=None,
        responses=inline_serializer('ConsoliderGoldenReponse', {
            'entites': serializers.JSONField(),
            'consolides': serializers.IntegerField(),
        }))
    @action(detail=False, methods=['post'])
    def consolider(self, request):
        """Recalcule les golden records à la demande (aucune source mutée)."""
        company = request.user.company
        demandee = request.query_params.get('entite')
        entites = ([demandee] if demandee
                   else sorted(services.CONSOLIDATION))
        total = 0
        detail = []
        for entite in entites:
            try:
                records = services.consolider_golden(
                    company, entite, user=request.user)
            except ValueError as exc:
                return Response({'entite': str(exc)},
                                status=status.HTTP_400_BAD_REQUEST)
            total += len(records)
            detail.append({'entite': entite, 'consolides': len(records)})
        return Response({'entites': detail, 'consolides': total})

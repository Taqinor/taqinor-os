"""Vues de conformité fiscale marocaine (Groupe NTMAR)."""
from django.db import models as django_models
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    AttestationTenant, BeneficiaireEffectif, EcheanceFiscale, ObligationFiscale,
    VeilleReglementaire,
)
from .selectors import (
    attestations_expirantes, pieces_reutilisables_attestations, registre_ubo,
    tableau_conformite,
)
from .serializers import (
    AttestationTenantSerializer, BeneficiaireEffectifSerializer,
    EcheanceFiscaleSerializer, ObligationFiscaleSerializer,
    VeilleReglementaireSerializer,
)
from .services import (
    calendrier, envoyer_rappels_fiscaux, export_declaration_ubo,
    marquer_impact_veille_traite, seed_obligations_standard,
)


class ObligationFiscaleViewSet(CompanyScopedModelViewSet):
    """CRUD des obligations fiscales récurrentes (NTMAR14)."""
    queryset = ObligationFiscale.objects.all()
    serializer_class = ObligationFiscaleSerializer
    filterset_fields = ['type_obligation', 'actif']

    def get_permissions(self):
        # NTMAR — la conformité fiscale (obligations, calendrier, rappels,
        # tableau de bord) est réservée Responsable/Directeur/Admin ;
        # company-scopée par CompanyScopedModelViewSet. Garde par action
        # (pattern d'or crm/compta, YRBAC13).
        return [IsResponsableOrAdmin()]

    @action(detail=False, methods=['post'], url_path='seed-standard')
    def seed_standard(self, request):
        """NTMAR14 — seed idempotent des obligations standard marocaines."""
        created = seed_obligations_standard(request.user.company)
        return Response(
            ObligationFiscaleSerializer(created, many=True).data)

    @action(detail=False, methods=['post'], url_path='calendrier')
    def calendrier_action(self, request):
        """NTMAR14 — matérialise le calendrier daté de l'année (idempotent).
        Corps : ``{"annee": 2026}`` (défaut : année courante)."""
        from django.utils import timezone
        annee = int(request.data.get('annee') or timezone.localdate().year)
        echeances = calendrier(request.user.company, annee)
        return Response(EcheanceFiscaleSerializer(echeances, many=True).data)

    @action(detail=False, methods=['get'], url_path='tableau-conformite')
    def tableau_conformite_action(self, request):
        """NTMAR16 — feu tricolore par obligation."""
        return Response(tableau_conformite(request.user.company))

    @action(detail=False, methods=['post'], url_path='rappels')
    def rappels_action(self, request):
        """NTMAR15 — déclenche les rappels dus (idempotent), manuel/debug —
        la commande ``manage.py rappels_fiscaux`` reste le chemin planifié."""
        notifiees = envoyer_rappels_fiscaux(request.user.company)
        return Response(
            EcheanceFiscaleSerializer(notifiees, many=True).data)


class EcheanceFiscaleViewSet(CompanyScopedModelViewSet):
    """Lecture des échéances datées (générées via ``calendrier``, NTMAR14)."""
    queryset = EcheanceFiscale.objects.select_related('obligation')
    serializer_class = EcheanceFiscaleSerializer
    http_method_names = ['get', 'head', 'options']
    filterset_fields = ['obligation', 'statut']


class AttestationTenantViewSet(CompanyScopedModelViewSet):
    """CRUD des attestations fiscales/sociales du tenant (NTMAR28)."""
    queryset = AttestationTenant.objects.all()
    serializer_class = AttestationTenantSerializer
    filterset_fields = ['type_attestation']

    def get_permissions(self):
        # NTMAR28/29 — attestations tenant réservées Responsable/Directeur/
        # Admin (company-scopé). Garde par action (pattern d'or, YRBAC13).
        return [IsResponsableOrAdmin()]

    @action(detail=False, methods=['get'], url_path='expirantes')
    def expirantes(self, request):
        """NTMAR28 — attestations expirant sous ``?within=N`` jours (défaut 30)."""
        try:
            within = int(request.query_params.get('within', 30))
        except (TypeError, ValueError):
            within = 30
        qs = attestations_expirantes(request.user.company, within=within)
        return Response(AttestationTenantSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='pieces-reutilisables')
    def pieces_reutilisables(self, request):
        """NTMAR29 — attestations valides réutilisables (source pour un
        dossier de soumission ``apps.ao`` — le pré-remplissage lui-même est
        hors périmètre de ce lot)."""
        return Response(pieces_reutilisables_attestations(request.user.company))


class BeneficiaireEffectifViewSet(CompanyScopedModelViewSet):
    """CRUD du registre UBO (NTMAR30)."""
    queryset = BeneficiaireEffectif.objects.all()
    serializer_class = BeneficiaireEffectifSerializer

    def get_permissions(self):
        # NTMAR30/31 — registre UBO réservé Responsable/Directeur/Admin
        # (company-scopé). Garde par action (pattern d'or, YRBAC13).
        return [IsResponsableOrAdmin()]

    @action(detail=False, methods=['get'], url_path='registre')
    def registre(self, request):
        """NTMAR30 — registre + alerte de complétude (Σ détention < seuil)."""
        data = registre_ubo(request.user.company)
        return Response({
            'beneficiaires': BeneficiaireEffectifSerializer(
                data['beneficiaires'], many=True).data,
            'total_pourcentage': str(data['total_pourcentage']),
            'complet': data['complet'],
        })

    @action(detail=False, methods=['get'], url_path='export-declaration')
    def export_declaration(self, request):
        """NTMAR31 — export (structure OMPIC) prêt à déposer manuellement."""
        return Response({'lignes': export_declaration_ubo(request.user.company)})


class VeilleReglementaireViewSet(CompanyScopedModelViewSet):
    """CRUD de la veille réglementaire (NTMAR32/33).

    Lecture : entrées de la société + entrées GLOBALES (``company`` NULL).
    Écriture : toujours scopée à la société de l'utilisateur (jamais une
    entrée globale créée via l'API)."""
    queryset = VeilleReglementaire.objects.all()
    serializer_class = VeilleReglementaireSerializer
    filterset_fields = ['domaine', 'statut']

    def get_queryset(self):
        company = self.request.user.company
        qs = VeilleReglementaire.objects.filter(
            django_models.Q(company=company) | django_models.Q(company__isnull=True))
        domaine = self.request.query_params.get('domaine')
        if domaine:
            qs = qs.filter(domaine=domaine)
        return qs

    def get_permissions(self):
        # NTMAR32/33 — veille réglementaire réservée Responsable/Directeur/
        # Admin (company-scopé + entrées globales en lecture seule). Garde
        # par action (pattern d'or, YRBAC13).
        return [IsResponsableOrAdmin()]

    @action(detail=True, methods=['post'], url_path='marquer-impact-traite')
    def marquer_impact_traite(self, request, pk=None):
        """NTMAR33 — marque l'impact d'une veille comme traité."""
        veille = self.get_object()
        marquer_impact_veille_traite(veille)
        return Response(VeilleReglementaireSerializer(veille).data)


@api_view(['GET'])
def tableau_conformite_view(request):
    """NTMAR16 — ``GET /api/django/fiscal/tableau-conformite/``."""
    return Response(tableau_conformite(request.user.company))

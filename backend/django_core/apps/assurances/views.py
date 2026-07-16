"""Vues du registre des assurances & sinistres d'entreprise (NTASS)."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import HasPermissionOrLegacy
from core.mixins import TenantMixin
from core.permissions import WriteScopedPermissionMixin

from .models import (
    ActifCouvert, Assureur, Courtier, EcheancePrime, GarantiePolice,
    PoliceAssurance,
)
from .serializers import (
    ActifCouvertSerializer, AssureurSerializer, CourtierSerializer,
    EcheancePrimeSerializer, GarantiePoliceSerializer,
    PoliceActivitySerializer, PoliceAssuranceSerializer,
)
from .services import (
    CHAMPS_SUIVIS_POLICE, generer_echeancier_prime, log_police_creation,
    log_police_note, log_police_transitions_auto, proposer_ecriture_prime,
)


class _AssurancesBaseViewSet(
        WriteScopedPermissionMixin, TenantMixin, viewsets.ModelViewSet):
    """Base commune : société scopée (TenantMixin) + lecture/écriture
    fine-grainées (NTASS29 — ``assurances_voir``/``assurances_gerer``).

    Comptes légacy sans rôle fin : repli historique Responsable/Administrateur
    préservé (voir ``core.permissions.WriteScopedPermissionMixin``)."""
    read_permission = 'assurances_voir'
    write_permission = 'assurances_gerer'


class AssureurViewSet(_AssurancesBaseViewSet):
    """CRUD des assureurs (compagnies d'assurance), scopé société (NTASS1)."""
    queryset = Assureur.objects.all()
    serializer_class = AssureurSerializer
    filterset_fields = ['actif']


class CourtierViewSet(_AssurancesBaseViewSet):
    """CRUD des courtiers/intermédiaires d'assurance, scopé société (NTASS1)."""
    queryset = Courtier.objects.all()
    serializer_class = CourtierSerializer
    filterset_fields = ['actif']


class PoliceAssuranceViewSet(_AssurancesBaseViewSet):
    """CRUD des polices d'assurance d'entreprise, scopé société (NTASS2)."""
    queryset = PoliceAssurance.objects.select_related('assureur', 'courtier')
    serializer_class = PoliceAssuranceSerializer
    filterset_fields = ['type_police', 'statut', 'assureur', 'courtier']

    def perform_create(self, serializer):
        try:
            super().perform_create(serializer)
        except IntegrityError:
            # Filet de course sur (company, numero_police) — la contrainte DB
            # se déclenche entre la validation serializer et l'écriture.
            raise ValidationError(
                {'numero_police':
                 'Ce numéro de police existe déjà dans votre société.'})
        log_police_creation(serializer.instance, self.request.user)

    def perform_update(self, serializer):
        # NTASS3 — capture l'état AVANT sauvegarde des champs suivis pour
        # loguer automatiquement toute transition (statut/échéance/prime).
        avant = {
            champ: getattr(serializer.instance, champ)
            for champ in CHAMPS_SUIVIS_POLICE
        }
        try:
            super().perform_update(serializer)
        except IntegrityError:
            raise ValidationError(
                {'numero_police':
                 'Ce numéro de police existe déjà dans votre société.'})
        log_police_transitions_auto(
            serializer.instance, avant, self.request.user)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """NTASS3 — timeline chatter de la police (plus récent d'abord)."""
        police = self.get_object()
        return Response(
            PoliceActivitySerializer(police.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter')
    def noter(self, request, pk=None):
        """NTASS3 — note manuelle (auteur posé côté serveur)."""
        police = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = log_police_note(police, request.user, body)
        return Response(PoliceActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='generer-echeancier')
    def generer_echeancier(self, request, pk=None):
        """NTASS5 — découpe ``prime_annuelle_ht`` en échéances datées.

        Corps : ``{"periodicite": "trimestrielle"}`` (voir
        ``EcheancePrime.Periodicite``, défaut ``annuelle``)."""
        police = self.get_object()
        periodicite = request.data.get(
            'periodicite', EcheancePrime.Periodicite.ANNUELLE)
        if periodicite not in EcheancePrime.Periodicite.values:
            return Response(
                {'periodicite': 'Périodicité invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        echeances = generer_echeancier_prime(police, periodicite)
        return Response(
            EcheancePrimeSerializer(echeances, many=True).data,
            status=status.HTTP_201_CREATED)


class EcheancePrimeViewSet(_AssurancesBaseViewSet):
    """CRUD de l'échéancier de primes, scopé société (NTASS5)."""
    queryset = EcheancePrime.objects.select_related('police')
    serializer_class = EcheancePrimeSerializer
    filterset_fields = ['police', 'statut', 'periodicite']

    @action(detail=True, methods=['post'], url_path='marquer-payee')
    def marquer_payee(self, request, pk=None):
        """NTASS5 — marque l'échéance comme payée."""
        echeance = self.get_object()
        echeance.statut = EcheancePrime.Statut.PAYEE
        echeance.save(update_fields=['statut'])
        return Response(EcheancePrimeSerializer(echeance).data)

    @action(detail=True, methods=['post'], url_path='proposer-ecriture',
            permission_classes=[HasPermissionOrLegacy(
                'assurances_proposer_ecriture')])
    def proposer_ecriture(self, request, pk=None):
        """NTASS6 — propose (brouillon) l'écriture comptable de l'échéance.

        Réservé compta/admin (``assurances_proposer_ecriture`` — NTASS29 ;
        repli légacy Responsable/Administrateur pour les comptes sans rôle
        fin, voir ``HasPermissionOrLegacy``)."""
        echeance = self.get_object()
        try:
            ecriture = proposer_ecriture_prime(echeance, user=request.user)
        except DjangoValidationError as exc:
            # Levée par compta.services (ex. période comptable verrouillée,
            # FG115) — remontée en 400 lisible plutôt qu'un 500.
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'echeance': EcheancePrimeSerializer(echeance).data,
            'ecriture_id': ecriture.id,
            'ecriture_statut': ecriture.statut,
        }, status=status.HTTP_201_CREATED)


class GarantiePoliceViewSet(_AssurancesBaseViewSet):
    """CRUD des garanties d'une police, scopé société (NTASS4).

    Endpoint imbriqué : ``?police=<id>`` filtre les garanties d'une police."""
    queryset = GarantiePolice.objects.select_related('police')
    serializer_class = GarantiePoliceSerializer
    filterset_fields = ['police']


class ActifCouvertViewSet(_AssurancesBaseViewSet):
    """CRUD des actifs couverts par une police, scopé société (NTASS7).

    Endpoint imbriqué : ``?police=<id>`` filtre les actifs d'une police."""
    queryset = ActifCouvert.objects.select_related('police')
    serializer_class = ActifCouvertSerializer
    filterset_fields = ['police', 'type_actif']

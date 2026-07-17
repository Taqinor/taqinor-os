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
    ActifCouvert, AttestationAssurance, Assureur, Courtier, DeclarationSinistre,
    EcheancePrime, ExigenceAssuranceMarche, GarantiePolice, PoliceAssurance,
)
from .serializers import (
    ActifCouvertSerializer, AttestationAssuranceSerializer, AssureurSerializer,
    CourtierSerializer, DeclarationSinistreSerializer, EcheancePrimeSerializer,
    ExigenceAssuranceMarcheSerializer, GarantiePoliceSerializer,
    IndemnisationSinistreSerializer, PoliceActivitySerializer,
    PoliceAssuranceSerializer, SinistreActivitySerializer,
)
from .selectors import attestations_expirantes, polices_expirantes
from .services import (
    CHAMPS_SUIVIS_POLICE, CHAMPS_SUIVIS_SINISTRE, enregistrer_indemnisation,
    generer_echeancier_prime, log_police_creation, log_police_note,
    log_police_transitions_auto, log_sinistre_creation, log_sinistre_note,
    log_sinistre_transitions_auto, proposer_ecriture_indemnisation,
    proposer_ecriture_prime, renouveler_police,
    verifier_conformite_assurance_marche,
)


def _detail_django_validation_error(exc):
    """Message client-lisible depuis un ``django.core.exceptions.
    ValidationError`` (dont ``str()`` renvoie un repr de liste peu lisible)."""
    return ' '.join(exc.messages) if getattr(exc, 'messages', None) else str(exc)


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

    @action(detail=False, methods=['get'], url_path='expirantes')
    def expirantes(self, request):
        """NTASS8 — Polices ACTIVES expirant sous ``?within=N`` jours (défaut
        30). Pattern ``expirantes/?within=N`` (flotte/rh)."""
        try:
            within = int(request.query_params.get('within', 30))
        except (TypeError, ValueError):
            within = 30
        qs = polices_expirantes(request.user.company, within=within)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

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

    @action(detail=True, methods=['post'], url_path='renouveler')
    def renouveler(self, request, pk=None):
        """NTASS9 — renouvelle la police (versioning léger, voir
        ``services.renouveler_police``). Corps optionnel :
        ``{"periodicite": "...", "nouveau_numero_police": "..."}``."""
        police = self.get_object()
        try:
            nouvelle = renouveler_police(
                police, user=request.user,
                periodicite=request.data.get('periodicite'),
                nouveau_numero_police=request.data.get('nouveau_numero_police'))
        except DjangoValidationError as exc:
            return Response(
                {'detail': _detail_django_validation_error(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PoliceAssuranceSerializer(nouvelle).data,
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
            return Response(
                {'detail': _detail_django_validation_error(exc)},
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


class DeclarationSinistreViewSet(_AssurancesBaseViewSet):
    """CRUD des déclarations de sinistre transverses (NTASS10).

    ``reference`` (numéro de dossier ``SIN-<année>-NNN``) est générée
    RACE-SAFE via ``core.numbering`` (jamais ``count()+1``)."""
    queryset = DeclarationSinistre.objects.select_related('police')
    serializer_class = DeclarationSinistreSerializer
    filterset_fields = ['police', 'statut', 'type_sinistre']

    def perform_create(self, serializer):
        from apps.ventes.utils.references import create_with_reference

        company = self.request.user.company
        create_with_reference(
            DeclarationSinistre, 'SIN', company,
            lambda reference: serializer.save(
                company=company, reference=reference),
            padding=3, period='yearly')
        log_sinistre_creation(serializer.instance, self.request.user)

    def perform_update(self, serializer):
        # NTASS11 — capture l'état AVANT sauvegarde des champs suivis.
        avant = {
            champ: getattr(serializer.instance, champ)
            for champ in CHAMPS_SUIVIS_SINISTRE
        }
        super().perform_update(serializer)
        log_sinistre_transitions_auto(
            serializer.instance, avant, self.request.user)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """NTASS11 — timeline chatter du sinistre (plus récent d'abord)."""
        declaration = self.get_object()
        return Response(SinistreActivitySerializer(
            declaration.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter')
    def noter(self, request, pk=None):
        """NTASS11 — note manuelle (auteur posé côté serveur)."""
        declaration = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = log_sinistre_note(declaration, request.user, body)
        return Response(SinistreActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='enregistrer-indemnisation')
    def enregistrer_indemnisation_action(self, request, pk=None):
        """NTASS12 — pose l'indemnisation (réclamé/franchise/indemnisé) et
        fait passer le sinistre à ``indemnise``. Corps : ``montant_reclame``,
        ``montant_indemnise`` (requis) ; ``franchise_appliquee``,
        ``date_versement``, ``garantie_id`` (optionnels)."""
        declaration = self.get_object()
        try:
            montant_reclame = request.data['montant_reclame']
            montant_indemnise = request.data['montant_indemnise']
        except KeyError as exc:
            return Response(
                {str(exc).strip("'"): 'Champ requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        indemnisation = enregistrer_indemnisation(
            declaration,
            montant_reclame=montant_reclame,
            montant_indemnise=montant_indemnise,
            franchise_appliquee=request.data.get('franchise_appliquee'),
            date_versement=request.data.get('date_versement'),
            garantie_id=request.data.get('garantie_id'),
            user=request.user,
        )
        return Response(
            IndemnisationSinistreSerializer(indemnisation).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'],
            url_path='proposer-ecriture-indemnisation',
            permission_classes=[HasPermissionOrLegacy(
                'assurances_proposer_ecriture')])
    def proposer_ecriture_indemnisation_action(self, request, pk=None):
        """NTASS13 — propose (brouillon) l'écriture comptable de
        l'indemnisation encaissée (débit banque / crédit produit non courant).
        Réservé compta/admin (``assurances_proposer_ecriture``, NTASS29)."""
        declaration = self.get_object()
        indemnisation = getattr(declaration, 'indemnisation', None)
        if indemnisation is None:
            return Response(
                {'detail': "Aucune indemnisation enregistrée sur ce sinistre."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ecriture = proposer_ecriture_indemnisation(
                indemnisation, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': _detail_django_validation_error(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'indemnisation': IndemnisationSinistreSerializer(indemnisation).data,
            'ecriture_id': ecriture.id,
            'ecriture_statut': ecriture.statut,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='marquer-conteste')
    def marquer_conteste(self, request, pk=None):
        """NTASS16 — marque un sinistre refusé/contesté escaladé : pose
        ``conteste=True`` (le ``statut`` reste ``refuse``), SANS créer de
        dossier contentieux — prépare seulement le terrain pour que le futur
        module NTJUR le référence en retour (``dossier_contentieux_ref``)."""
        declaration = self.get_object()
        declaration.conteste = True
        declaration.save(update_fields=['conteste'])
        log_sinistre_note(
            declaration, request.user,
            'Sinistre marqué contesté (escalade contentieux préparée).')
        return Response(
            DeclarationSinistreSerializer(declaration).data)


class AttestationAssuranceViewSet(_AssurancesBaseViewSet):
    """CRUD des attestations d'assurance que NOUS détenons (NTASS17).

    ``?police=<id>`` filtre les attestations d'une police. Accepte l'upload
    multipart du document scanné (FileField ``document``)."""
    queryset = AttestationAssurance.objects.select_related('police')
    serializer_class = AttestationAssuranceSerializer
    filterset_fields = ['police', 'statut']

    @action(detail=False, methods=['get'], url_path='expirantes')
    def expirantes(self, request):
        """NTASS18 — Attestations VALIDES expirant sous ``?within=N`` jours
        (défaut 30). Alerte DISTINCTE de l'alerte police (une police active
        peut avoir une attestation datée)."""
        try:
            within = int(request.query_params.get('within', 30))
        except (TypeError, ValueError):
            within = 30
        qs = attestations_expirantes(request.user.company, within=within)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class ExigenceAssuranceMarcheViewSet(_AssurancesBaseViewSet):
    """Checklist de conformité assurance par marché/appel d'offres (NTASS19).

    ``?marche_ref=<id>`` filtre les exigences d'un marché."""
    queryset = ExigenceAssuranceMarche.objects.all()
    serializer_class = ExigenceAssuranceMarcheSerializer
    filterset_fields = ['marche_ref', 'type_police_requis', 'statut_verification']

    @action(detail=True, methods=['post'], url_path='verifier')
    def verifier(self, request, pk=None):
        """NTASS19 — croise les polices actives de la société avec l'exigence
        et pose ``statut_verification`` (conforme / non_conforme)."""
        exigence = self.get_object()
        verifier_conformite_assurance_marche(exigence)
        return Response(
            ExigenceAssuranceMarcheSerializer(exigence).data)

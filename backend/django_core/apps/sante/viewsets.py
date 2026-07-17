"""Viewsets DRF du module ``apps.sante``.

Tous les viewsets héritent de ``core.viewsets.CompanyScopedModelViewSet`` :
queryset filtré par ``request.user.company``, ``company`` forcée côté serveur
en création (jamais lue du corps de requête). Le grain RBAC fin (nouveaux
rôles ``secretaire_medicale``/``praticien``/``caissier_sante``) est posé par
NTSAN17 — en attendant, le défaut « authentifié suffit » de
``CompanyScopedModelViewSet`` s'applique.
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.destroy_mixins import UsageGuardedDestroyMixin
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    ActeMedical, ActeRealise, Admission, Convention, FactureSante,
    GrilleTarifaire, PaiementSante, Patient, Praticien, PriseEnCharge,
    RendezVous, Salle)
from .serializers import (
    ActeMedicalSerializer, ActeRealiseSerializer, AdmissionSerializer,
    ConventionSerializer, FactureSanteSerializer, GrilleTarifaireSerializer,
    PaiementSanteSerializer, PatientSerializer, PraticienSerializer,
    PriseEnChargeSerializer, RendezVousSerializer, SalleSerializer)


class PraticienViewSet(CompanyScopedModelViewSet):
    queryset = Praticien.objects.select_related('user').all()
    serializer_class = PraticienSerializer


class SalleViewSet(CompanyScopedModelViewSet):
    queryset = Salle.objects.all()
    serializer_class = SalleSerializer


class PatientViewSet(CompanyScopedModelViewSet):
    """NTSAN3 — dossier administratif patient. ``numero_dossier`` est
    attribué côté serveur à la création (anti-collision, jamais un
    ``count()+1``)."""

    queryset = Patient.objects.select_related('client').all()
    serializer_class = PatientSerializer

    def get_queryset(self):
        """NTSAN18 — recherche accueil/réception par ``?q=`` (nom, prénom,
        CIN ou téléphone), utilisée par l'écran « Réception »."""
        qs = super().get_queryset()
        q = self.request.query_params.get('q')
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(nom__icontains=q) | Q(prenom__icontains=q) |
                Q(cin__icontains=q) | Q(telephone__icontains=q) |
                Q(whatsapp__icontains=q))
        return qs

    def perform_create(self, serializer):
        super().perform_create(serializer)
        from .services import attribuer_numero_dossier
        attribuer_numero_dossier(serializer.instance)


class RendezVousViewSet(CompanyScopedModelViewSet):
    """NTSAN4 — agenda multi-praticiens. `GET .../rendezvous/` accepte les
    filtres `praticien`, `salle`, `date_debut`, `date_fin` (calendrier). La
    création/modification refuse tout chevauchement praticien OU salle
    (NTSAN2)."""

    queryset = RendezVous.objects.select_related(
        'patient', 'praticien', 'salle').all()
    serializer_class = RendezVousSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        praticien = params.get('praticien')
        salle = params.get('salle')
        date_debut = params.get('date_debut')
        date_fin = params.get('date_fin')
        if praticien:
            qs = qs.filter(praticien_id=praticien)
        if salle:
            qs = qs.filter(salle_id=salle)
        if date_debut:
            qs = qs.filter(date_heure_debut__date__gte=date_debut)
        if date_fin:
            qs = qs.filter(date_heure_debut__date__lte=date_fin)
        return qs

    def _guard(self, *, praticien, salle, date_heure_debut, duree_min,
               exclude_id=None):
        from .services import verifier_chevauchement_rdv
        message = verifier_chevauchement_rdv(
            company=self.request.user.company, praticien=praticien,
            salle=salle, date_heure_debut=date_heure_debut,
            duree_min=duree_min, exclude_id=exclude_id)
        if message:
            raise ValidationError({'detail': message})

    def perform_create(self, serializer):
        data = serializer.validated_data
        self._guard(
            praticien=data.get('praticien'), salle=data.get('salle'),
            date_heure_debut=data['date_heure_debut'],
            duree_min=data.get('duree_min', 30))
        serializer.save(
            company=self.request.user.company,
            cree_par=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        data = serializer.validated_data
        self._guard(
            praticien=data.get('praticien', instance.praticien),
            salle=data.get('salle', instance.salle),
            date_heure_debut=data.get(
                'date_heure_debut', instance.date_heure_debut),
            duree_min=data.get('duree_min', instance.duree_min),
            exclude_id=instance.id)
        super().perform_update(serializer)


class AdmissionViewSet(CompanyScopedModelViewSet):
    """NTSAN6 — parcours administratif patient (admission → actes → sortie)."""

    queryset = Admission.objects.select_related('patient', 'praticien', 'rdv').all()
    serializer_class = AdmissionSerializer

    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        from .services import cloturer_admission

        admission = self.get_object()
        try:
            cloturer_admission(admission)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(AdmissionSerializer(admission).data)


class ActeMedicalViewSet(UsageGuardedDestroyMixin, CompanyScopedModelViewSet):
    """NTSAN7 — nomenclature des actes. Soft-disable via `desactiver`/
    `activer` (jamais un DELETE physique une fois l'acte utilisé — la garde
    de suppression est complétée dans la même passe que NTSAN10)."""

    queryset = ActeMedical.objects.all()
    serializer_class = ActeMedicalSerializer

    def destroy_guard_message(self, acte):
        """NTSAN7/NTSAN10 — un acte déjà réalisé (facturé ou non) ou déjà
        présent dans une grille tarifaire ne se supprime jamais physiquement
        (soft-disable uniquement, via `desactiver`)."""
        if acte.realisations.exists():
            return (
                "Cet acte a déjà été réalisé sur au moins un patient — il "
                "ne peut plus être supprimé, seulement désactivé.")
        if acte.grilles_tarifaires.exists():
            return (
                "Cet acte est référencé dans une grille tarifaire — il ne "
                "peut plus être supprimé, seulement désactivé.")
        return None

    @action(detail=True, methods=['post'], url_path='desactiver')
    def desactiver(self, request, pk=None):
        acte = self.get_object()
        acte.actif = False
        acte.save(update_fields=['actif'])
        return Response(ActeMedicalSerializer(acte).data)

    @action(detail=True, methods=['post'], url_path='activer')
    def activer(self, request, pk=None):
        acte = self.get_object()
        acte.actif = True
        acte.save(update_fields=['actif'])
        return Response(ActeMedicalSerializer(acte).data)


class ConventionViewSet(CompanyScopedModelViewSet):
    """NTSAN9 — liste des conventions (mutuelle/CNOPS/CNSS/cash), paramétrable
    par clinique — aucune convention codée en dur."""

    queryset = Convention.objects.all()
    serializer_class = ConventionSerializer


class GrilleTarifaireViewSet(CompanyScopedModelViewSet):
    """NTSAN8 — tarifs par convention. Consommée par la facturation
    (NTSAN13, via `selectors.tarif_applicable`)."""

    queryset = GrilleTarifaire.objects.select_related('convention', 'acte').all()
    serializer_class = GrilleTarifaireSerializer


class ActeRealiseViewSet(CompanyScopedModelViewSet):
    """NTSAN10 — actes réalisés. `tarif_applique_ttc` est TOUJOURS calculé
    côté serveur (jamais lu du corps de requête) via
    `services.realiser_acte`, snapshotté à la réalisation."""

    queryset = ActeRealise.objects.select_related(
        'admission', 'patient', 'praticien', 'acte').all()
    serializer_class = ActeRealiseSerializer

    def perform_create(self, serializer):
        from .services import realiser_acte

        data = serializer.validated_data
        instance = realiser_acte(
            admission=data['admission'],
            patient=data['patient'],
            praticien=data['praticien'],
            acte=data['acte'],
            date_realisation=data['date_realisation'],
            quantite=data.get('quantite', 1),
            facturable=data.get('facturable', True),
        )
        serializer.instance = instance


class PriseEnChargeViewSet(CompanyScopedModelViewSet):
    """NTSAN12 — prise en charge / entente préalable. Une transition vers
    refusee/expiree déclenche `services.verifier_prise_en_charge` (traçage
    chatter+audit du basculement en reste-à-charge patient total)."""

    queryset = PriseEnCharge.objects.select_related(
        'patient', 'convention', 'admission').all()
    serializer_class = PriseEnChargeSerializer

    def perform_update(self, serializer):
        ancien_statut = serializer.instance.statut
        super().perform_update(serializer)
        instance = serializer.instance
        if instance.statut != ancien_statut:
            from .services import verifier_prise_en_charge
            verifier_prise_en_charge(instance, user=self.request.user)


class FactureSanteViewSet(CompanyScopedModelViewSet):
    """NTSAN13 — facturation patient/tiers payant. La création agrège des
    `ActeRealise` existants (jamais de lignes libres) : `POST` attend
    `{"admission": <id>, "actes_realises": [<id>, ...], "convention": <id?>,
    "remise_ttc": <decimal?>}`. Le split tiers payant/patient est TOUJOURS
    calculé côté serveur (`services.creer_facture_sante`)."""

    queryset = FactureSante.objects.select_related(
        'patient', 'admission', 'convention').all()
    serializer_class = FactureSanteSerializer

    def create(self, request, *args, **kwargs):
        from .services import creer_facture_sante

        company = request.user.company
        admission = Admission.objects.filter(
            company=company, pk=request.data.get('admission')).first()
        if admission is None:
            raise ValidationError({'admission': 'Admission introuvable.'})

        acte_ids = request.data.get('actes_realises') or []
        actes = list(ActeRealise.objects.filter(
            company=company, admission=admission, pk__in=acte_ids,
            facture_sante__isnull=True))
        if not actes:
            raise ValidationError(
                {'actes_realises': 'Aucun acte réalisé facturable trouvé.'})

        convention = None
        convention_id = request.data.get('convention')
        if convention_id:
            convention = Convention.objects.filter(
                company=company, pk=convention_id).first()

        facture = creer_facture_sante(
            admission=admission, actes_realises=actes, convention=convention,
            remise_ttc=request.data.get('remise_ttc'))
        return Response(
            FactureSanteSerializer(facture).data,
            status=status.HTTP_201_CREATED)


class PaiementSanteViewSet(CompanyScopedModelViewSet):
    """NTSAN15 — encaissement. `montant`/`facture_sante` viennent du corps de
    requête ; `encaisse_par` est TOUJOURS posé côté serveur (jamais lu du
    corps). Le statut de la facture est recalculé (`services.
    enregistrer_paiement`) après chaque paiement partiel/total."""

    queryset = PaiementSante.objects.select_related('facture_sante').all()
    serializer_class = PaiementSanteSerializer

    def perform_create(self, serializer):
        from .services import enregistrer_paiement

        data = serializer.validated_data
        instance = enregistrer_paiement(
            facture_sante=data['facture_sante'],
            montant=data['montant'],
            mode=data.get('mode', PaiementSante.Mode.ESPECES),
            date_paiement=data['date_paiement'],
            encaisse_par=self.request.user,
        )
        serializer.instance = instance

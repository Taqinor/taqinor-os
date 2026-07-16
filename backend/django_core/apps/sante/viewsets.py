"""Viewsets DRF du module ``apps.sante``.

Tous les viewsets héritent de ``core.viewsets.CompanyScopedModelViewSet`` :
queryset filtré par ``request.user.company``, ``company`` forcée côté serveur
en création (jamais lue du corps de requête). Le grain RBAC fin (nouveaux
rôles ``secretaire_medicale``/``praticien``/``caissier_sante``) est posé par
NTSAN17 — en attendant, le défaut « authentifié suffit » de
``CompanyScopedModelViewSet`` s'applique.
"""
from rest_framework.exceptions import ValidationError

from core.viewsets import CompanyScopedModelViewSet

from .models import Patient, Praticien, RendezVous, Salle
from .serializers import (
    PatientSerializer, PraticienSerializer, RendezVousSerializer,
    SalleSerializer)


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

"""CADV33 — registre des expériences de cadence : API ``crm/experiences-cadence/``.

Forme servie : ``contract_samples/experiences_cadence.json`` (CADV96). Liste
triée par date, bornée à ``request.user.company`` (``company`` forcée côté
serveur par ``TenantMixin``, jamais lue du corps). Lecture : ``crm_voir`` ;
écriture (POST/PATCH) : responsable ou admin. Aucune suppression : un
registre de repères ne s'efface pas. ``resultat`` se renseigne par PATCH à la
date de lecture ; ``date_lecture`` avant ``date`` est refusée (409 nommant le
champ). Lu par la courbe de cohorte (CADV110).
"""
from rest_framework import serializers

from authentication.permissions import (
    HasPermissionOrLegacy, IsResponsableOrAdmin,
)
from core.viewsets import CompanyScopedModelViewSet

from core.conflit_etat import ConflitEtat

from .models_cadence import ExperienceCadence


class ExperienceCadenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperienceCadence
        fields = ['id', 'date', 'changement', 'metrique', 'effet_attendu',
                  'date_lecture', 'resultat']
        read_only_fields = ['id']

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        date = attrs.get('date', getattr(instance, 'date', None))
        lecture = attrs.get('date_lecture',
                            getattr(instance, 'date_lecture', None))
        if date and lecture and lecture < date:
            # ENF11 : règle liant deux champs, que le schéma ne peut pas dire.
            raise ConflitEtat({
                'date_lecture': ['La date de lecture ne peut pas précéder la '
                                 'date du changement.']})
        return attrs


class ExperienceCadenceViewSet(CompanyScopedModelViewSet):
    queryset = ExperienceCadence.objects.all().order_by('date', 'id')
    serializer_class = ExperienceCadenceSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [HasPermissionOrLegacy('crm_voir')()]
        return [IsResponsableOrAdmin()]

"""Sérialiseurs des Ressources humaines.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import Departement, DossierEmploye


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class DepartementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departement
        fields = ['id', 'nom', 'code', 'actif', 'date_creation']
        read_only_fields = ['date_creation']


class DossierEmployeSerializer(serializers.ModelSerializer):
    type_contrat_display = serializers.CharField(
        source='get_type_contrat_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = DossierEmploye
        fields = [
            'id', 'user', 'matricule', 'nom', 'prenom', 'cin', 'telephone',
            'email', 'poste', 'departement', 'date_embauche', 'type_contrat',
            'type_contrat_display', 'contrat_date_debut', 'contrat_date_fin',
            'statut', 'statut_display', 'cout_horaire',
            'rib', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_departement(self, value):
        return _meme_societe(self, value, 'Département')

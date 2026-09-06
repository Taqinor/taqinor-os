from rest_framework import serializers

from .models import Territoire, TerritoireMembre, TerritoireRegle


def _valider_meme_societe(value, request, label):
    """AUD814 — refuse une FK (``territoire``/``utilisateur``) qui n'appartient
    pas à la société de l'appelant. Sans ce garde-fou, un Responsable de
    société A pouvait POSTer un membre avec un territoire de société B (201
    accepté), et ``territoires.services._rotate_member`` assignait ensuite des
    leads de B à un commercial de A sans jamais revérifier la société. Un appel
    hors requête (services/seeds/tests) ou un superuser sans société ne sont
    pas concernés — même politique que
    ``apps/parametres/serializers_company.py``."""
    if request is None:
        return value
    user = getattr(request, 'user', None)
    company_id = getattr(user, 'company_id', None)
    if company_id and value is not None and value.company_id != company_id:
        raise serializers.ValidationError(f'{label} inconnu.')
    return value


class TerritoireRegleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TerritoireRegle
        fields = ['id', 'territoire', 'ordre', 'condition', 'actif']

    def validate_territoire(self, value):
        return _valider_meme_societe(
            value, self.context.get('request'), 'Territoire')


class TerritoireMembreSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.CharField(
        source='utilisateur.username', read_only=True)

    class Meta:
        model = TerritoireMembre
        fields = [
            'id', 'territoire', 'utilisateur', 'utilisateur_nom', 'quota_pct',
            'nb_assignations', 'dernier_assigne_at', 'actif',
        ]
        read_only_fields = ['nb_assignations', 'dernier_assigne_at']

    def validate_territoire(self, value):
        return _valider_meme_societe(
            value, self.context.get('request'), 'Territoire')

    def validate_utilisateur(self, value):
        return _valider_meme_societe(
            value, self.context.get('request'), 'Utilisateur')


class TerritoireSerializer(serializers.ModelSerializer):
    type_territoire_display = serializers.CharField(
        source='get_type_territoire_display', read_only=True)
    regles = TerritoireRegleSerializer(many=True, read_only=True)
    membres = TerritoireMembreSerializer(many=True, read_only=True)

    class Meta:
        model = Territoire
        fields = [
            'id', 'nom', 'type_territoire', 'type_territoire_display',
            'criteres', 'actif', 'date_creation', 'regles', 'membres',
        ]
        read_only_fields = ['date_creation']

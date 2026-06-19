"""Sérialiseur des modèles de documents éditables — D2/N60/N67/N26/N59.

Expose les portions de texte éditables du devis. ``company``, ``version`` et
``date_modification`` sont posés/gérés CÔTÉ SERVEUR — jamais lus du corps de la
requête. Les champs vides → repli moteur sur le littéral historique (le PDF reste
byte-identique tant que rien n'est édité)."""
from rest_framework import serializers

from .models_documents import DocumentTemplates


class DocumentTemplatesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplates
        fields = [
            'validite_badge_p1',
            'validite_onepage',
            'cgv_titre',
            'cgv_bullets',
            'garantie_titre',
            'garantie_detail',
            'garantie_perf_label',
            'bpa_titre',
            'bpa_mention',
            'acceptance_stamp',
            'version',
            'date_modification',
        ]
        # version/date posés serveur ; company jamais exposée ni acceptée.
        read_only_fields = ['version', 'date_modification']

    def validate_cgv_bullets(self, value):
        """Liste de chaînes (puces CGV) ou NULL. Refuse tout autre type."""
        if value in (None, ''):
            return None
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'Les puces des conditions générales doivent être une liste.')
        return [str(x) for x in value]

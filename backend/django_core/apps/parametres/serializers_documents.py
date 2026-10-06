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
            'cgv_par_mode',
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

    #: CIQ218 — les deux modes C&I qui portent leurs propres conditions.
    MODES_CGV_CI = ('commercial', 'industriel')

    def validate_cgv_par_mode(self, value):
        """CIQ218 — ``{commercial|industriel: {titre, bullets[]}}`` ou vide.
        Refuse un autre mode ou une forme inattendue (message français)."""
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Les conditions générales par mode doivent être un objet '
                '{commercial: {titre, bullets}, industriel: {…}}.')
        propre = {}
        for mode, variante in value.items():
            if mode not in self.MODES_CGV_CI:
                raise serializers.ValidationError(
                    f'Mode « {mode} » inconnu : seuls commercial et '
                    'industriel portent des conditions générales C&I.')
            if variante in (None, ''):
                continue
            if not isinstance(variante, dict) or not isinstance(
                    variante.get('bullets', []), list):
                raise serializers.ValidationError(
                    f'cgv_par_mode.{mode} : attendu {{titre, bullets: [...]}}.')
            puces = [str(x) for x in variante.get('bullets') or []
                     if str(x or '').strip()]
            titre = str(variante.get('titre') or '').strip()
            if puces or titre:
                propre[mode] = {'titre': titre, 'bullets': puces}
        return propre

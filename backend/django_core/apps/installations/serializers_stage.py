"""CH5 — Sérialiseur de configuration des étapes/gates de chantier (StageModele).

Édition réservée au Directeur (cf. la vue). Le sérialiseur expose l'ordre, le
drapeau bloquant, les exigences (`exige_*`) et le statut hérité mappé ; `cle`
et `protege` sont posés/verrouillés côté serveur pour les étapes système.
"""
from rest_framework import serializers

from .models import StageModele


def valider_unicite_societe(serializer, champ, valeur, message, **portee):
    """ACHT76 — unicité PAR SOCIÉTÉ d'un champ de référentiel (clé, type, nom)
    avant l'écriture : 400 en français sous le champ au lieu d'un 500
    (``IntegrityError`` — la société, posée côté serveur, n'est pas parmi les
    champs du sérialiseur, donc DRF ne génère aucun ``UniqueTogetherValidator``).
    Un PATCH qui garde sa propre valeur reste accepté (instance exclue)."""
    request = serializer.context.get('request')
    company = getattr(getattr(request, 'user', None), 'company', None)
    if company is None:
        return valeur
    qs = serializer.Meta.model.objects.filter(
        company=company, **{champ: valeur}, **portee)
    if serializer.instance is not None:
        qs = qs.exclude(pk=serializer.instance.pk)
    if qs.exists():
        raise serializers.ValidationError(message)
    return valeur


class StageModeleSerializer(serializers.ModelSerializer):
    statut_legacy_display = serializers.CharField(
        source='get_statut_legacy_display', read_only=True, default=None)

    class Meta:
        model = StageModele
        fields = [
            'id', 'cle', 'libelle', 'ordre', 'bloquant',
            'exige_checklist', 'exige_photos', 'exige_series', 'exige_tests',
            'exige_materiel', 'exige_dossier', 'exige_pack',
            # CIQ623 — documents de sécurité chantier.
            'exige_hse',
            # CHT23 — exigences de comptage configurables (additif, défauts =
            # comportement historique octet pour octet).
            'photos_min', 'checklist_pct_min',
            'statut_legacy', 'statut_legacy_display', 'actif', 'protege',
        ]
        # `protege` est un verrou système : jamais modifiable via l'API.
        read_only_fields = ['protege']

    def validate_cle(self, value):
        # La clé d'une étape SYSTÈME (protégée) est stable — on ne la renomme
        # pas (elle porte le mapping des effets de bord). Les étapes créées par
        # le Directeur gardent leur clé libre.
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise serializers.ValidationError(
                "La clé d'une étape système ne peut pas être modifiée.")
        return valider_unicite_societe(
            self, 'cle', value, "Cette clé d'étape existe déjà.")

"""NTMOB1 — sérialiseurs du journal hors-ligne (lecture seule).

NTMOB2 ajoute le DÉTAIL du conflit et son arbitrage (toujours en lecture), plus
un sérialiseur d'ENTRÉE dédié à la décision humaine (`ResolutionConflitSerializer`).
"""
from rest_framework import serializers

from . import services
from .models import OfflineOperation


class OfflineOperationSerializer(serializers.ModelSerializer):
    """Journal en LECTURE SEULE : une opération n'est jamais créée par ce
    sérialiseur — elle naît du lot de synchro, société posée serveur."""

    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    module_libelle = serializers.CharField(
        source='get_module_display', read_only=True)
    # NTMOB2 — libellé de l'arbitrage ('' tant qu'aucun n'a eu lieu : le champ
    # est facultatif, ``get_resolution_display`` rend alors la chaîne vide).
    resolution_libelle = serializers.CharField(
        source='get_resolution_display', read_only=True)

    class Meta:
        model = OfflineOperation
        fields = [
            'id', 'module', 'module_libelle', 'op_type', 'client_op_id',
            'statut', 'statut_libelle', 'payload', 'resultat', 'erreur',
            'date_creation', 'date_traitement', 'created_at', 'updated_at',
            # NTMOB2 — de quoi afficher le conflit et son arbitrage.
            'conflit', 'resolution', 'resolution_libelle', 'date_resolution',
        ]
        read_only_fields = fields


class ResolutionConflitSerializer(serializers.Serializer):
    """NTMOB2 — la DÉCISION humaine sur un conflit (entrée du point d'arbitrage).

    `choix` : ``mienne`` | ``serveur`` | ``fusion``. `payload` n'est lu que pour
    une fusion — c'est le corps recomposé à la main, et il est alors OBLIGATOIRE
    (une « fusion » sans corps fusionné écraserait en aveugle)."""

    choix = serializers.ChoiceField(choices=services.CHOIX_CONFLIT)
    payload = serializers.DictField(required=False)

    def validate(self, attrs):
        if attrs['choix'] == 'fusion' and not attrs.get('payload'):
            raise serializers.ValidationError(
                {'payload': 'Une fusion manuelle exige un corps fusionné.'})
        return attrs

"""Revue chantier 26/10/2026 — champs GPS de ``InterventionSerializer``.

Suivi de position AUTOMATIQUE pendant la session d'intervention (loi 09-08 /
délibération CNDP 17-2014) : l'écran « Ma journée » lit sur chaque
intervention si le suivi s'applique (``gps_tracking_required`` : en route /
sur site, non annulée) et où en est le consentement de SON technicien
(``gps_consentement`` : ``absent`` | ``a_accepter`` | ``actif`` |
``revoque``). Lecture seule — jamais posés par le client.

Fichier frère de ``serializers.py`` (mur ≥ 2 000 lignes : il ne grossit pas).
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

#: Valeurs possibles de ``gps_consentement`` (cf. ``GpsConsentRecord.statut``).
STATUTS_CONSENTEMENT_GPS = ['absent', 'a_accepter', 'actif', 'revoque']


class InterventionGpsChampsMixin(serializers.Serializer):
    """Champs GPS en lecture seule, sans N+1 : la carte {technicien: statut}
    de la société est chargée UNE fois par passe de sérialisation et gardée
    dans le contexte (même patron que ``InterventionSerializer._shotlist``) —
    kanban, calendrier et « Ma tournée » ne tirent qu'une requête."""
    gps_tracking_required = serializers.BooleanField(read_only=True)
    gps_consentement = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ChoiceField(choices=STATUTS_CONSENTEMENT_GPS))
    def get_gps_consentement(self, obj):
        if not obj.technicien_id:
            return 'absent'
        cache = self.context.get('_gps_consentements_cache')
        if cache is None:
            cache = self.context['_gps_consentements_cache'] = {}
        if obj.company_id not in cache:
            from .gps_tracking_service import statuts_consentement
            cache[obj.company_id] = statuts_consentement(obj.company_id)
        return cache[obj.company_id].get(obj.technicien_id, 'absent')

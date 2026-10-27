"""Revue chantier 26/10/2026 — champs GPS de ``InterventionSerializer``.

Suivi de position AUTOMATIQUE pendant la session d'intervention (loi 09-08 /
délibération CNDP 17-2014) : l'écran « Ma journée » lit sur chaque
intervention si le suivi s'applique (``gps_tracking_required`` : en route /
sur site, non annulée) et où en est le consentement de SON technicien
(``gps_consentement`` : ``absent`` | ``a_accepter`` | ``actif`` |
``revoque``). Lecture seule — jamais posés par le client.

Fichier frère de ``serializers.py`` (mur ≥ 2 000 lignes : il ne grossit pas).

Fondateur 27/10/2026 — ``gps_suivi_interrompu_depuis_min`` (intervention) et
``suivi_interrompu_depuis_min`` (alerte ``interruption``) : minutes de silence
du suivi pendant la session en cours, ``null`` hors session ou sans
interruption. Carte calculée UNE fois par passe et par société
(``gps_tracking_service.interruptions_suivi``), gardée dans le contexte.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

#: Valeurs possibles de ``gps_consentement`` (cf. ``GpsConsentRecord.statut``).
STATUTS_CONSENTEMENT_GPS = ['absent', 'a_accepter', 'actif', 'revoque']


def _cache_contexte(serializer, cle, company_id, calcul):
    """Valeur par société gardée dans le contexte de sérialisation (une seule
    évaluation de ``calcul(company_id)`` pour toute une liste)."""
    cache = serializer.context.get(cle)
    if cache is None:
        cache = serializer.context[cle] = {}
    if company_id not in cache:
        cache[company_id] = calcul(company_id)
    return cache[company_id]


def _statuts_consentement(serializer, company_id):
    from .gps_tracking_service import statuts_consentement
    return _cache_contexte(
        serializer, '_gps_consentements_cache', company_id, statuts_consentement)


def _interruptions(serializer, company_id):
    """{intervention_id: {..., 'depuis_min'}} — réutilise la carte des
    consentements déjà en cache (aucune requête de plus sur cette table)."""
    from .gps_tracking_service import interruptions_suivi
    return _cache_contexte(
        serializer, '_gps_interruptions_cache', company_id,
        lambda cid: interruptions_suivi(cid, statuts=_statuts_consentement(serializer, cid)))


class InterventionGpsChampsMixin(serializers.Serializer):
    """Champs GPS en lecture seule, sans N+1 : la carte {technicien: statut}
    de la société est chargée UNE fois par passe de sérialisation et gardée
    dans le contexte (même patron que ``InterventionSerializer._shotlist``) —
    kanban, calendrier et « Ma tournée » ne tirent qu'une requête."""
    gps_tracking_required = serializers.BooleanField(read_only=True)
    gps_consentement = serializers.SerializerMethodField()
    gps_suivi_interrompu_depuis_min = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ChoiceField(choices=STATUTS_CONSENTEMENT_GPS))
    def get_gps_consentement(self, obj):
        if not obj.technicien_id:
            return 'absent'
        return _statuts_consentement(self, obj.company_id).get(obj.technicien_id, 'absent')

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_gps_suivi_interrompu_depuis_min(self, obj):
        # Hors session (ou sans accord) : aucune requête, ``null``.
        if not obj.gps_tracking_required or self.get_gps_consentement(obj) != 'actif':
            return None
        info = _interruptions(self, obj.company_id).get(obj.id)
        return info['depuis_min'] if info else None


class GeofenceAlertGpsChampsMixin(serializers.Serializer):
    """Alerte ``interruption`` encore en cours (même épisode de silence) :
    minutes depuis le dernier instant connu ; ``null`` sinon."""
    suivi_interrompu_depuis_min = serializers.SerializerMethodField()

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_suivi_interrompu_depuis_min(self, obj):
        if obj.type_franchissement != 'interruption' or obj.captured_at is None:
            return None
        info = _interruptions(self, obj.company_id).get(obj.intervention_id)
        if info is None or obj.captured_at < info['dernier_releve']:
            return None
        return info['depuis_min']

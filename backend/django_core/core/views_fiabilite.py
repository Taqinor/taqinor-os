"""NTOBS21 — API des réglages « Fiabilité » d'une société.

  GET   /api/django/core/fiabilite/reglages/  → réglages de la société
  PATCH /api/django/core/fiabilite/reglages/  → modification champ par champ

SINGLETON par société : la ligne ``core.ReliabilitySettings`` est résolue
depuis ``request.user.company`` (jamais depuis l'URL ni le corps — aucune
fuite inter-société possible) et créée aux défauts à la première lecture.
D'où une vue de DÉTAIL sans identifiant plutôt qu'un ModelViewSet (même
patron que ``apps.uxviews.UxParametresView``).

Permissions (NTOBS22) : lecture ``fiabilite_voir`` OU
``fiabilite_administration`` ; écriture ``fiabilite_administration`` ;
Directeur/Administrateur gardent toujours l'accès (``FiabilitePermission``).

Module séparé de ``core/views.py`` (fichier ≥ 2 000 lignes qui ne grossit
plus). ``core`` reste fondation : aucun import d'app métier.
"""
from rest_framework import generics, serializers
from rest_framework.exceptions import NotFound
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated

from .champs_stricts import ChaineStricte, ChampsStrictsMixin
from .maintenance_windows import FiabilitePermission
from .models import ReliabilitySettings


class ReliabilitySettingsSerializer(ChampsStrictsMixin, serializers.ModelSerializer):
    """Les quatre réglages ; ``company`` n'est jamais exposée ni acceptée.
    Booléens et texte STRICTS (un ``0`` pour un booléen → 400, api-fuzz)."""

    notifier_incident_region = ChaineStricte(
        required=False, allow_blank=True, allow_null=True, max_length=100)

    class Meta:
        model = ReliabilitySettings
        fields = [
            'notifier_maintenance_email',
            'notifier_quota_email',
            'notifier_incident_region',
            'afficher_badge_sla_dashboard',
            'updated_at',
        ]
        read_only_fields = ['updated_at']

    def validate_notifier_incident_region(self, value):
        # Vide ou absent = « toutes les régions » : stocké '' (jamais None),
        # pour un seul test « filtre posé ? » côté lecteurs.
        return (value or '').strip()


class ReliabilitySettingsView(generics.RetrieveUpdateAPIView):
    """GET/PATCH des réglages Fiabilité de la société de l'appelant."""

    serializer_class = ReliabilitySettingsSerializer
    permission_classes = [IsAuthenticated, FiabilitePermission]
    parser_classes = [JSONParser]
    # Pas de PUT : un remplacement complet réinitialiserait les autres champs.
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        company = getattr(self.request.user, 'company', None)
        if company is None:
            # Compte sans société (opérateur plateforme) : rien à régler.
            raise NotFound('Aucune société rattachée à ce compte.')
        reglages, _ = ReliabilitySettings.objects.get_or_create(
            company=company)
        return reglages

    def perform_update(self, serializer):
        # La société est TOUJOURS celle de l'appelant — jamais lue du corps.
        serializer.save(company=self.request.user.company)

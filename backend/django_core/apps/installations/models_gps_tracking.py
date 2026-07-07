"""
XFSM23 — Géolocalisation temps réel + géofencing techniciens (ENFORCED).

Décision fondateur (remplace le libellé « opt-in » du plan initial) : le
consentement des employés est DÉJÀ acquis en amont (processus RH hors OS) — ce
module n'est donc PAS un interrupteur que le technicien peut désactiver. Trois
pièces :

  * ``GpsConsentRecord`` — la trace DURABLE du consentement déjà obtenu par
    employé (établie une fois, jamais reposée par le client mobile).
  * ``PositionTechnicien`` — les positions live persistées (rétention COURTE,
    cf. ``purge_positions_expirees``), liées à l'intervention active quand il y
    en a une.
  * ``GeofenceAlert`` — le drapeau/journal levé quand une position live sort du
    rayon attendu du chantier pendant une intervention active.

Le caractère « obligatoire pendant une intervention active » est modélisé côté
serveur par ``Intervention.gps_tracking_required`` (propriété calculée sur le
statut F3 — JAMAIS un champ que le client peut poser) : tant que le statut est
dans la plage active (à préparer confirmé/prête → en route → sur site), le
tracking reste requis ; il retombe à faux dès que l'intervention est
terminée/validée/annulée. Rien ici ne touche la state machine F3 elle-même
(``Intervention.STATUT_ORDER`` reste intact) — c'est une lecture, pas une
mutation.

Additif — company-scopée, posée côté serveur ; aucune migration destructive.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from .models_intervention import Intervention

# Statuts F3 pendant lesquels le suivi GPS live est OBLIGATOIRE (chantier en
# cours de réalisation terrain). Volontairement exclut À_PREPARER (le
# technicien n'est pas encore en mission) et TERMINEE/VALIDEE (mission close).
GPS_TRACKING_REQUIRED_STATUTS = (
    Intervention.Statut.PRETE,
    Intervention.Statut.EN_ROUTE,
    Intervention.Statut.SUR_SITE,
)

# Rayon (km) par défaut au-delà duquel une position live pendant une
# intervention active déclenche une alerte géofence. Paramétrable par appel
# (cf. ``services.enregistrer_position``) — cette constante est juste le défaut.
DEFAULT_GEOFENCE_RADIUS_KM = 0.5

# XFSM23 — rétention des positions live : purge des traces plus vieilles que ce
# nombre de jours (donnée personnelle sensible, loi 09-08 — pas de conservation
# longue). Purge exécutée par ``services.purge_positions_expirees`` (tâche/
# commande manuelle ; pas de Celery beat ajouté ici — hors scope de ce lot).
POSITION_RETENTION_JOURS = 30


class GpsConsentRecord(models.Model):
    """Trace DURABLE du consentement GPS déjà obtenu par employé (loi 09-08).

    Établi UNE FOIS (processus RH/onboarding, hors de ce module) ; ce modèle ne
    fait qu'enregistrer le fait, il ne pilote AUCUN interrupteur côté
    technicien — voir la note de module ci-dessus. ``revoked_at`` existe pour
    l'audit (fin de contrat, retrait légal) mais n'est jamais posé par le
    client mobile ; seule une action responsable/admin peut révoquer."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='gps_consent_records')
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='gps_consent_records')
    # Référence externe au support de consentement (ex. n° de document RH
    # signé, id d'un formulaire) — texte libre, jamais interprété ici.
    consent_ref = models.CharField(max_length=120, blank=True, null=True)
    consent_recorded_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='gps_consents_enregistres')
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Consentement GPS technicien'
        verbose_name_plural = 'Consentements GPS technicien'
        ordering = ['-consent_recorded_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'technicien'],
                condition=models.Q(revoked_at__isnull=True),
                name='uniq_gps_consent_actif'),
        ]
        indexes = [
            models.Index(fields=['company', 'technicien']),
        ]

    def __str__(self):
        return f'Consentement GPS · {self.technicien_id}'

    @property
    def is_active(self):
        return self.revoked_at is None


class PositionTechnicien(models.Model):
    """Position GPS live d'un technicien (ping périodique du client mobile).

    ``intervention`` est nullable : une position peut être capturée pendant les
    heures de service SANS intervention active (selon la politique société),
    mais le caractère OBLIGATOIRE (``gps_tracking_required``) ne s'applique
    qu'à une intervention active. Rétention courte : ``services.
    purge_positions_expirees`` supprime les lignes plus vieilles que
    ``POSITION_RETENTION_JOURS`` — aucune conservation indéfinie."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='positions_techniciens')
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='positions_gps')
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, null=True, blank=True,
        related_name='positions_gps')
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_m = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Précision GPS rapportée par le client (mètres), si fournie.")
    captured_at = models.DateTimeField(default=timezone.now)
    # Distance (km) au chantier au moment du ping, si une intervention est liée
    # et que le chantier a un GPS renseigné. Dénormalisée pour éviter un
    # recalcul haversine à chaque lecture de l'historique.
    distance_site_km = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True)
    hors_perimetre = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Position technicien'
        verbose_name_plural = 'Positions techniciens'
        ordering = ['-captured_at']
        indexes = [
            models.Index(fields=['company', 'technicien', '-captured_at']),
            models.Index(fields=['intervention', '-captured_at']),
        ]

    def __str__(self):
        return f'Position · {self.technicien_id} @ {self.captured_at:%Y-%m-%d %H:%M}'


class GeofenceAlert(models.Model):
    """Alerte/journal quand une position live sort du rayon attendu du
    chantier pendant une intervention active (géofencing). Une ligne par
    dépassement détecté — pas de déduplication : l'historique complet sert de
    preuve d'audit. Additif, company-scopée."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='geofence_alerts')
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='geofence_alerts')
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='geofence_alerts')
    position = models.ForeignKey(
        PositionTechnicien, on_delete=models.CASCADE,
        related_name='geofence_alerts')
    distance_site_km = models.DecimalField(max_digits=8, decimal_places=3)
    rayon_attendu_km = models.DecimalField(max_digits=8, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)
    acquittee = models.BooleanField(default=False)
    acquittee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='geofence_alerts_acquittees')
    acquittee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Alerte géofence'
        verbose_name_plural = 'Alertes géofence'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'intervention', '-created_at']),
        ]

    def __str__(self):
        return (f'Géofence · intervention {self.intervention_id} '
                f'({self.distance_site_km} km)')

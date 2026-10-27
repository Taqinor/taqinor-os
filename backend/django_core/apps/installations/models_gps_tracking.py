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
dans la plage active (en route → sur site — « prête » retirée le 26/10/2026),
le tracking reste requis ; il retombe à faux dès que l'intervention est
terminée/validée/annulée. Rien ici ne touche la state machine F3 elle-même
(``Intervention.STATUT_ORDER`` reste intact) — c'est une lecture, pas une
mutation.

Additif — company-scopée, posée côté serveur ; aucune migration destructive.

Revue chantier du 26/10/2026 — cadre légal (loi 09-08, délibération CNDP
17-2014) : le suivi reste AUTOMATIQUE pendant la session d'intervention (aucun
interrupteur par session), mais il n'est jamais caché. Avant le premier ping,
le technicien lit dans l'application la notice d'information
(``NOTICE_GEOLOC_V1`` : responsable du traitement, finalités, données,
destinataires, durée de conservation, droits, n° de récépissé CNDP) et en
accuse réception UNE FOIS (``GpsConsentRecord.accepte_le``). Le suivi n'a lieu
que pendant le temps de travail effectif (en route / sur site) ; un bandeau
visible le rappelle sur « Ma journée » ; le technicien consulte ses propres
positions (droit d'accès, art. 7).

Décision fondateur 27/10/2026 — les techniciens sont des PRESTATAIRES
externes : le suivi est OBLIGATOIRE et INÉVITABLE, jamais caché. L'accord
aux conditions d'utilisation (notice v2) conditionne l'accès aux missions :
un consentement en attente est créé à la première ouverture de « Ma
journée » (``consent_ref='conditions-app'``), le départ dépôt / check-in est
refusé (403) tant que l'accord manque, un indicateur discret remplace le
bandeau, et un silence de plus de 15 min pendant une session lève une
alerte ``interruption`` notifiée au responsable.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from .models_intervention import Intervention

# Statuts F3 pendant lesquels le suivi GPS live est OBLIGATOIRE : le temps de
# travail TERRAIN effectif (trajet + présence sur site). Revue chantier
# 26/10/2026 — « Prête » en est retirée : une intervention prête n'est pas
# encore une mission en cours (le technicien peut être chez lui), et la CNDP
# borne le suivi au temps de travail effectif. À_PREPARER et TERMINEE/VALIDEE
# restent exclus.
GPS_TRACKING_REQUIRED_STATUTS = (
    Intervention.Statut.EN_ROUTE,
    Intervention.Statut.SUR_SITE,
)

# Rayon (km) par défaut au-delà duquel une position live pendant une
# intervention active déclenche une alerte géofence — repli quand le chantier
# n'a pas de rayon propre (``Installation.geofence_rayon_m``).
DEFAULT_GEOFENCE_RADIUS_KM = 0.5

# XFSM23 — rétention des positions live : purge des traces plus vieilles que ce
# nombre de jours (donnée personnelle sensible, loi 09-08 — pas de conservation
# longue). Purge quotidienne par la tâche Celery beat
# ``installations.purger_positions_gps`` (``tasks.py``). Les alertes de
# franchissement (``GeofenceAlert``) survivent à la purge (``position`` passe à
# NULL) : l'historique de présence reste lisible.
POSITION_RETENTION_JOURS = 30

# Version courante de la notice d'information géolocalisation. Fondateur
# 27/10/2026 — v2 : les techniciens sont des PRESTATAIRES externes qui
# utilisent l'application de la société ; l'acceptation de ces conditions
# (géolocalisation comprise) conditionne l'accès aux missions.
NOTICE_GEOLOC_VERSION = 'v2'

#: Libellé affiché tant que la société n'a pas saisi son n° de récépissé CNDP.
RECEPISSE_NON_DECLARE = 'non encore déclaré'

#: Référence posée sur le consentement créé à la première ouverture de
#: « Ma journée » par un utilisateur terrain (en attente de son accord).
CONSENT_REF_CONDITIONS_APP = 'conditions-app'

#: Notice d'information (loi 09-08 art. 5 ; délibération CNDP 17-2014 sur la
#: géolocalisation). Montrée au technicien AVANT tout suivi ; son accord est
#: horodaté sur ``GpsConsentRecord``. Le n° de récépissé est celui du dossier
#: de la société (``recepisse_cndp``), « non encore déclaré » tant qu'il est
#: vide — jamais un numéro inventé.
NOTICE_GEOLOC_V1 = {
    'version': NOTICE_GEOLOC_VERSION,
    'titre': 'Information sur la géolocalisation pendant vos interventions',
    'texte': (
        "Pendant vos missions, votre position est relevée automatiquement "
        "par l'application, uniquement lorsque l'intervention est « en "
        "route » ou « sur site ». Elle n'est jamais relevée en dehors de ces "
        "périodes. Un indicateur dans l'application vous le signale pendant "
        "le suivi. L'acceptation de ces conditions est nécessaire pour "
        "utiliser l'application de terrain."
    ),
    'responsable': (
        "La société qui vous confie la mission (celle qui a créé votre "
        "compte), responsable du traitement au sens de la loi 09-08."),
    'finalites': [
        "Organiser les interventions et le déplacement des techniciens.",
        "Constater l'arrivée et la présence sur le chantier (heure "
        "d'arrivée, temps passé sur site).",
        "Assurer la sécurité des techniciens isolés sur chantier.",
        "Établir la preuve de la prestation (arrivée, présence, durée sur "
        "site).",
    ],
    'donnees': [
        "Position GPS (latitude, longitude) et sa précision.",
        "Heure de chaque relevé.",
        "Intervention et chantier concernés.",
        "Distance au chantier et franchissements de son périmètre.",
    ],
    'destinataires': [
        "Votre responsable et les administrateurs de la société.",
        "Aucun tiers, aucun client : la position n'est jamais montrée "
        "au client.",
    ],
    'retention_jours': POSITION_RETENTION_JOURS,
    'droits': [
        "Droit d'accès : vous consultez vos propres positions dans "
        "« Ma journée » (Mes positions du jour).",
        "Droit de rectification et d'opposition pour motif légitime : "
        "adressez-vous à votre responsable ou à l'administrateur.",
        "Droit de retrait : le retrait de l'accord met fin à l'accès aux "
        "missions dans l'application ; demandez-le à votre responsable.",
        "Réclamation possible auprès de la CNDP (www.cndp.ma).",
    ],
}


def notice_geoloc(recepisse_cndp=None):
    """Notice d'information à servir au technicien, n° de récépissé CNDP
    compris (« non encore déclaré » tant qu'il est vide)."""
    notice = dict(NOTICE_GEOLOC_V1)
    notice['recepisse_cndp'] = (recepisse_cndp or '').strip() or RECEPISSE_NON_DECLARE
    return notice


class GpsConsentRecord(models.Model):
    """Trace DURABLE du consentement GPS déjà obtenu par employé (loi 09-08).

    Établi UNE FOIS (processus RH/onboarding, hors de ce module) ; ce modèle ne
    fait qu'enregistrer le fait, il ne pilote AUCUN interrupteur côté
    technicien — voir la note de module ci-dessus. ``revoked_at`` existe pour
    l'audit (fin de contrat, retrait légal) mais n'est jamais posé par le
    client mobile ; seule une action responsable/admin peut révoquer."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True, blank=True, related_name='gps_consent_records')
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # on_delete: donnée de suivi/planning du technicien — sans objet sans lui
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
    # Revue chantier 26/10/2026 — information préalable (loi 09-08 art. 5) :
    # version de la notice montrée, n° de récépissé CNDP de la société, et
    # l'ACCUSÉ DE RÉCEPTION du technicien lui-même, posé UNE FOIS dans
    # l'application (``mon-consentement/accepter``). Tant qu'il manque, aucun
    # ping n'est accepté.
    notice_version = models.CharField(
        max_length=20, default=NOTICE_GEOLOC_VERSION,
        help_text="Version de la notice d'information géolocalisation montrée.")
    recepisse_cndp = models.CharField(
        max_length=60, blank=True, default='',
        help_text="N° de récépissé de la déclaration CNDP (vide = non encore déclaré).")
    accepte_le = models.DateTimeField(
        null=True, blank=True,
        help_text="Accusé de réception de la notice par le technicien (dans l'application).")
    accepte_depuis_ip = models.GenericIPAddressField(null=True, blank=True)

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
        """Non révoqué (n'implique PAS l'accusé de réception du technicien)."""
        return self.revoked_at is None

    @property
    def is_acknowledged(self):
        """Le technicien a lu la notice et en a accusé réception."""
        return self.accepte_le is not None

    @property
    def statut(self):
        """``revoque`` | ``a_accepter`` | ``actif`` (cf. ``statut_consentement``)."""
        if not self.is_active:
            return 'revoque'
        return 'actif' if self.is_acknowledged else 'a_accepter'


class PositionTechnicien(models.Model):
    """Position GPS live d'un technicien (ping périodique du client mobile).

    ``intervention`` est nullable : une position peut être capturée pendant les
    heures de service SANS intervention active (selon la politique société),
    mais le caractère OBLIGATOIRE (``gps_tracking_required``) ne s'applique
    qu'à une intervention active. Rétention courte : ``services.
    purge_positions_expirees`` supprime les lignes plus vieilles que
    ``POSITION_RETENTION_JOURS`` — aucune conservation indéfinie."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True, blank=True, related_name='positions_techniciens')
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # on_delete: donnée de suivi/planning du technicien — sans objet sans lui
        related_name='positions_gps')
    intervention = models.ForeignKey(
        Intervention,
        on_delete=models.CASCADE,  # on_delete: PositionTechnicien est le détail de Intervention — n'existe pas sans lui
        null=True, blank=True,
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
    """Journal des FRANCHISSEMENTS du rayon attendu du chantier pendant une
    intervention active (géofencing). Additif, company-scopée.

    Deux types de lignes (``type_franchissement``) :

      * ``sortie`` — la position live est HORS du rayon alors que
        l'intervention est SUR SITE. Revue chantier 26/10/2026 : UNE seule
        sortie ouverte par intervention jusqu'à une nouvelle entrée (avant,
        une ligne par ping hors rayon — une alerte par minute, y compris
        pendant le trajet « en route ») ; chaque nouvelle sortie notifie le(s)
        responsable(s).
      * ``entree`` — NTMOB9 : la position live vient de RENTRER dans le rayon
        alors que la précédente était dehors. C'est le point de présence
        « check-in géofencé » du technicien, posé SANS action de sa part. Une
        seule ligne par franchissement entrant (pas une par ping à l'intérieur)
        puisqu'il faut une position précédente hors périmètre pour le
        déclencher.

    NTMOB9 se construit ici plutôt que sur une table de pointage dédiée : le
    consentement vit déjà dans ``GpsConsentRecord``, la position dans
    ``PositionTechnicien`` et le franchissement ici — une deuxième table
    dupliquerait la même donnée (arbitrage WIR113, ``docs/module-map.md``).
    """

    class TypeFranchissement(models.TextChoices):
        ENTREE = 'entree', 'Entrée'
        SORTIE = 'sortie', 'Sortie'
        # Fondateur 27/10/2026 — aucun relevé depuis ``SEUIL_INTERRUPTION_MIN``
        # alors que l'intervention est en route / sur site et l'accord donné
        # (``gps_tracking_service.signaler_interruptions``, beat 10 min).
        INTERRUPTION = 'interruption', 'Suivi interrompu'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True, blank=True, related_name='geofence_alerts')
    intervention = models.ForeignKey(
        Intervention,
        on_delete=models.CASCADE,  # on_delete: GeofenceAlert est le détail de Intervention — n'existe pas sans lui
        related_name='geofence_alerts')
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # on_delete: donnée de suivi/planning du technicien — sans objet sans lui
        related_name='geofence_alerts')
    # Revue chantier 26/10/2026 — SET_NULL (était CASCADE) : la purge des
    # positions (rétention 30 j) ne doit pas effacer l'historique de présence.
    position = models.ForeignKey(
        PositionTechnicien,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='geofence_alerts')
    # Nulle pour une ``interruption`` sans aucun relevé évalué (jamais une
    # distance inventée).
    distance_site_km = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True)
    rayon_attendu_km = models.DecimalField(max_digits=8, decimal_places=3)
    # NTMOB9 — défaut ``sortie`` : toute ligne antérieure à ce champ était un
    # dépassement de rayon, la reprise de l'historique est donc exacte sans
    # migration de données.
    type_franchissement = models.CharField(
        max_length=12, choices=TypeFranchissement.choices,
        default=TypeFranchissement.SORTIE,
        verbose_name='Type de franchissement')
    created_at = models.DateTimeField(auto_now_add=True)
    # Revue 26/10/2026 (F4) — instant du RELEVÉ qui a levé le franchissement
    # (``created_at`` = insertion, faux pour un lot hors-ligne rattrapé après
    # coup). Copié de la position : survit à sa purge (présence après 30 j).
    # Nul pour les alertes antérieures (repli sur ``created_at``).
    captured_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Instant du relevé GPS ayant levé le franchissement.')
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
        return (f'Géofence {self.get_type_franchissement_display()} · '
                f'intervention {self.intervention_id} '
                f'({self.distance_site_km} km)')

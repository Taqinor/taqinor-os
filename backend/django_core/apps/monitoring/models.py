"""
Monitoring (N50/N51/N52) — supervision de la PRODUCTION des systèmes installés.

Le « système installé » est le chantier réceptionné (apps.installations.
Installation, parc_actif). Ce module ajoute, de façon STRICTEMENT ADDITIVE :

  * MonitoringConfig : configuration de supervision PAR système installé —
    quel fournisseur (provider), activé ou non, et ses identifiants/réglages
    (JSON, par système). Tant qu'aucun fournisseur n'est configuré, la
    supervision ne fait RIEN (saisie manuelle uniquement) — comportement
    d'aujourd'hui inchangé.

  * ProductionReading : un relevé de production (énergie kWh sur une période),
    soit saisi À LA MAIN (fallback par défaut), soit récupéré AUTOMATIQUEMENT
    par un connecteur fournisseur configuré.

L'interface fournisseur est SWAPPABLE — calquée sur l'interface OCR existante :
un fournisseur par défaut « NoOp » qui ne renvoie rien (saisie manuelle), et un
squelette `FusionSolarProvider` (Huawei) qui ne s'active QUE si des identifiants
sont configurés par système, et qui sinon (ou en cas d'erreur réseau) no-ope
proprement (renvoie []). Aucune dépendance pip nouvelle, aucun coût par défaut.

N52 — la sous-performance est pilotée par un réglage PAR SOCIÉTÉ
(MonitoringSettings) : seuil (% sous l'attendu) + bascule d'auto-création d'un
ticket SAV. Par défaut la bascule est DÉSACTIVÉE : rien ne change tant qu'on ne
l'active pas. Le drapeau de sous-performance (UnderperformanceFlag) est
idempotent — jamais deux tickets pour un même drapeau ouvert.

`company` est TOUJOURS posée côté serveur (TenantMixin), jamais lue du corps.
"""
from django.conf import settings
from django.db import models

# FG282 — garantie de production (modèle additif en module dédié, re-exporté ici
# pour que `monitoring.models.ProductionWarranty` reste l'import canonique).
from .models_warranty import ProductionWarranty  # noqa: F401


class MonitoringConfig(models.Model):
    """Configuration de supervision d'UN système installé (chantier).

    `provider` = clé du fournisseur dans le registre (défaut 'noop' = manuel).
    `credentials` = JSON par système (identifiants / station id…) lu par le
    connecteur ; jamais exposé tel quel côté client (write-only en API).
    Tant que `enabled` est faux ou que les identifiants manquent, la synchro
    ne fait rien (saisie manuelle), comportement d'aujourd'hui.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='monitoring_configs')
    # Un chantier (système installé) ↔ une configuration de supervision.
    installation = models.OneToOneField(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='monitoring_config')
    # Clé du fournisseur dans le registre. 'noop' = aucun (saisie manuelle).
    provider = models.CharField(max_length=40, default='noop')
    enabled = models.BooleanField(default=False)
    # Réglages/identifiants par système (station id, login…). JSON libre lu par
    # le connecteur. Vide = pas d'identifiants → le connecteur no-ope.
    credentials = models.JSONField(default=dict, blank=True)
    # Production annuelle attendue (kWh/an) pour ce système, base du calcul de
    # sous-performance (N52). Optionnelle ; sinon estimée depuis la puissance.
    expected_annual_kwh = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuration de supervision'
        verbose_name_plural = 'Configurations de supervision'
        ordering = ['-date_modification']
        indexes = [models.Index(fields=['company', 'provider'])]

    def __str__(self):
        return f'Monitoring #{self.installation_id} ({self.provider})'

    @property
    def is_auto(self):
        """Vrai si une récupération automatique est réellement possible :
        activé, fournisseur non-noop ET identifiants présents."""
        return bool(self.enabled and self.provider != 'noop' and self.credentials)


class ProductionReading(models.Model):
    """Un relevé de production (énergie kWh sur une période) d'un système.

    `source` distingue la saisie manuelle (fallback) de la récupération
    automatique par un connecteur. `external_id` (optionnel) rend la synchro
    auto idempotente : un même relevé fournisseur n'est jamais dupliqué.
    """

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Saisie manuelle'
        AUTO = 'auto', 'Automatique'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='production_readings')
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='production_readings')
    # Date du relevé (jour). `period_days` = nombre de jours couverts (1 = jour,
    # 30 ≈ mois…) pour interpréter l'énergie sur la bonne fenêtre.
    date = models.DateField()
    period_days = models.PositiveIntegerField(default=1)
    energy_kwh = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.MANUAL)
    # Identifiant fourni par le connecteur (idempotence de la synchro auto).
    external_id = models.CharField(max_length=120, blank=True, default='')
    note = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='production_readings')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Relevé de production'
        verbose_name_plural = 'Relevés de production'
        ordering = ['-date', '-id']
        indexes = [
            models.Index(fields=['company', 'installation', '-date']),
        ]
        constraints = [
            # Un relevé auto par (système, external_id) — idempotence synchro.
            models.UniqueConstraint(
                fields=['installation', 'external_id'],
                condition=models.Q(source='auto') & ~models.Q(external_id=''),
                name='uniq_auto_reading_external_id'),
        ]

    def __str__(self):
        return f'{self.installation_id} {self.date} {self.energy_kwh} kWh'


class CleaningEvent(models.Model):
    """FG283 — un NETTOYAGE de panneaux daté pour un système.

    Sert de borne pour estimer la perte par salissure : la chute de PR depuis le
    dernier nettoyage indique l'encrassement accumulé. Multi-tenant ; `company`
    posée côté serveur, jamais lue du corps.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='cleaning_events')
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='cleaning_events')
    date = models.DateField()
    note = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cleaning_events')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Nettoyage de panneaux'
        verbose_name_plural = 'Nettoyages de panneaux'
        ordering = ['-date', '-id']
        indexes = [
            models.Index(fields=['company', 'installation', '-date']),
        ]

    def __str__(self):
        return f'Nettoyage #{self.installation_id} {self.date}'


class MonitoringSettings(models.Model):
    """N52 — réglage de sous-performance PAR SOCIÉTÉ (singleton).

    `underperf_threshold_pct` = pourcentage SOUS l'attendu déclenchant le
    drapeau (défaut 20 %). `auto_create_ticket` = créer automatiquement un
    ticket SAV quand un système est flaggé (défaut FAUX → comportement
    d'aujourd'hui : rien n'est créé tant qu'on ne l'active pas).
    """

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='monitoring_settings')
    underperf_threshold_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=20)
    auto_create_ticket = models.BooleanField(default=False)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réglage supervision'
        verbose_name_plural = 'Réglages supervision'

    def __str__(self):
        return f'Réglage supervision (société {self.company_id})'

    @classmethod
    def get(cls, company):
        obj, _ = cls.objects.get_or_create(company=company)
        return obj


class UnderperformanceFlag(models.Model):
    """N52 — drapeau de sous-performance OUVERT pour un système.

    Rend l'auto-création de ticket SAV idempotente : un seul drapeau ouvert par
    système à la fois ; si un ticket est créé, il est lié ici. Le drapeau se
    ferme quand la production repasse au-dessus du seuil.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='underperformance_flags')
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='underperformance_flags')
    # Performance mesurée vs attendue (ratio % au moment du flag), pour info.
    ratio_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    is_open = models.BooleanField(default=True)
    # Ticket SAV auto-créé pour ce drapeau (le cas échéant). SET_NULL : la
    # suppression d'un ticket ne casse pas le drapeau.
    ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='underperformance_flags')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_cloture = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Drapeau de sous-performance'
        verbose_name_plural = 'Drapeaux de sous-performance'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'installation', 'is_open']),
        ]
        constraints = [
            # Un seul drapeau OUVERT par système (idempotence du flag/ticket).
            models.UniqueConstraint(
                fields=['installation'],
                condition=models.Q(is_open=True),
                name='uniq_open_underperf_flag'),
        ]

    def __str__(self):
        return f'Flag #{self.installation_id} ({"ouvert" if self.is_open else "fermé"})'


# ── FG244 — Abonnements de monitoring (revenu récurrent) ───────────────────
# ODX16 — relogé depuis ``apps.compta`` (défaut fondateur : monitoring, car le
# modèle référence les configs de supervision ; facturation future via services
# ventes). La table physique existante est PRÉSERVÉE À L'IDENTIQUE
# (``db_table = 'compta_abonnementmonitoring'``) via des migrations
# ``SeparateDatabaseAndState`` (state-only, aucun SQL, aucune donnée déplacée) :
# compta 0105 le retire de l'état AVANT que monitoring 0004 ne le recrée sur la
# MÊME table. Un shim de ré-export subsiste dans ``apps/compta/models.py`` pour
# le code/migrations/services historiques. Client/installation restent
# référencés par id (cross-app — jamais d'import crm/installations).

class AbonnementMonitoring(models.Model):
    """Abonnement de supervision (monitoring) mensuel/annuel (FG244).

    Offre de revenu récurrent adossée au module monitoring : le client paie une
    supervision périodique de son installation. Client/installation référencés
    par id (cross-app — jamais d'import monitoring/crm). ``prochaine_echeance``
    est recalculée à chaque renouvellement selon la périodicité. Scopé société.
    """
    class Periodicite(models.TextChoices):
        MENSUEL = 'mensuel', 'Mensuel'
        ANNUEL = 'annuel', 'Annuel'

    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'
        RESILIE = 'resilie', 'Résilié'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='abonnements_monitoring',
        verbose_name='Société',
    )
    client_id = models.PositiveIntegerField(verbose_name='Id du client')
    installation_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Id de l'installation")
    periodicite = models.CharField(
        max_length=8, choices=Periodicite.choices, default=Periodicite.MENSUEL,
        verbose_name='Périodicité')
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Montant par période (MAD)')
    statut = models.CharField(
        max_length=8, choices=Statut.choices, default=Statut.ACTIF,
        verbose_name='Statut')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    prochaine_echeance = models.DateField(
        null=True, blank=True, verbose_name='Prochaine échéance')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    # YSUBS3 — dernière période facturée (garde d'idempotence : ne re-facture
    # jamais la même `prochaine_echeance`). NULL = jamais facturé
    # (comportement historique intact tant que personne n'appelle
    # `facturer`).
    derniere_facturation = models.DateField(
        null=True, blank=True, verbose_name='Dernière période facturée')
    # YSUBS4 — motif de résiliation (obligatoire à la résiliation, posé par
    # le service ``resilier_abonnement_monitoring``, jamais le viewset).
    motif_resiliation = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Motif de résiliation')

    class Meta:
        verbose_name = 'Abonnement de monitoring'
        verbose_name_plural = 'Abonnements de monitoring'
        db_table = 'compta_abonnementmonitoring'
        ordering = ['prochaine_echeance', 'id']

    def __str__(self):
        return f'Monitoring client #{self.client_id} ({self.periodicite})'

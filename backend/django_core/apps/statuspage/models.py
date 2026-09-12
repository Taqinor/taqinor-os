"""NTOBS1/NTOBS2/NTOBS14/NTOBS15 — page de statut publique.

Modèles PUBLICS et majoritairement SYSTÈME (partagés entre tenants) : un jeu
de composants (API, PDF-devis, Stockage documents, Notifications, IA) et
l'historique d'incidents qui les affecte. ``company`` est NULLABLE sur
``ComponentStatus``/``IncidentPublic``/``UptimeDayBucket`` — la grande
majorité des lignes sont système (``company=None``), visibles de tous les
tenants ; un enregistrement société-spécifique reste possible pour un futur
incident borné à un seul tenant (ex. un aléa de migration de données propre à
une société). Le texte des incidents (titre/updates/post-mortem) est TOUJOURS
rédigé par un humain (le fondateur) — jamais généré automatiquement à partir
de ``core.health`` (règle « checked-facts-only » : aucun narratif inventé).

Cette app N'IMPORTE AUCUN modèle métier : les statuts sont dérivés de
``core.health.check_services()`` par le job Celery beat (``tasks.py``), jamais
d'appel synchrone côté public.
"""
from django.db import models
from django.utils import timezone

from core.models import TimestampedModel


class ComponentStatus(TimestampedModel):
    """Statut courant d'un composant public (rafraîchi par le beat 5 min).

    ``company`` NULL = composant SYSTÈME, partagé entre tous les tenants (le
    cas normal — API/PDF-devis/Stockage/Notifications/IA sont des services
    partagés). Un jeu de composants distinct par société n'est pas construit
    ici (hors périmètre NTOBS1) mais le champ reste nullable pour ne jamais
    fermer la porte à un composant société-spécifique futur.
    """

    class Statut(models.TextChoices):
        OPERATIONAL = 'operational', 'Opérationnel'
        DEGRADED = 'degraded', 'Dégradé'
        PARTIAL_OUTAGE = 'partial_outage', 'Panne partielle'
        MAJOR_OUTAGE = 'major_outage', 'Panne majeure'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='statuspage_composants',
        verbose_name='Société',
        help_text='NULL = composant système, partagé entre tous les tenants.')
    nom = models.CharField('Composant', max_length=120)
    region = models.CharField(
        'Région', max_length=60, blank=True, default='',
        help_text='Ex. « EU-West/Hetzner ». Libre, jamais un identifiant interne.')
    statut = models.CharField(
        'Statut', max_length=20, choices=Statut.choices,
        default=Statut.OPERATIONAL)
    derniere_verification = models.DateTimeField(
        'Dernière vérification', null=True, blank=True)

    class Meta:
        verbose_name = 'Composant (statut public)'
        verbose_name_plural = 'Composants (statut public)'
        ordering = ['nom', 'region']
        indexes = [
            models.Index(fields=['nom', 'region'],
                         name='statuspage_component_nom_idx'),
        ]

    def __str__(self):
        return f'{self.nom} ({self.region or "global"}) — {self.statut}'


class IncidentPublic(TimestampedModel):
    """Incident public affichable sur la page de statut.

    Rédigé par le fondateur — ``titre``/updates/post-mortem ne sont JAMAIS
    générés automatiquement depuis ``core.health`` (le texte narratif reste
    humain ; seul le statut des composants est dérivé automatiquement).
    """

    class Severite(models.TextChoices):
        MINEURE = 'mineure', 'Mineure'
        MAJEURE = 'majeure', 'Majeure'
        CRITIQUE = 'critique', 'Critique'

    class Statut(models.TextChoices):
        INVESTIGATING = 'investigating', 'En investigation'
        IDENTIFIED = 'identified', 'Cause identifiée'
        MONITORING = 'monitoring', 'Sous surveillance'
        RESOLVED = 'resolved', 'Résolu'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='statuspage_incidents',
        verbose_name='Société',
        help_text='NULL = incident système, visible de tous les tenants.')
    titre = models.CharField('Titre', max_length=255)
    composants = models.ManyToManyField(
        ComponentStatus, related_name='incidents', blank=True,
        verbose_name='Composants touchés')
    severite = models.CharField(
        'Sévérité', max_length=10, choices=Severite.choices,
        default=Severite.MINEURE)
    statut = models.CharField(
        'Statut', max_length=20, choices=Statut.choices,
        default=Statut.INVESTIGATING)
    region = models.CharField('Région', max_length=60, blank=True, default='')
    debute_le = models.DateTimeField('Débuté le', default=timezone.now)
    resolu_le = models.DateTimeField('Résolu le', null=True, blank=True)

    # NTOBS2 — post-mortem publié séparément de la clôture de l'incident.
    # Texte libre rédigé par un humain (checklist affichée à la saisie côté
    # frontend, pas de garde automatique possible sur du texte libre).
    postmortem_markdown = models.TextField(
        'Post-mortem', blank=True, default='')
    postmortem_publie_le = models.DateTimeField(
        'Post-mortem publié le', null=True, blank=True)

    class Meta:
        verbose_name = 'Incident (public)'
        verbose_name_plural = 'Incidents (publics)'
        ordering = ['-debute_le']
        indexes = [
            models.Index(fields=['statut', '-debute_le'],
                         name='statuspage_incident_statut_idx'),
            models.Index(fields=['region'], name='statuspage_incident_region_idx'),
        ]

    def __str__(self):
        return f'{self.titre} ({self.statut})'

    @property
    def postmortem_publie(self):
        return bool(self.postmortem_publie_le)


class IncidentUpdate(TimestampedModel):
    """Mise à jour horodatée d'un incident public (texte libre, humain)."""

    incident = models.ForeignKey(
        IncidentPublic, on_delete=models.CASCADE, related_name='updates',
        verbose_name='Incident')
    statut = models.CharField(
        'Statut au moment de la mise à jour', max_length=20,
        choices=IncidentPublic.Statut.choices)
    message = models.TextField('Message')
    horodatage = models.DateTimeField('Horodatage', default=timezone.now)

    class Meta:
        verbose_name = "Mise à jour d'incident"
        verbose_name_plural = "Mises à jour d'incident"
        ordering = ['horodatage']

    def __str__(self):
        return f'Update {self.incident_id} @ {self.horodatage}'

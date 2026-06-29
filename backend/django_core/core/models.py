from django.db import models


class TimestampedModel(models.Model):
    """
    Modèle abstrait de base — ajoute created_at
    / updated_at à tout modèle qui en hérite.
    Usage : class MonModele(TimestampedModel): ...
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AnomalyFlag(TimestampedModel):
    """FG360 — Signalement d'anomalie détectée (stock / paiements / fraude).

    Modèle de FONDATION, volontairement GÉNÉRIQUE : il ne référence AUCUN modèle
    métier (core doit rester une couche de base — contrat import-linter
    ``core-foundation-is-a-base-layer``). Le sujet de l'anomalie est désigné par
    une paire ``subject_type`` (libellé d'app/modèle, ex. ``'stock.Produit'``) +
    ``subject_id`` (chaîne) au lieu d'une vraie ForeignKey — pas d'import métier.

    Multi-tenant : ``company`` est obligatoire et toujours imposé côté serveur ;
    les querysets doivent filtrer par société (voir ``core.mixins.TenantMixin``).
    Un scan planifié (``core.anomaly.scan_for_outliers`` + ``record_anomaly``)
    repère les valeurs aberrantes et matérialise un ``AnomalyFlag`` par cas.
    """

    CATEGORY_STOCK = 'stock'
    CATEGORY_PAIEMENT = 'paiement'
    CATEGORY_FRAUDE = 'fraude'
    CATEGORY_AUTRE = 'autre'
    CATEGORY_CHOICES = [
        (CATEGORY_STOCK, 'Stock'),
        (CATEGORY_PAIEMENT, 'Paiement'),
        (CATEGORY_FRAUDE, 'Fraude'),
        (CATEGORY_AUTRE, 'Autre'),
    ]

    SEVERITY_INFO = 'info'
    SEVERITY_AVERTISSEMENT = 'avertissement'
    SEVERITY_CRITIQUE = 'critique'
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, 'Information'),
        (SEVERITY_AVERTISSEMENT, 'Avertissement'),
        (SEVERITY_CRITIQUE, 'Critique'),
    ]

    STATUS_OUVERT = 'ouvert'
    STATUS_EXAMINE = 'examine'
    STATUS_IGNORE = 'ignore'
    STATUS_RESOLU = 'resolu'
    STATUS_CHOICES = [
        (STATUS_OUVERT, 'Ouvert'),
        (STATUS_EXAMINE, 'En cours d\'examen'),
        (STATUS_IGNORE, 'Ignoré'),
        (STATUS_RESOLU, 'Résolu'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='anomaly_flags', verbose_name='Société')

    category = models.CharField(
        'Catégorie', max_length=20, choices=CATEGORY_CHOICES,
        default=CATEGORY_AUTRE)
    severity = models.CharField(
        'Gravité', max_length=20, choices=SEVERITY_CHOICES,
        default=SEVERITY_AVERTISSEMENT)
    status = models.CharField(
        'Statut', max_length=20, choices=STATUS_CHOICES,
        default=STATUS_OUVERT)

    # Désignation générique du sujet (PAS de FK métier — core reste fondation).
    subject_type = models.CharField(
        'Type de sujet', max_length=100, blank=True,
        help_text='Libellé app.Modèle, ex. « stock.Produit » (générique).')
    subject_id = models.CharField('Identifiant du sujet', max_length=64, blank=True)

    # Métrique qui a déclenché l'alerte.
    metric = models.CharField('Métrique', max_length=80, blank=True)
    value = models.FloatField('Valeur observée', null=True, blank=True)
    expected = models.FloatField('Valeur attendue', null=True, blank=True)
    score = models.FloatField(
        'Score d\'aberration', null=True, blank=True,
        help_text='Écart standardisé (z-score) ou amplitude relative.')

    message = models.CharField('Message', max_length=255)
    detail = models.JSONField('Détail', default=dict, blank=True)

    detected_at = models.DateTimeField('Détecté le', auto_now_add=True)

    class Meta:
        verbose_name = 'Anomalie détectée'
        verbose_name_plural = 'Anomalies détectées'
        ordering = ['-detected_at']
        indexes = [
            # Noms courts (≤30) et déterministes — pas de hash divergent.
            models.Index(fields=['company', 'status'], name='anomaly_company_status_idx'),
            models.Index(fields=['company', 'category'], name='anomaly_company_cat_idx'),
        ]

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.message}'

from django.db import models

from .stages import STAGE_CHOICES, NEW


class Client(models.Model):
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='clients',
    )
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255, blank=True, null=True)
    # Optionnel depuis 2026-06 : un client peut être créé depuis un lead sans
    # email (l'unicité (company, email) reste garantie quand l'email existe).
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        unique_together = [('company', 'email')]

    def __str__(self):
        return f"{self.nom} {self.prenom if self.prenom else ''}"


class Lead(models.Model):
    """A sales lead / opportunity — distinct from a Client (customer) record.

    Leads carry a pipeline stage (canonical from STAGES.py) and a source/origin
    so imported test leads are distinguishable from leads created natively in the
    OS. Pipeline stage lives HERE, never on the Client/contact table.
    """

    class Source(models.TextChoices):
        OS_NATIVE = 'os_native', 'Créé dans TAQINOR'
        ODOO_IMPORT_TEST = 'odoo_import_test', 'Import test Odoo'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='leads',
    )
    # Contact identity (a lead may not yet be a structured client).
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255, blank=True, null=True)
    societe = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    ville = models.CharField(max_length=120, blank=True, null=True)

    # Client (fiche structurée) résolu depuis ce lead — rempli au premier devis
    # ou manuellement ; la résolution évite les doublons (voir services.py).
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads',
    )

    # Facture électrique du lead (MAD/mois). Si l'été ne diffère pas de
    # l'hiver, facture_hiver vaut pour les deux (ete_differente = False).
    facture_hiver = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    facture_ete = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    ete_differente = models.BooleanField(default=False)

    # Pipeline stage — canonical keys from STAGES.py (default Nouveau / NEW).
    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default=NEW,
    )
    # Origin marker: native vs imported test data.
    source = models.CharField(
        max_length=32,
        choices=Source.choices,
        default=Source.OS_NATIVE,
    )
    # Traceability for imported records (e.g. Odoo lead id) — never written back.
    external_system = models.CharField(max_length=50, blank=True, null=True)
    external_id = models.CharField(max_length=100, blank=True, null=True)

    note = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'source']),
            models.Index(fields=['company', 'stage']),
        ]
        constraints = [
            # An imported record is unique per (company, system, external id) so
            # a re-run of the import does not create duplicates.
            models.UniqueConstraint(
                fields=['company', 'external_system', 'external_id'],
                name='uniq_lead_external_ref',
                condition=models.Q(external_id__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.nom} {self.prenom or ''} [{self.stage}]".strip()

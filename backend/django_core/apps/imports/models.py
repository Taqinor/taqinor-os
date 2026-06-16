from django.conf import settings
from django.db import models


class ImportBatch(models.Model):
    """Trace d'un import CSV / Excel — sert de marqueur d'origine.

    Chaque enregistrement créé par l'import porte un FK `import_batch` vers ce
    lot : on distingue ainsi les fiches importées des fiches saisies à la main
    ET de la migration Odoo ponctuelle (qui, elle, ne crée AUCUN ImportBatch).
    Strictement scopé société (règle multi-tenant non négociable).
    """

    class Target(models.TextChoices):
        LEAD = 'lead', 'Leads'
        CLIENT = 'client', 'Clients'
        PRODUIT = 'produit', 'Produits'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='import_batches',
    )
    target = models.CharField(max_length=20, choices=Target.choices)
    # Nom du fichier d'origine (informatif).
    filename = models.CharField(max_length=255, blank=True, default='')
    # Combien de lignes ont été créées / ignorées lors de la confirmation.
    created_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='import_batches',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lot d\'import'
        verbose_name_plural = 'Lots d\'import'
        ordering = ['-created_at']

    def __str__(self):
        return f'Import {self.target} #{self.pk} ({self.created_count} créés)'

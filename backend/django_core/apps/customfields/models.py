"""T11 — mécanisme de champs personnalisés (additif, approche JSONField).

Un admin définit des champs sur un module (leads, clients, produits) ; les
valeurs sont stockées dans le `custom_data` (JSONField) de l'enregistrement,
indexées par `code`. Aucune migration destructive : ajouter/retirer une
définition ne touche pas le schéma. Cf. docs/erp-data-model-proposal.md.
"""
from django.db import models


class CustomFieldDef(models.Model):
    class Module(models.TextChoices):
        LEAD = 'lead', 'Lead'
        CLIENT = 'client', 'Client'
        PRODUIT = 'produit', 'Produit'

    class FieldType(models.TextChoices):
        TEXT = 'text', 'Texte'
        NUMBER = 'number', 'Nombre'
        DATE = 'date', 'Date'
        CHOICE = 'choice', 'Choix'
        BOOLEAN = 'boolean', 'Oui/Non'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='custom_fields')
    module = models.CharField(max_length=20, choices=Module.choices)
    code = models.SlugField(max_length=50)
    libelle = models.CharField(max_length=120)
    type = models.CharField(max_length=12, choices=FieldType.choices,
                            default=FieldType.TEXT)
    # Options de la liste de choix (type=choice).
    options = models.JSONField(null=True, blank=True)
    obligatoire = models.BooleanField(default=False)
    # Afficher dans les listes/filtres (en plus du formulaire).
    visible_liste = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['module', 'ordre', 'libelle']
        unique_together = [('company', 'module', 'code')]
        verbose_name = 'Champ personnalisé'
        verbose_name_plural = 'Champs personnalisés'

    def __str__(self):
        return f'{self.module}.{self.code}'

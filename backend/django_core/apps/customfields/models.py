from django.db import models

# Modules cibles supportés par le mécanisme de champs personnalisés.
# Identifiants en anglais ; libellés français pour l'UI.
MODULE_LEAD = 'lead'
MODULE_CLIENT = 'client'
MODULE_PRODUIT = 'produit'

MODULE_CHOICES = [
    (MODULE_LEAD, 'Lead'),
    (MODULE_CLIENT, 'Client'),
    (MODULE_PRODUIT, 'Produit'),
]
MODULE_KEYS = {MODULE_LEAD, MODULE_CLIENT, MODULE_PRODUIT}

# Types de champ proposés. Identifiants stables en anglais.
TYPE_TEXT = 'text'
TYPE_NUMBER = 'number'
TYPE_DATE = 'date'
TYPE_CHOICE = 'choice'
TYPE_BOOLEAN = 'boolean'

FIELD_TYPE_CHOICES = [
    (TYPE_TEXT, 'Texte'),
    (TYPE_NUMBER, 'Nombre'),
    (TYPE_DATE, 'Date'),
    (TYPE_CHOICE, 'Liste de choix'),
    (TYPE_BOOLEAN, 'Oui / Non'),
]
FIELD_TYPE_KEYS = {TYPE_TEXT, TYPE_NUMBER, TYPE_DATE, TYPE_CHOICE, TYPE_BOOLEAN}


class CustomFieldDefinition(models.Model):
    """Définition d'un champ personnalisé ajouté par la société sur un module.

    La portée est TOUJOURS bornée à la société (`company`) : un champ d'une
    société ne fuit jamais chez une autre (règle multi-tenant non négociable).
    Les valeurs sont stockées dans le JSONField `custom_fields` du modèle cible.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='custom_field_definitions',
    )
    module = models.CharField(max_length=20, choices=MODULE_CHOICES)
    # Slug dérivé côté serveur depuis le libellé ; identifiant stable utilisé
    # comme clé dans le JSON des valeurs. Unique par (company, module).
    field_key = models.SlugField(max_length=60)
    label = models.CharField(max_length=120)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    # Options pour le type 'choice' : liste de chaînes. Vide pour les autres.
    choices = models.JSONField(default=list, blank=True)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    show_in_list = models.BooleanField(default=False)
    show_in_filter = models.BooleanField(default=False)
    # Désactiver = retirer le champ des formulaires sans perdre les valeurs
    # déjà saisies (jamais de suppression destructive des données).
    active = models.BooleanField(default=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Champ personnalisé'
        verbose_name_plural = 'Champs personnalisés'
        ordering = ['module', 'order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'module', 'field_key'],
                name='uniq_customfield_company_module_key',
            ),
        ]

    def __str__(self):
        return f'{self.module}.{self.field_key} ({self.label})'


class HiddenStandardField(models.Model):
    """Masquage d'un champ standard (natif) d'un module pour une société.

    Réversible : « réinitialiser par défaut » supprime ces entrées et ré-affiche
    les champs standard. On ne touche jamais au code des modèles natifs.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='hidden_standard_fields',
    )
    module = models.CharField(max_length=20, choices=MODULE_CHOICES)
    # Clé du champ standard masqué (ex. 'fbclid', 'utm_source').
    field_key = models.CharField(max_length=60)

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Champ standard masqué'
        verbose_name_plural = 'Champs standard masqués'
        ordering = ['module', 'field_key']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'module', 'field_key'],
                name='uniq_hiddenfield_company_module_key',
            ),
        ]

    def __str__(self):
        return f'{self.module}.{self.field_key} (masqué)'

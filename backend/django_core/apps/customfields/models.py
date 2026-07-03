"""T11 — mécanisme de champs personnalisés (additif, approche JSONField).

Un admin définit des champs sur un module (leads, clients, produits) ; les
valeurs sont stockées dans le `custom_data` (JSONField) de l'enregistrement,
indexées par `code`. Aucune migration destructive : ajouter/retirer une
définition ne touche pas le schéma. Cf. docs/erp-data-model-proposal.md.
"""
from django.conf import settings
from django.db import models


class CustomFieldDef(models.Model):
    class Module(models.TextChoices):
        LEAD = 'lead', 'Lead'
        CLIENT = 'client', 'Client'
        PRODUIT = 'produit', 'Produit'
        # FG100 — nouveaux modules opérationnels (additif, jamais destructif).
        DEVIS = 'devis', 'Devis'
        INSTALLATION = 'installation', 'Chantier'
        TICKET = 'ticket', 'Ticket SAV'
        # GED10 — métadonnées typées configurables sur les documents GED.
        DOCUMENT = 'document', 'Document GED'
        # XPLT14 — couverture des modules récents (relation/fichier).
        FOURNISSEUR = 'fournisseur', 'Fournisseur'
        EMPLOYE = 'employe', 'Employé'

    class FieldType(models.TextChoices):
        TEXT = 'text', 'Texte'
        NUMBER = 'number', 'Nombre'
        DATE = 'date', 'Date'
        CHOICE = 'choice', 'Choix'
        BOOLEAN = 'boolean', 'Oui/Non'
        # XPLT14 — lien vers un enregistrement d'un autre module (id + libellé
        # dénormalisé dans custom_data, résolu via les selectors du module
        # cible) et fichier (clé MinIO, réutilise records.storage).
        RELATION = 'relation', 'Relation'
        FICHIER = 'fichier', 'Fichier'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='custom_fields')
    # XPLT16 — max_length généreux : un objet personnalisé pose ses
    # définitions sous ``custom:<code_objet>`` (préfixe + slug, > 20 chars).
    # `choices` reste informatif (catalogue des modules NATIFS) ; les valeurs
    # `custom:*` sont validées dynamiquement par le serializer, pas ici.
    module = models.CharField(max_length=60, choices=Module.choices)
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
    # XPLT14 — module cible d'un champ type=relation (ex. 'client', 'produit').
    # Ignoré pour tout autre type. Valeurs valides = Module.choices.
    relation_module = models.CharField(
        max_length=20, choices=Module.choices, null=True, blank=True)
    # XPLT15 — conditions dynamiques (visible/requis/lecture seule) sans code.
    # Dict optionnel à clés parmi 'visible_si' / 'requis_si' /
    # 'lecture_seule_si', chaque valeur étant un arbre de conditions ET/OU/NON
    # au format core.rules (validé par validate_condition_group à la
    # définition). Évalué CÔTÉ FRONT pour l'affichage ET RE-VALIDÉ côté
    # serializer (requis_si est enforce serveur — jamais fait confiance au
    # seul masquage front). None/absent = pas de condition (comportement
    # actuel inchangé).
    conditions = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['module', 'ordre', 'libelle']
        unique_together = [('company', 'module', 'code')]
        verbose_name = 'Champ personnalisé'
        verbose_name_plural = 'Champs personnalisés'

    def __str__(self):
        return f'{self.module}.{self.code}'


class CustomObjectDef(models.Model):
    """XPLT16 — objet métier no-code créé par l'admin (registre de clés,
    visiteurs, matériel prêté…) sans écrire de code.

    Les CHAMPS de l'objet sont des ``CustomFieldDef`` ordinaires posés sous
    ``module='custom:<code>'`` (réutilisation totale du mécanisme existant :
    types, validation, RELATION/FICHIER, conditions XPLT15) — aucun second
    moteur de définition de champs. Les données saisies vivent dans
    ``CustomRecord.data`` (une ligne par enregistrement, comme ``custom_data``
    sur les modules natifs)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='custom_objects')
    code = models.SlugField(max_length=50)
    libelle = models.CharField(max_length=120)
    icone = models.CharField(max_length=8, blank=True, default='')
    actif = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='custom_objects_crees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['libelle']
        unique_together = [('company', 'code')]
        verbose_name = 'Objet personnalisé'
        verbose_name_plural = 'Objets personnalisés'

    def __str__(self):
        return f'{self.company_id}:{self.code}'

    @property
    def field_module(self):
        """La valeur `module` sous laquelle vivent les CustomFieldDef de cet
        objet — préfixe stable, jamais recalculé depuis le libellé (qui peut
        changer sans casser les définitions existantes)."""
        return f'custom:{self.code}'


class CustomRecord(models.Model):
    """XPLT16 — un enregistrement d'un ``CustomObjectDef`` (ligne de données).

    ``data`` porte les valeurs, validées/nettoyées par
    ``serializers.validate_custom_data(objet.field_module, company, data)`` —
    même chemin que ``custom_data`` sur les modules natifs. Le chatter
    générique (``records.Activity``, cf. les modules natifs) reste
    consommable via son ``content_type``/``object_id`` GenericForeignKey
    standard sans champ supplémentaire ici."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='custom_records')
    objet = models.ForeignKey(
        CustomObjectDef, on_delete=models.CASCADE, related_name='records')
    data = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='custom_records_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Enregistrement personnalisé'
        verbose_name_plural = 'Enregistrements personnalisés'

    def __str__(self):
        return f'{self.objet.code}#{self.pk}'

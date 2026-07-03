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

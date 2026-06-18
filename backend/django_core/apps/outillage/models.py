"""Module Outillage (F1 / F2) — équipement DURABLE, tenu strictement séparé du
stock consommable (apps.stock.Produit).

Un outil (perceuse, échelle, multimètre…) se suit à travers les emplacements
existants (dépôt principal + camionnette de apps.stock.EmplacementStock) plus un
état « En intervention ». Il n'est JAMAIS vendable, jamais consommé, et
n'apparaît sur AUCUN document client.

Les kits d'outillage (F2) sont des MODÈLES nommés et réutilisables, éditables
dans Paramètres : chacun est une liste ordonnée d'outils du catalogue, et peut
viser un type d'intervention qui le pré-sélectionne. Additif — company-scopé,
aucune migration destructive.
"""
from django.db import models


class Outillage(models.Model):
    """Outil durable du parc d'outillage (F1). Séparé des SKUs de stock."""

    class Statut(models.TextChoices):
        DISPONIBLE = 'disponible', 'Disponible'
        EN_INTERVENTION = 'en_intervention', 'En intervention'
        EN_REPARATION = 'en_reparation', 'En réparation'
        PERDU = 'perdu', 'Perdu'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='outillages')
    nom = models.CharField(max_length=255)
    # Catégorie libre (Échelle, Électroportatif, Mesure…). Texte simple :
    # l'outillage n'a pas besoin d'un référentiel dédié comme le catalogue.
    categorie = models.CharField(max_length=120, blank=True, default='')
    # Étiquette d'inventaire (asset tag) — identifiant physique collé sur l'outil.
    asset_tag = models.CharField(max_length=80, blank=True, default='')
    numero_serie = models.CharField(max_length=120, blank=True, default='')
    # Emplacement courant choisi parmi les emplacements de stock existants
    # (dépôt principal + camionnette). Null quand l'outil est en intervention,
    # en réparation ou perdu (sans emplacement physique connu).
    emplacement = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='outillages')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.DISPONIBLE)
    date_achat = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, default='')

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Outil'
        verbose_name_plural = 'Outillage'
        ordering = ['nom', 'id']
        indexes = [
            models.Index(fields=['company', 'statut']),
        ]

    def __str__(self):
        return self.nom


class KitOutillage(models.Model):
    """Modèle NOMMÉ et réutilisable de kit d'outillage (F2), éditable dans
    Paramètres. Peut viser un `type_intervention` (clé TypeIntervention) qui le
    pré-sélectionne à la préparation d'une intervention de ce type. Les défauts
    semés (Kit pose structure, raccordement, mise en service) sont pleinement
    éditables (renommer / réordonner / désactiver). Désactiver préserve la
    valeur sur les enregistrements historiques."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='kits_outillage')
    nom = models.CharField(max_length=120)
    # Type d'intervention (clé) qui auto-sélectionne ce kit. Vide = générique.
    type_intervention = models.CharField(max_length=40, blank=True, default='')
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Kit d'outillage"
        verbose_name_plural = "Kits d'outillage"
        ordering = ['ordre', 'nom']
        unique_together = [('company', 'nom')]

    def __str__(self):
        return self.nom


class KitOutillageItem(models.Model):
    """Un outil requis dans un kit (F2), ordonné. Référence un outil du
    catalogue Outillage. Company posée côté serveur depuis le kit parent."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='kit_outillage_items')
    kit = models.ForeignKey(
        KitOutillage, on_delete=models.CASCADE, related_name='items')
    outil = models.ForeignKey(
        Outillage, on_delete=models.CASCADE, related_name='kit_items')
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Outil du kit"
        verbose_name_plural = "Outils du kit"
        ordering = ['ordre', 'id']
        unique_together = [('kit', 'outil')]

    def __str__(self):
        return f'{self.kit} — {self.outil}'

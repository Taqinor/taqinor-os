"""Modèles du module Gestion de flotte (`apps.flotte`).

Squelette multi-société (FLOTTE1) enrichi des premiers actifs roulants :

* ``Vehicule`` (FLOTTE2) — véhicules immatriculés du parc (immatriculation,
  marque, modèle, énergie, kilométrage, valeur, statut).
* ``EnginRoulant`` (FLOTTE4) — engins non immatriculés suivis au compteur
  d'heures (nacelle, groupe électrogène, chariot…).

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Module entièrement additif — aucun comportement
existant n'est modifié.
"""
from django.db import models


# ── FLOTTE2 — Véhicules immatriculés ───────────────────────────────────────

class Vehicule(models.Model):
    """Un véhicule immatriculé du parc de la société."""

    class Energie(models.TextChoices):
        DIESEL = 'diesel', 'Diesel'
        ESSENCE = 'essence', 'Essence'
        ELECTRIQUE = 'electrique', 'Électrique'
        HYBRIDE = 'hybride', 'Hybride'

    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        MAINTENANCE = 'maintenance', 'En maintenance'
        REFORME = 'reforme', 'Réformé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='vehicules',
        verbose_name='Société',
    )
    immatriculation = models.CharField(
        max_length=30, verbose_name='Immatriculation')
    marque = models.CharField(max_length=80, blank=True, verbose_name='Marque')
    modele = models.CharField(max_length=80, blank=True, verbose_name='Modèle')
    energie = models.CharField(
        max_length=20, choices=Energie.choices, default=Energie.DIESEL,
        verbose_name='Énergie')
    kilometrage = models.PositiveIntegerField(
        default=0, verbose_name='Kilométrage')
    valeur = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Valeur (MAD)')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.ACTIF,
        verbose_name='Statut')
    # FLOTTE3 — référence VERS un emplacement de stock (`stock.EmplacementStock`)
    # par id NUMÉRIQUE, jamais un FK cross-app dur (modularité, voir CLAUDE.md).
    # null = véhicule non rattaché à un emplacement. La validation « même
    # société » se fait côté serveur via le sélecteur de `apps.stock`.
    emplacement_stock_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Emplacement de stock (id)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Véhicule'
        verbose_name_plural = 'Véhicules'
        unique_together = [('company', 'immatriculation')]
        ordering = ['immatriculation']

    def __str__(self):
        return f'{self.immatriculation} — {self.marque} {self.modele}'.strip()


# ── FLOTTE4 — Engins roulants suivis au compteur d'heures ──────────────────

class EnginRoulant(models.Model):
    """Un engin non immatriculé suivi au compteur d'heures.

    Distinct du ``Vehicule`` immatriculé : nacelles, groupes électrogènes et
    chariots se suivent au compteur d'heures (et non au kilométrage).
    """

    class Type(models.TextChoices):
        NACELLE = 'nacelle', 'Nacelle'
        GROUPE = 'groupe_electrogene', 'Groupe électrogène'
        CHARIOT = 'chariot', 'Chariot'

    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        MAINTENANCE = 'maintenance', 'En maintenance'
        REFORME = 'reforme', 'Réformé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='engins_roulants',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Désignation')
    type_engin = models.CharField(
        max_length=30, choices=Type.choices, default=Type.NACELLE,
        verbose_name='Type d\'engin')
    marque = models.CharField(max_length=80, blank=True, verbose_name='Marque')
    modele = models.CharField(max_length=80, blank=True, verbose_name='Modèle')
    compteur_heures = models.DecimalField(
        max_digits=10, decimal_places=1, default=0,
        verbose_name='Compteur d\'heures')
    valeur = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Valeur (MAD)')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.ACTIF,
        verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Engin roulant'
        verbose_name_plural = 'Engins roulants'
        ordering = ['nom']

    def __str__(self):
        return f'{self.nom} ({self.get_type_engin_display()})'


# ── FLOTTE6 — Référentiels (listes éditables par société) ──────────────────

class ReferentielFlotte(models.Model):
    """Entrée d'une liste de référence éditable du parc (lookup générique).

    Référentiel ADDITIF : il fournit des listes éditables par société (type de
    véhicule, type d'engin, énergie, catégorie de permis…) en PARALLÈLE des
    ``TextChoices`` figés portés par ``Vehicule``/``EnginRoulant`` — il ne les
    remplace ni ne les modifie. Chaque entrée est rattachée à une société (FK
    ``company`` posée côté serveur) et identifiée de façon stable par
    ``(company, domaine, code)``.
    """

    class Domaine(models.TextChoices):
        TYPE_VEHICULE = 'type_vehicule', 'Type de véhicule'
        TYPE_ENGIN = 'type_engin', "Type d'engin"
        ENERGIE = 'energie', 'Énergie'
        CATEGORIE_PERMIS = 'categorie_permis', 'Catégorie de permis'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='referentiels_flotte',
        verbose_name='Société',
    )
    domaine = models.CharField(
        max_length=30, choices=Domaine.choices, verbose_name='Domaine')
    code = models.CharField(max_length=40, verbose_name='Code')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Référentiel de flotte'
        verbose_name_plural = 'Référentiels de flotte'
        unique_together = [('company', 'domaine', 'code')]
        ordering = ['domaine', 'ordre', 'libelle']

    def __str__(self):
        return f'{self.get_domaine_display()} — {self.libelle}'

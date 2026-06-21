"""Modèles du module Gestion de flotte (`apps.flotte`).

Socle multi-société (FLOTTE1 / FLOTTE2) : le parc roulant de la société.

* ``Vehicule`` (FLOTTE2) — un véhicule/engin du parc (immatriculation, marque,
  modèle, type, énergie, kilométrage, valeur d'acquisition, mise en circulation,
  statut, conducteur).

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Module entièrement additif — aucun comportement
existant n'est modifié.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


# ── FLOTTE2 — Véhicules & engins du parc ───────────────────────────────────

class Vehicule(models.Model):
    """Un véhicule/engin immatriculé du parc de la société."""

    class TypeVehicule(models.TextChoices):
        VEHICULE = 'vehicule', 'Véhicule léger'
        CAMIONNETTE = 'camionnette', 'Camionnette'
        UTILITAIRE = 'utilitaire', 'Utilitaire'
        NACELLE = 'nacelle', 'Nacelle'
        GROUPE = 'groupe_electrogene', 'Groupe électrogène'
        CHARIOT = 'chariot', 'Chariot élévateur'
        AUTRE = 'autre', 'Autre'

    class Energie(models.TextChoices):
        ESSENCE = 'essence', 'Essence'
        DIESEL = 'diesel', 'Diesel'
        ELECTRIQUE = 'electrique', 'Électrique'
        HYBRIDE = 'hybride', 'Hybride'
        GPL = 'gpl', 'GPL'

    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        MAINTENANCE = 'maintenance', 'En maintenance'
        HORS_SERVICE = 'hors_service', 'Hors service'
        CEDE = 'cede', 'Cédé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_vehicules',
        verbose_name='Société',
    )
    immatriculation = models.CharField(
        max_length=20, verbose_name='Immatriculation')
    marque = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Marque')
    modele = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Modèle')
    type_vehicule = models.CharField(
        max_length=30, choices=TypeVehicule.choices,
        default=TypeVehicule.CAMIONNETTE, verbose_name='Type de véhicule')
    energie = models.CharField(
        max_length=20, choices=Energie.choices, default=Energie.DIESEL,
        verbose_name='Énergie')
    kilometrage = models.PositiveIntegerField(
        default=0, verbose_name='Kilométrage')
    valeur_acquisition = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name="Valeur d'acquisition")
    date_mise_circulation = models.DateField(
        null=True, blank=True, verbose_name='Date de mise en circulation')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.ACTIF,
        verbose_name='Statut')
    conducteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vehicules_conduits',
        verbose_name='Conducteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Véhicule'
        verbose_name_plural = 'Véhicules'
        unique_together = [('company', 'immatriculation')]
        ordering = ['immatriculation']

    def __str__(self):
        return f'{self.immatriculation} — {self.marque} {self.modele}'

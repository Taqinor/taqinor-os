"""Modèles de l'app `mrp` (Groupe NTMFG — Production / MRP II).

Moteur générique de production : postes de charge, gammes opératoires, ordres
de fabrication capacitaires. Distinct du kitting boutique déjà livré côté
`installations.Kit`/`KitComposant`/`OrdreAssemblage` (assemblage léger
magasin) — jamais reconstruit ici. `mrp` référence `stock`/`installations`
UNIQUEMENT par string-FK (jamais d'import de leurs modules `models`).
"""
from django.db import models

from core.models import TenantModel


class PosteDeCharge(TenantModel):
    """NTMFG1 — poste de charge (work center) : machine, ligne ou poste
    manuel, avec sa capacité journalière et son coût horaire INTERNE (jamais
    client-facing — comme `Produit.prix_achat`, DC28)."""

    class TypePoste(models.TextChoices):
        MACHINE = 'machine', 'Machine'
        LIGNE = 'ligne', 'Ligne'
        MANUEL = 'manuel', 'Poste manuel'
        # NTMFG10 — poste de sous-traitance (opération confiée à un tiers).
        SOUS_TRAITE = 'sous_traite', 'Sous-traité'

    code = models.CharField(max_length=40, verbose_name='Code')
    nom = models.CharField(max_length=200, verbose_name='Nom')
    type_poste = models.CharField(
        max_length=16, choices=TypePoste.choices,
        default=TypePoste.MACHINE, verbose_name='Type de poste')
    capacite_heures_jour = models.DecimalField(
        max_digits=5, decimal_places=2, default=8,
        verbose_name='Capacité (h/jour)')
    # Coût horaire INTERNE (main-d'œuvre + amortissement) — jamais dans un
    # document client-facing (même règle que `Produit.prix_achat`, DC28).
    cout_horaire = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Coût horaire (interne)')
    # Calendrier de travail simple : jours ouvrés + horaires, ex.
    # {"jours_ouvres": [0,1,2,3,4], "heure_debut": "08:00", "heure_fin": "17:00"}
    # (0=lundi). Défaut = semaine standard marocaine (lun-ven).
    calendrier_travail = models.JSONField(
        default=dict, blank=True, verbose_name='Calendrier de travail')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Poste de charge'
        verbose_name_plural = 'Postes de charge'
        ordering = ['nom']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='mrp_poste_co_code_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='mrp_poste_co_actif_idx'),
        ]

    def __str__(self):
        return f'{self.code} — {self.nom}'


class Gamme(TenantModel):
    """NTMFG2 — gamme opératoire généraliste (routing) : la SÉQUENCE
    d'opérations avec poste de charge + temps standard pour fabriquer un
    produit, réutilisable par plusieurs Ordres de Fabrication (NTMFG3).

    Distincte de `installations.EtapeAssemblage` (checklist légère d'un Kit
    atelier-boutique, sans poste ni temps réglé séparé du temps de
    préparation) — une `Gamme` PEUT référencer un produit qui EST un
    `stock.KitProduit` (le composite vendable), mais porte sa propre
    industrialisation (postes, temps, capacité)."""

    nom = models.CharField(max_length=200, verbose_name='Nom')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='mrp_gammes', verbose_name='Produit fabriqué')
    version = models.PositiveIntegerField(default=1, verbose_name='Version')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Gamme opératoire'
        verbose_name_plural = 'Gammes opératoires'
        ordering = ['produit_id', '-version']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'produit', 'version'],
                name='mrp_gamme_co_produit_version_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'produit', 'actif'],
                         name='mrp_gamme_co_produit_actif_idx'),
        ]

    def __str__(self):
        return f'{self.nom} (v{self.version})'


class OperationGamme(models.Model):
    """NTMFG2 — une opération de la gamme : poste de charge + temps standard
    (prépa/unitaire/par-lot, style routing Odoo). Pas de `company` propre —
    scopée via `gamme.company` (même convention que
    `installations.KitComposant`)."""

    gamme = models.ForeignKey(
        Gamme, on_delete=models.CASCADE, related_name='operations')
    ordre = models.PositiveIntegerField(default=1, verbose_name='Ordre')
    poste_charge = models.ForeignKey(
        PosteDeCharge, on_delete=models.PROTECT,
        related_name='operations_gamme', verbose_name='Poste de charge')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    temps_prepa_min = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Temps de préparation (min)')
    temps_unitaire_min = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Temps unitaire (min/pièce)')
    temps_min_par_lot = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Temps minimum par lot (min)')

    class Meta:
        verbose_name = 'Opération de gamme'
        verbose_name_plural = 'Opérations de gamme'
        ordering = ['gamme_id', 'ordre', 'id']
        indexes = [
            models.Index(fields=['gamme'], name='mrp_opgamme_gamme_idx'),
            models.Index(fields=['poste_charge'], name='mrp_opgamme_poste_idx'),
        ]

    def __str__(self):
        return f'{self.gamme_id} · {self.ordre}. {self.libelle}'

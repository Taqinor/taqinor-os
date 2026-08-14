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

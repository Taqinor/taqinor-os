"""NTFPA — FP&A d'entreprise : budgets par département, prévisions glissantes,
scénarios what-if, variance analysis.

Distinct de ``gestion_projet.BudgetProjet``/``LigneBudgetProjet`` (PROJ21/22 —
budget MICRO d'un chantier, matériel/main-d'œuvre/sous-traitance/divers) : ce
module porte le budget MACRO par société/département/période. Les deux
couches ne fusionnent JAMAIS.

Tout est multi-société : ``company`` posée côté serveur (jamais lue du corps
de requête). Pas de nouveau modèle de chatter — le journal (« mail.thread »)
d'un objet FP&A passe par le mixin de chatter générique de fondation
``records.Activity`` (ARC8) via ``apps.records.services`` ; AUCUNE classe
``*Activity`` bespoke n'est créée ici (garde ``check_platform.py``/ARC8).
"""
from django.conf import settings
from django.db import models


class Departement(models.Model):
    """NTFPA1 — Unité organisationnelle FP&A (hiérarchie intra-société)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='fpa_departements', verbose_name='Société',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    nom = models.CharField(max_length=150, verbose_name='Nom')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='fpa_departements_diriges',
        verbose_name='Responsable',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sous_departements', verbose_name='Département parent',
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Département'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='fpa_departement_code_unique'),
        ]
        ordering = ['nom']

    def __str__(self):
        return f'{self.code} — {self.nom}'

    def sous_arbre_ids(self):
        """Retourne l'ensemble des ids de ce département + tous ses
        descendants (récursif), utilisé par le périmètre de visibilité
        (NTFPA26) — un responsable de département voit aussi ses
        sous-départements."""
        ids = {self.pk}
        for enfant in Departement.objects.filter(parent_id=self.pk):
            ids |= enfant.sous_arbre_ids()
        return ids


class CycleBudgetaire(models.Model):
    """NTFPA2 — Cycle budgétaire d'entreprise (ex. « Budget 2027 »).

    ``exercice_comptable_id`` référence ``compta.ExerciceComptable`` en
    STRING-ID (jamais un FK dur — cross-app boundary, FPA lit compta via
    ``apps.compta.selectors.get_exercice_label`` uniquement).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        OUVERT_SAISIE = 'ouvert_saisie', 'Ouvert à la saisie'
        EN_VALIDATION = 'en_validation', 'En validation'
        CLOS = 'clos', 'Clos'

    class TypeCycle(models.TextChoices):
        ANNUEL = 'annuel', 'Annuel'
        TRIMESTRIEL = 'trimestriel', 'Trimestriel'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='fpa_cycles_budgetaires', verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom')
    exercice_comptable_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Exercice comptable (référence)',
    )
    date_debut = models.DateField(verbose_name='Début')
    date_fin = models.DateField(verbose_name='Fin')
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut',
    )
    type_cycle = models.CharField(
        max_length=15, choices=TypeCycle.choices, default=TypeCycle.ANNUEL,
        verbose_name='Type de cycle',
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cycle budgétaire'
        ordering = ['-date_debut']

    def __str__(self):
        return self.nom

    @property
    def clos(self):
        return self.statut == self.Statut.CLOS

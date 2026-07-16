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

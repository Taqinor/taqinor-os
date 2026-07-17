"""Onboarding produit (NTDMO11-13) — checklist « Premiers pas ».

Deux modèles :

* ``OnboardingChecklistItem`` — CATALOGUE d'items (clé stable, libellé FR, ordre,
  rôles cibles, lien vers l'écran, événement d'auto-complétion). Un item est
  GLOBAL par défaut (``company`` NULL = modèle partagé par toutes les sociétés) ;
  le FK ``company`` nullable existe pour la portée multi-tenant (jamais utilisé
  pour les items de catalogue standard). ``roles_cibles`` vide = tous les rôles.
* ``OnboardingProgress`` — avancement PAR utilisateur (company + user + item),
  ``complete_le`` nullable, unique_together (user, item). Company-scopé.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class OnboardingChecklistItem(TenantModel):
    """Item de checklist « Premiers pas » (catalogue, généralement global).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré
    ci-dessous (related_name historique conservé) avec ``null=True,
    blank=True`` — divergence VOLONTAIRE du socle (par défaut obligatoire) :
    ``company`` NULL = item de catalogue GLOBAL (partagé par toutes les
    sociétés)."""
    # ``company`` NULL = item de catalogue GLOBAL (partagé par toutes les
    # sociétés). Présent pour la portée multi-tenant (YDATA4) ; les items seedés
    # sont globaux (company=None).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='onboarding_items')
    key = models.SlugField(
        max_length=80, unique=True,
        help_text='Clé stable (jamais renommée) — identifiant d\'auto-complétion.')
    libelle = models.CharField(max_length=200)
    # Ordre d'affichage dans le widget.
    ordre = models.PositiveIntegerField(default=100)
    # Rôles cibles (noms ``roles.Role``). Liste VIDE = tous les rôles.
    roles_cibles = models.JSONField(default=list, blank=True)
    # Lien vers l'écran cible (route frontend), ex. '/ventes/devis/nouveau'.
    lien = models.CharField(max_length=255, blank=True, default='')
    # Clé d'événement du bus (core.events) qui auto-coche l'item (NTDMO12).
    # Vide = item coché manuellement uniquement.
    event_key = models.CharField(max_length=60, blank=True, default='')
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['ordre', 'key']
        verbose_name = 'Item de checklist onboarding'
        verbose_name_plural = 'Items de checklist onboarding'

    def __str__(self):
        return f'{self.key} — {self.libelle}'

    def concerne_role(self, role_nom):
        """Vrai si l'item cible ce rôle (liste vide = tous les rôles)."""
        if not self.roles_cibles:
            return True
        return role_nom in self.roles_cibles


class OnboardingProgress(TenantModel):
    """Avancement d'un item de checklist pour un utilisateur (company-scopé).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='onboarding_progress')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='onboarding_progress')
    item = models.ForeignKey(
        OnboardingChecklistItem, on_delete=models.CASCADE,
        related_name='progress')
    # Horodatage de complétion (NULL = à faire).
    complete_le = models.DateTimeField(null=True, blank=True)
    # NTDMO13 — masquage manuel d'un item (persistant) SANS le marquer fait :
    # NULL = visible, non-NULL = ignoré par l'utilisateur.
    ignore_le = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'item')]
        verbose_name = 'Avancement onboarding'
        verbose_name_plural = 'Avancements onboarding'

    def __str__(self):
        etat = 'fait' if self.complete_le else 'à faire'
        return f'{self.user_id} · {self.item.key} ({etat})'

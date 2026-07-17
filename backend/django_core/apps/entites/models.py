"""apps.entites — Structure d'entités intra-tenant (Groupe NTADM, NTADM1).

Additif pur : aucun modèle métier existant (crm/ventes/stock) ne référence
encore l'entité (NTADM2, qui ajouterait un FK `entite` sur Lead/Devis/
Facture/Produit, est BLOQUÉ hors périmètre — écriture de migration dans des
apps étrangères — et reste à faire par le run plateforme/finance étendu).
"""
from django.db import models

from core.models import TenantModel


class Entite(TenantModel):
    """NTADM1 — unité organisationnelle DANS un tenant (holding, filiale,
    agence). `parent` (self-FK nullable) permet une hiérarchie à N niveaux.
    `code` unique par société (jamais globalement) — deux tenants différents
    peuvent réutiliser le même code."""

    nom = models.CharField(max_length=150)
    code = models.CharField(max_length=50)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,  # on_delete: une entité orpheline (parent supprimé) redevient racine plutôt que de disparaître en cascade
        related_name='enfants')
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Entité'
        verbose_name_plural = 'Entités'
        unique_together = [('company', 'code')]
        ordering = ['nom']

    def __str__(self):
        return f'{self.code} — {self.nom}'

    def descendants_ids(self):
        """Ensemble des ids de TOUS les descendants (récursif, pas soi-même).
        Utilisé par la garde anti-cycle NTADM30 : un parent ne peut jamais
        être rattaché à l'un de ses propres descendants."""
        out = set()
        stack = list(self.enfants.values_list('id', flat=True))
        seen = set(stack)
        while stack:
            current = stack.pop()
            out.add(current)
            for child_id in Entite.objects.filter(
                    parent_id=current).values_list('id', flat=True):
                if child_id not in seen:
                    seen.add(child_id)
                    stack.append(child_id)
        return out

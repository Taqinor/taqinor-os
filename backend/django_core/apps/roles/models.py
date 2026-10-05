from django.db import models

# Registre des droits : permissions_registre.py (SPL301).
from .permissions_registre import PERIMETRE_CHOICES


class Role(models.Model):
    company = models.ForeignKey(
        'authentication.Company',  # app_label.ModelName
        # on_delete: un rôle n'existe que dans SA société — supprimer la
        # société supprime ses rôles (aucun rôle orphelin ne doit survivre,
        # sans quoi il resterait porteur de permissions sans locataire).
        on_delete=models.CASCADE,
        related_name='roles',
    )
    nom = models.CharField(max_length=100)
    permissions = models.JSONField(default=list)
    est_systeme = models.BooleanField(default=False)
    # ── NTADM3 — Périmètre de DONNÉES par entité ────────────────────────────
    # Narrowing OPT-IN, exactement le patron déjà utilisé pour
    # ``records_scope_*`` (portée par propriétaire) et ``app_<clé>_voir``
    # (visibilité d'app) : VIDE = aucune restriction, le rôle voit toutes les
    # entités — c'est l'état de TOUS les rôles existants, donc zéro
    # régression. Dès qu'au moins une entité est cochée, la liste devient une
    # LISTE BLANCHE (cf. ``core.entite_scoping``) : les lignes « non
    # affectées » (``entite IS NULL``) restent visibles de tous, celles d'une
    # entité hors périmètre disparaissent et ne peuvent plus être créées.
    # FK-STRING cross-app : jamais d'import de ``apps.entites.models`` ici.
    entites_visibles = models.ManyToManyField(
        'entites.Entite',
        blank=True,
        related_name='roles_visibles',
        verbose_name='Entités visibles',
        help_text="Vide = toutes les entités sont visibles (défaut).",
    )
    # ── NTADM21 — Garde-fou de la délégation ────────────────────────────────
    # NULL = GLOBAL = comportement historique (Directeur, Administrateur, et
    # tous les rôles existants). Rempli, il BORNE ce que le porteur peut
    # créer, éditer et assigner comme rôle (cf. ``permissions_hors_perimetre``
    # et les gardes de ``RoleViewSet`` / ``UserSerializer.validate_role``).
    perimetre = models.CharField(
        'Périmètre de délégation', max_length=10,
        choices=PERIMETRE_CHOICES, null=True, blank=True, default=None,
        help_text="Vide = délégation globale (aucune restriction).",
    )

    class Meta:
        unique_together = [('company', 'nom')]
        verbose_name = 'Rôle'
        verbose_name_plural = 'Rôles'
        ordering = ['company', 'nom']

    def __str__(self):
        return f'{self.company.nom} — {self.nom}'

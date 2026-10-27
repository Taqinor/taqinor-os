from django.conf import settings
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


# ── Organigramme (fondateur, 27/10/2026) ────────────────────────────────────
# Direction en haut → départements (chacun son responsable) → équipes (chacune
# son chef) → personnes. Chaque compte porte une FONCTION (``Poste``) qui donne
# son département et son rôle par défaut. La hiérarchie (``supervisor``) en est
# recalculée par ``authentication.equipes_structure.recalculer_hierarchie``.


class Departement(models.Model):
    company = models.ForeignKey(
        # on_delete: donnée propre à la société — supprimée avec elle
        'authentication.Company', on_delete=models.CASCADE,
        related_name='departements')
    nom = models.CharField(max_length=120)
    responsable = models.ForeignKey(
        # on_delete: le département survit au départ de son responsable
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='departements_diriges')
    # Un seul département « Direction » par société (contrôlé au serializer).
    est_direction = models.BooleanField(default=False)
    ordre = models.IntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = [('company', 'nom')]
        ordering = ['-est_direction', 'ordre', 'nom']
        verbose_name = 'Département'
        verbose_name_plural = 'Départements'

    def __str__(self):
        return self.nom


class Poste(models.Model):
    """Fonction (intitulé de poste) : porte le département et le rôle par
    défaut de ses titulaires (``CustomUser.fonction``)."""
    company = models.ForeignKey(
        # on_delete: donnée propre à la société — supprimée avec elle
        'authentication.Company', on_delete=models.CASCADE,
        related_name='postes')
    intitule = models.CharField(max_length=120)
    departement = models.ForeignKey(
        # on_delete: la fonction survit à la suppression du département
        Departement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='postes')
    role = models.ForeignKey(
        # on_delete: la fonction survit à la suppression du rôle par défaut
        Role, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='postes')
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = [('company', 'intitule')]
        ordering = ['intitule']
        verbose_name = 'Fonction'
        verbose_name_plural = 'Fonctions'

    def __str__(self):
        return self.intitule


class EquipeOrg(models.Model):
    """Équipe générique d'un département autre que les ventes
    (``crm.EquipeCommerciale``) et le terrain (``installations.Equipe``)."""
    company = models.ForeignKey(
        # on_delete: donnée propre à la société — supprimée avec elle
        'authentication.Company', on_delete=models.CASCADE,
        related_name='equipes_org')
    nom = models.CharField(max_length=120)
    departement = models.ForeignKey(
        # on_delete: l'équipe survit à la suppression du département
        Departement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipes_org')
    chef = models.ForeignKey(
        # on_delete: l'équipe survit au départ de son chef
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='equipes_org_dirigees')
    membres = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='equipes_org')
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('company', 'nom')]
        ordering = ['nom']
        verbose_name = 'Équipe'
        verbose_name_plural = 'Équipes'

    def __str__(self):
        return self.nom

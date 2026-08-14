"""apps.promotions.models — moteur de promotions panier (NTRET12).

``ReglexPromotion`` est le modèle de règle configurable (company-scopée, via
``core.models.TenantModel``). Le calcul lui-même vit dans ``engine.py``
(module PUR, sans ORM) ; ``services.py`` fait le pont ORM ↔ moteur.

``categorie``/``produit`` référencent ``apps.stock`` par FK CHAÎNE
(``'stock.Categorie'``/``'stock.Produit'``) — jamais un import direct des
modèles stock (règle de modularité cross-app, CLAUDE.md)."""
from django.db import models
from django.utils import timezone

from core.models import TenantModel


class ReglexPromotion(TenantModel):
    """Une règle de promotion panier configurable (NTRET12)."""

    class TypeRegle(models.TextChoices):
        REMISE_POURCENTAGE_PRODUIT = (
            'remise_pourcentage_produit', 'Remise % produit/catégorie')
        REMISE_MONTANT_PANIER = (
            'remise_montant_panier', 'Remise montant fixe panier')
        N_POUR_M = 'n_pour_m', 'N pour M (ex. 3 pour 2)'
        PLAGE_HORAIRE = 'plage_horaire', 'Plage horaire (happy hour)'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: composition — l'objet n'existe que dans sa societe
        related_name='regles_promotion')
    nom = models.CharField(max_length=150)
    type_regle = models.CharField(max_length=30, choices=TypeRegle.choices)
    actif = models.BooleanField(default=True)
    # Plus petit = prioritaire entre règles NON cumulables (départage : la
    # remise la plus avantageuse gagne — cf. engine.evaluer_promotions).
    priorite = models.PositiveSmallIntegerField(default=100)
    cumulable = models.BooleanField(
        default=False,
        help_text='Peut se combiner avec les autres règles actives '
                  '(sinon, seule la plus prioritaire des règles non '
                  'cumulables applicables est retenue).')

    # ── Condition d'application (ciblage — vide = tout le panier) ──────────
    categorie = models.ForeignKey(
        'stock.Categorie', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='regles_promotion')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='regles_promotion')
    montant_min_panier = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Montant minimum du panier (TTC) pour que la règle '
                  "s'applique. Vide = aucun minimum.")

    # ── Paramètres selon le type (vides = non pertinents pour ce type) ─────
    remise_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Pourcentage de remise (remise_pourcentage_produit / '
                  'plage_horaire).')
    remise_montant = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Montant fixe de remise (remise_montant_panier).')
    n_achete = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text='N (n_pour_m) — ex. 3.')
    m_paye = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text='M (n_pour_m) — ex. 2.')
    heure_debut = models.TimeField(
        null=True, blank=True, help_text='Début de la plage horaire (happy hour).')
    heure_fin = models.TimeField(
        null=True, blank=True, help_text='Fin de la plage horaire (happy hour).')
    # Jours de semaine actifs (0=lundi … 6=dimanche). Vide = tous les jours.
    jours_semaine = models.JSONField(null=True, blank=True, default=list)

    # ── Période de validité (vide = toujours valide) ────────────────────────
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Règle de promotion'
        verbose_name_plural = 'Règles de promotion'
        ordering = ['priorite', 'nom']

    def __str__(self):
        return self.nom


# ── NTRET13 — Coupons à code unique ─────────────────────────────────────────
# Distinct de ``compta.CodePromotion`` (code de campagne marketing générique,
# sans traçabilité d'usage unique) : un CouponUnique porte une limite d'usage
# stricte (1×/client ou N× global) et une remise liée à UNE règle
# ``ReglexPromotion`` — objets distincts, cas d'usage distincts, ni l'un ni
# l'autre ne remplace ou ne duplique l'autre.

def default_coupon_code():
    import secrets
    import string
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


class CouponUnique(TenantModel):
    """Un coupon à code unique (NTRET13), saisissable à l'écran caisse."""

    class ModeLimite(models.TextChoices):
        UNIQUE_PAR_CLIENT = 'unique_par_client', '1 utilisation par client'
        GLOBAL = 'global', 'N utilisations au total (global)'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: composition — l'objet n'existe que dans sa societe
        related_name='coupons_uniques')
    code = models.CharField(max_length=32, default=default_coupon_code)
    regle = models.ForeignKey(
        ReglexPromotion, on_delete=models.PROTECT, related_name='coupons')
    mode_limite = models.CharField(
        max_length=20, choices=ModeLimite.choices, default=ModeLimite.GLOBAL)
    # Nombre d'utilisations autorisées en mode GLOBAL (ignoré en mode
    # UNIQUE_PAR_CLIENT, où la limite est structurellement 1 par client —
    # cf. CouponUtilisation.Meta.constraints).
    limite_usage = models.PositiveIntegerField(default=1)
    date_expiration = models.DateField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    # Posés côté SERVEUR à la PREMIÈRE utilisation uniquement (traçabilité —
    # jamais réécrits ensuite, même si le coupon est réutilisé par d'autres
    # clients en mode global).
    utilise_par = models.ForeignKey(
        'crm.Client', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coupons_utilises_en_premier')
    utilise_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Coupon à code unique'
        verbose_name_plural = 'Coupons à code unique'
        unique_together = [('company', 'code')]

    def __str__(self):
        return self.code


class CouponUtilisation(TenantModel):
    """Journal d'utilisation d'un coupon (NTRET13) — UNE ligne par
    utilisation effective. Porte la contrainte structurelle « 1×/client »
    des coupons en mode ``unique_par_client`` (jamais seulement applicative)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: composition — l'objet n'existe que dans sa societe
        related_name='utilisations_coupon')
    coupon = models.ForeignKey(
        CouponUnique, on_delete=models.CASCADE, related_name='utilisations')  # on_delete: composition — une utilisation n'existe que pour son coupon
    client = models.ForeignKey(
        'crm.Client', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='utilisations_coupon')
    utilise_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Utilisation de coupon'
        verbose_name_plural = 'Utilisations de coupon'
        ordering = ['-utilise_le']
        constraints = [
            models.UniqueConstraint(
                fields=['coupon', 'client'],
                condition=models.Q(client__isnull=False),
                name='promotions_couponutilisation_unique_par_client',
            ),
        ]

    def __str__(self):
        return f'{self.coupon.code} — {self.client_id}'


# ── NTRET15 — Cartes cadeaux ─────────────────────────────────────────────────

def default_carte_cadeau_code():
    import secrets
    import string
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(10))


class CarteCadeau(TenantModel):
    """Une carte cadeau (NTRET15) : émise au comptoir (encaissée normalement,
    sans ligne de stock — une carte cadeau n'est pas un produit inventorié),
    utilisable comme mode de paiement partiel/total sur une vente ultérieure,
    plusieurs passages possibles jusqu'à épuisement."""

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        EPUISEE = 'epuisee', 'Épuisée'
        EXPIREE = 'expiree', 'Expirée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: composition — l'objet n'existe que dans sa societe
        related_name='cartes_cadeaux')
    # Code unique généré, OU physique saisi (carte pré-imprimée) — les deux
    # passent par le même champ, `default` ne s'applique que si absent.
    code = models.CharField(max_length=32, default=default_carte_cadeau_code)
    montant_initial = models.DecimalField(max_digits=12, decimal_places=2)
    # Solde courant — décrémenté à chaque utilisation, jamais négatif (garde
    # dans ``services.debiter_carte_cadeau``, jamais seulement applicative).
    solde = models.DecimalField(max_digits=12, decimal_places=2)
    date_emission = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateField(
        null=True, blank=True, help_text='Vide = aucune expiration.')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ACTIVE)

    class Meta:
        verbose_name = 'Carte cadeau'
        verbose_name_plural = 'Cartes cadeaux'
        unique_together = [('company', 'code')]

    def __str__(self):
        return self.code

    def est_utilisable(self):
        """Utilisable MAINTENANT : statut actif en base ET pas expirée à la
        date du jour (l'expiration est évaluée dynamiquement — jamais besoin
        d'une tâche planifiée pour « faire passer » une carte en expirée)."""
        if self.statut != self.Statut.ACTIVE:
            return False
        if self.date_expiration and timezone.localdate() > self.date_expiration:
            return False
        return self.solde > 0

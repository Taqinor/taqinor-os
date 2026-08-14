"""apps.promotions.models — moteur de promotions panier (NTRET12).

``ReglexPromotion`` est le modèle de règle configurable (company-scopée, via
``core.models.TenantModel``). Le calcul lui-même vit dans ``engine.py``
(module PUR, sans ORM) ; ``services.py`` fait le pont ORM ↔ moteur.

``categorie``/``produit`` référencent ``apps.stock`` par FK CHAÎNE
(``'stock.Categorie'``/``'stock.Produit'``) — jamais un import direct des
modèles stock (règle de modularité cross-app, CLAUDE.md)."""
from django.db import models

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
        'authentication.Company', on_delete=models.CASCADE,
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

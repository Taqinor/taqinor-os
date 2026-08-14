"""Modèles de planification supply chain (Groupe NTSCM).

Multi-société : chaque modèle hérite de ``core.models.TenantModel`` (FK
``company`` posée côté serveur, jamais lue du corps de requête). Les
références vers ``apps.stock`` (Produit/Categorie) sont des FK **string-safe**
(``'stock.Produit'``) — jamais un ``from apps.stock.models import ...``
(frontière cross-app, CLAUDE.md) : Django résout la référence par app
label/nom de modèle sans qu'aucun import Python ne soit nécessaire ici.
"""
import re
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TenantModel

_PERIODE_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')


def _valider_periode(periode):
    """Garde-fou format ``YYYY-MM`` — appliqué dans ``save()`` (pas seulement
    dans un ``clean()`` qu'un ``.save()`` direct contournerait, cf. le piège
    CI documenté dans le brief de cette lane)."""
    if not _PERIODE_RE.match(periode or ''):
        raise ValueError(
            f'periode invalide : {periode!r} (format attendu "YYYY-MM").')


class PrevisionDemande(TenantModel):
    """NTSCM1 — prévision de demande par article/segment/mois.

    ``segment`` est un texte libre optionnel (ville, canal, type_installation…
    — aucune taxonomie fermée n'existe encore côté demande). Une seule
    prévision par (société, produit, segment, période) — contrainte unique,
    régénérée par ``services.generer_previsions`` (NTSCM2/3, ``update_or_create``).
    """

    class Methode(models.TextChoices):
        MOYENNE_MOBILE = 'moyenne_mobile', 'Moyenne mobile'
        TENDANCE = 'tendance', 'Tendance'
        SAISONNIER = 'saisonnier', 'Saisonnier'
        MANUEL = 'manuel', 'Manuel'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='scm_previsions_demande', verbose_name='Société')
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.CASCADE,
        related_name='scm_previsions_demande', verbose_name='Produit')
    segment = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Segment',
        help_text='Ville, canal, type_installation… texte libre, vide = tous segments.')
    periode = models.CharField(
        max_length=7, verbose_name='Période (YYYY-MM)')
    quantite_prevue = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Quantité prévue')
    methode = models.CharField(
        max_length=20, choices=Methode.choices, default=Methode.MANUEL,
        verbose_name='Méthode')
    genere_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Généré le')
    genere_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='scm_previsions_generees', verbose_name='Généré par')

    class Meta:
        verbose_name = 'Prévision de demande'
        verbose_name_plural = 'Prévisions de demande'
        ordering = ['-periode', 'produit_id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'produit', 'segment', 'periode'],
                name='uniq_scm_prevision_produit_segment_periode'),
        ]

    def save(self, *args, **kwargs):
        _valider_periode(self.periode)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.produit_id} {self.segment or "—"} {self.periode} = {self.quantite_prevue}'


class EvenementDemande(TenantModel):
    """NTSCM3 — événement de demande (promotion, chantier planifié, rupture
    fournisseur connue…) impactant la prévision sur une fenêtre de dates.

    ``produit`` nullable = tous les produits d'une ``categorie`` (elle-même
    nullable) ; ``produit`` ET ``categorie`` nuls ensemble = événement GLOBAL
    (toute la société). ``impact_pct`` est SIGNÉ (ex. ``+30`` = +30% promo,
    ``-100`` = rupture connue → demande nulle sur la fenêtre).
    ``services.generer_previsions`` applique l'impact cumulé des événements
    chevauchant chaque mois prévu, avant écriture."""

    class TypeEvenement(models.TextChoices):
        PROMOTION = 'promotion', 'Promotion'
        CHANTIER_MAJEUR = 'chantier_majeur', 'Chantier majeur'
        RUPTURE_FOURNISSEUR = 'rupture_fournisseur', 'Rupture fournisseur'
        SAISONNALITE_LOCALE = 'saisonnalite_locale', 'Saisonnalité locale'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='scm_evenements_demande', verbose_name='Société')
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='scm_evenements_demande', verbose_name='Produit',
        help_text='Vide = tous les produits de la catégorie (ou toute la société si catégorie aussi vide).')
    categorie = models.ForeignKey(
        'stock.Categorie',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='scm_evenements_demande', verbose_name='Catégorie')
    date_debut = models.DateField(verbose_name='Début')
    date_fin = models.DateField(verbose_name='Fin')
    impact_pct = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name='Impact (%)',
        help_text='Signé : +30 = +30% de demande, -100 = rupture connue (demande nulle).')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    type_evenement = models.CharField(
        max_length=20, choices=TypeEvenement.choices,
        default=TypeEvenement.AUTRE, verbose_name="Type d'événement")
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Événement de demande'
        verbose_name_plural = 'Événements de demande'
        ordering = ['-date_debut']

    def save(self, *args, **kwargs):
        if self.date_fin < self.date_debut:
            raise ValueError('date_fin doit être postérieure ou égale à date_debut.')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.libelle} ({self.impact_pct:+}%)'

"""Modèles du reporting ESG/durabilité consolidé (Groupe NTESG).

Cette app est une COUCHE DE CONSOLIDATION : elle ne resaisit rien de ce que
``qhse`` capture déjà (bilan carbone QHSE39, indicateurs ESG bruts QHSE40,
déchets, conformité environnementale…). Elle ajoute :

* ``PeriodeReportingESG`` — une période de reporting (mois/trimestre/année)
  que l'on peut FIGER : une fois figée, son ``SnapshotESG`` associé porte les
  chiffres AU MOMENT DE LA CLÔTURE, gelés, jamais recalculés en direct
  ensuite (même logique que ``compta.PeriodeComptable``) ;
* ``SnapshotESG`` — le JSON figé produit par
  ``apps.esg.services.figer_periode`` (agrégation cross-app via
  ``apps.esg.selectors.agreger_indicateurs_periode``) ;
* ``CatalogueIndicateurESG`` — référentiel GRI-lite seedable (~25-30
  indicateurs standards), sert de check-list de couverture ;
* ``ObjectifESGTrajectoire`` — objectif de réduction/progression avec
  trajectoire linéaire référence→cible, comparée aux valeurs réelles.

Tout hérite de ``core.models.TenantModel`` (FK ``company`` + timestamps —
convention SCA4 pour tout NOUVEAU modèle multi-société). Lecture des données
sources d'autres apps EXCLUSIVEMENT via leurs ``selectors.py`` (import
fonction-local, jamais leurs ``models``) — voir ``apps/esg/selectors.py``.
Entièrement additif.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel


class PeriodeReportingESG(TenantModel):
    """Période de reporting ESG d'une société (NTESG1).

    ``statut`` suit un cycle à sens unique : ``brouillon`` → ``figee`` →
    ``publiee``. Une fois ``figee`` (ou ``publiee``), la période devient
    IMMUABLE — son ``SnapshotESG`` (JSON gelé) est la seule source de vérité
    pour tout rendu (PDF/xlsx/API publique) ultérieur, quelles que soient les
    évolutions des données sources QHSE après coup.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        FIGEE = 'figee', 'Figée'
        PUBLIEE = 'publiee', 'Publiée'

    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    date_debut = models.DateField(verbose_name='Début')
    date_fin = models.DateField(verbose_name='Fin')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    figee_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Figée le')
    figee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='periodes_esg_figees',
        verbose_name='Figée par',
    )

    class Meta:
        verbose_name = 'Période de reporting ESG'
        verbose_name_plural = 'Périodes de reporting ESG'
        ordering = ['-date_debut', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'libelle'],
                name='esg_periode_co_libelle_uniq',
            ),
        ]

    def clean(self):
        super().clean()
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError(
                'La date de fin ne peut pas précéder la date de début.')

    @property
    def est_figee(self):
        """Vrai si la période est ``figee`` ou ``publiee`` (immuable)."""
        return self.statut in (self.Statut.FIGEE, self.Statut.PUBLIEE)

    def __str__(self):
        return f'{self.libelle} ({self.get_statut_display()})'


class SnapshotESG(TenantModel):
    """Instantané JSON figé des chiffres ESG d'une période (NTESG1).

    Produit une seule fois par ``services.figer_periode`` (jamais recalculé
    après coup) : ``donnees`` porte la structure renvoyée par
    ``selectors.agreger_indicateurs_periode`` au moment du figeage, avec les
    dates sérialisées en ISO 8601 (JSON-safe).
    """

    periode = models.OneToOneField(
        PeriodeReportingESG,
        on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='snapshot',
        verbose_name='Période',
    )
    donnees = models.JSONField(default=dict, blank=True, verbose_name='Données')
    figee_le = models.DateTimeField(
        auto_now_add=True, verbose_name='Figé le')

    class Meta:
        verbose_name = 'Instantané ESG'
        verbose_name_plural = 'Instantanés ESG'
        ordering = ['-figee_le', '-id']

    def __str__(self):
        return f'Snapshot {self.periode_id} ({self.figee_le:%Y-%m-%d})'


class CatalogueIndicateurESG(TenantModel):
    """Référentiel GRI-lite d'indicateurs ESG standards (NTESG3).

    Seedé de façon idempotente par société via
    ``python manage.py seed_catalogue_esg`` (voir
    ``management/commands/seed_catalogue_esg.py``) — sert de check-list au
    responsable QHSE/RSE pour savoir quels ``qhse.IndicateurESG`` créer.
    ``reference_gri`` est affichée en info-bulle « inspiré de » — jamais
    présentée comme une certification GRI.
    """

    class Pilier(models.TextChoices):
        ENVIRONNEMENT = 'environnement', 'Environnement'
        SOCIAL = 'social', 'Social'
        GOUVERNANCE = 'gouvernance', 'Gouvernance'

    code = models.CharField(max_length=30, verbose_name='Code')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    pilier = models.CharField(
        max_length=15, choices=Pilier.choices, verbose_name='Pilier ESG')
    unite_attendue = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Unité attendue')
    reference_gri = models.CharField(
        max_length=60, blank=True, default='',
        verbose_name='Référence GRI (inspiré de)')

    class Meta:
        verbose_name = 'Indicateur du catalogue GRI-lite'
        verbose_name_plural = 'Catalogue GRI-lite'
        ordering = ['pilier', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='esg_catalogue_co_code_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.code} — {self.libelle}'


class ObjectifESGTrajectoire(TenantModel):
    """Objectif de réduction/progression ESG avec trajectoire linéaire (NTESG7).

    ``indicateur_code`` référence en LECTURE le ``code`` d'un
    ``qhse.IndicateurESG`` (jamais une FK cross-app — string souple, résolue
    au moment du calcul via ``qhse.selectors.export_esg``). La trajectoire
    théorique interpole linéairement entre
    (``annee_reference``, ``valeur_reference``) et
    (``annee_cible``, ``valeur_cible``) ; des jalons intermédiaires optionnels
    peuvent affiner l'affichage (``jalons`` = ``{"2027": 120.5, ...}``).
    """

    indicateur_code = models.CharField(
        max_length=30, verbose_name='Code indicateur (qhse.IndicateurESG)')
    libelle = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Libellé')
    valeur_reference = models.DecimalField(
        max_digits=18, decimal_places=4, verbose_name='Valeur de référence')
    annee_reference = models.PositiveIntegerField(
        verbose_name='Année de référence')
    valeur_cible = models.DecimalField(
        max_digits=18, decimal_places=4, verbose_name='Valeur cible')
    annee_cible = models.PositiveIntegerField(verbose_name='Année cible')
    jalons = models.JSONField(
        default=dict, blank=True,
        verbose_name='Jalons intermédiaires ({année: valeur})')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Objectif de trajectoire ESG'
        verbose_name_plural = 'Objectifs de trajectoire ESG'
        ordering = ['indicateur_code', 'annee_cible']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'indicateur_code', 'annee_cible'],
                name='esg_objectif_co_code_anneecible_uniq',
            ),
        ]

    def clean(self):
        super().clean()
        if self.annee_cible and self.annee_reference \
                and self.annee_cible <= self.annee_reference:
            raise ValidationError(
                "L'année cible doit être postérieure à l'année de référence.")

    def __str__(self):
        return (f'{self.indicateur_code} → {self.valeur_cible} '
                f'({self.annee_cible})')

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


class ClassificationABC(TenantModel):
    """NTSCM4 — classement ABC (Pareto) d'un produit, recalculé par
    ``selectors.classifier_abc`` (jamais saisi manuellement).

    ADAPTATION DE PÉRIMÈTRE (frontière cross-app, CLAUDE.md) : le plan
    d'origine prévoyait un champ persisté directement sur ``stock.Produit``
    (``Produit.classe_abc``) — cette lane ne peut pas écrire dans
    ``apps/stock`` (propriété d'une autre lane du même run). Le classement
    est donc persisté ICI, avec le même contrat (recalcul serveur uniquement,
    OneToOne avec le produit, jamais d'édition manuelle exposée par l'API)."""

    class Classe(models.TextChoices):
        A = 'A', 'A'
        B = 'B', 'B'
        C = 'C', 'C'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='scm_classifications_abc', verbose_name='Société')
    produit = models.OneToOneField(
        'stock.Produit',
        on_delete=models.CASCADE,
        related_name='scm_classification_abc', verbose_name='Produit')
    classe = models.CharField(
        max_length=1, choices=Classe.choices, verbose_name='Classe')
    valeur_cumulee_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name="Valeur de sortie (HT, sur la fenêtre)")
    part_valeur_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Part individuelle de la valeur totale (%)')
    rang = models.PositiveIntegerField(
        default=0, verbose_name='Rang (1 = plus grosse valeur)')
    fenetre_mois = models.PositiveSmallIntegerField(
        default=12, verbose_name="Fenêtre d'analyse (mois)")
    calcule_le = models.DateTimeField(
        auto_now=True, verbose_name='Calculé le')

    class Meta:
        verbose_name = 'Classification ABC'
        verbose_name_plural = 'Classifications ABC'
        ordering = ['rang']

    def __str__(self):
        return f'{self.produit_id} = {self.classe}'


class PolitiqueStock(TenantModel):
    """NTSCM6 — politique de stock d'un produit (min/max, ROP, stock de
    sécurité), une par produit.

    ``classe_abc`` est un SNAPSHOT (copié depuis ``ClassificationABC`` au
    dernier recalcul, jamais recalculé ici directement). ``service_level_pct``
    est initialisé selon la classe (A=95/B=90/C=85, voir
    ``services.SERVICE_LEVEL_PAR_CLASSE``) mais reste ÉDITABLE — un recalcul
    ultérieur ne l'écrase jamais si déjà personnalisé. ``point_commande``
    (ROP) et ``stock_securite_calcule`` sont dérivés, écrits UNIQUEMENT par
    ``services.recalculer_politiques_stock`` (NTSCM5/6). ``stock_min``/
    ``stock_max`` restent des cibles ÉDITABLES par l'acheteur (aucune formule
    du plan ne les dérive). ``stock_securite_manuel`` (override acheteur)
    prime toujours sur ``stock_securite_calcule`` quand renseigné."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='scm_politiques_stock', verbose_name='Société')
    produit = models.OneToOneField(
        'stock.Produit',
        on_delete=models.CASCADE,
        related_name='scm_politique_stock', verbose_name='Produit')
    classe_abc = models.CharField(
        max_length=1, blank=True, default='',
        verbose_name='Classe ABC (snapshot)')
    service_level_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('95'),
        verbose_name='Niveau de service (%)')
    stock_min = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Stock min')
    stock_max = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Stock max')
    point_commande = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Point de commande (ROP)',
        help_text='Dérivé : conso_moy × délai fournisseur moyen + stock de sécurité.')
    stock_securite_calcule = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Stock de sécurité calculé')
    stock_securite_manuel = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Stock de sécurité (override manuel)',
        help_text='Prime toujours sur le calculé quand renseigné.')
    revise_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Révisé le')

    class Meta:
        verbose_name = 'Politique de stock'
        verbose_name_plural = 'Politiques de stock'
        ordering = ['produit_id']

    def __str__(self):
        return f'{self.produit_id} ROP={self.point_commande}'


class CyclePlanificationSOP(TenantModel):
    """NTSCM12 — cycle de planification S&OP mensuel (demande/offre/finance).

    Machine à états SÉQUENTIELLE : ``services.avancer_statut_cycle`` est
    l'UNIQUE chemin d'écriture de ``statut`` (jamais un ``PATCH`` direct côté
    API, voir ``serializers.py``) et refuse toute tentative de sauter une
    étape. Un retour en arrière n'existe que via ``services.reouvrir_cycle``
    (réouverture admin EXPLICITE, journalisée). L'historique des transitions
    est conservé via ``records.services.log_field_change`` — primitive
    plateforme réutilisée, JAMAIS un nouveau modèle ``*Activity``."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        REVUE_DEMANDE = 'revue_demande', 'Revue de la demande'
        REVUE_OFFRE = 'revue_offre', "Revue de l'offre"
        REVUE_FINANCE = 'revue_finance', 'Revue financière'
        REUNION_RECONCILIATION = 'reunion_reconciliation', 'Réunion de réconciliation'
        APPROUVE = 'approuve', 'Approuvé'
        CLOS = 'clos', 'Clos'

    # Ordre séquentiel imposé — ``prochain_statut`` s'appuie UNIQUEMENT sur
    # cette liste (jamais une comparaison de libellé).
    STATUT_ORDER = [
        Statut.BROUILLON, Statut.REVUE_DEMANDE, Statut.REVUE_OFFRE,
        Statut.REVUE_FINANCE, Statut.REUNION_RECONCILIATION, Statut.APPROUVE,
        Statut.CLOS,
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='scm_cycles_sop', verbose_name='Société')
    periode = models.CharField(max_length=7, verbose_name='Période (YYYY-MM)')
    statut = models.CharField(
        max_length=24, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    date_reunion = models.DateField(
        null=True, blank=True, verbose_name='Date de la réunion')
    anime_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='scm_cycles_sop_animes', verbose_name='Animé par')
    notes_reunion = models.TextField(
        blank=True, default='', verbose_name='Notes de réunion')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Cycle de planification S&OP'
        verbose_name_plural = 'Cycles de planification S&OP'
        ordering = ['-periode']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'periode'], name='uniq_scm_cycle_sop_periode'),
        ]

    def save(self, *args, **kwargs):
        _valider_periode(self.periode)
        super().save(*args, **kwargs)

    def prochain_statut(self):
        """Étape suivante dans :data:`STATUT_ORDER`, ou ``None`` si déjà à
        l'étape finale (``clos``)."""
        idx = self.STATUT_ORDER.index(self.statut)
        if idx + 1 >= len(self.STATUT_ORDER):
            return None
        return self.STATUT_ORDER[idx + 1]

    def __str__(self):
        return f'S&OP {self.periode} ({self.get_statut_display()})'

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
        on_delete=models.CASCADE,  # on_delete: composition — une donnee de planification n'a aucun sens sans son produit
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
        on_delete=models.CASCADE,  # on_delete: composition — une donnee de planification n'a aucun sens sans son produit
        null=True, blank=True,
        related_name='scm_evenements_demande', verbose_name='Produit',
        help_text='Vide = tous les produits de la catégorie (ou toute la société si catégorie aussi vide).')
    categorie = models.ForeignKey(
        'stock.Categorie',
        on_delete=models.CASCADE,  # on_delete: composition — l'evenement de demande ne vise que cette categorie
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
        on_delete=models.CASCADE,  # on_delete: composition — une donnee de planification n'a aucun sens sans son produit
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
        constraints = [
            # `selectors.classifier_abc` fait un update_or_create(company,
            # produit) : sans cette contrainte, deux recalculs concurrents
            # creent DEUX lignes pour le meme produit (garde
            # check_get_or_create).
            models.UniqueConstraint(
                fields=['company', 'produit'],
                name='scm_classificationabc_co_produit_uniq'),
        ]

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
        on_delete=models.CASCADE,  # on_delete: composition — une donnee de planification n'a aucun sens sans son produit
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
        constraints = [
            # `services.recalculer_politiques_stock` fait un
            # get_or_create(company, produit) : meme raison que ci-dessus.
            models.UniqueConstraint(
                fields=['company', 'produit'],
                name='scm_politiquestock_co_produit_uniq'),
        ]

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


class LigneDemandeSOP(TenantModel):
    """NTSCM13 — snapshot GELÉ de la demande consensuelle d'un produit pour
    un cycle S&OP.

    ``quantite_prevision_systeme`` est copiée depuis ``PrevisionDemande`` au
    moment du gel (``services.geler_previsions_cycle``, appelé
    AUTOMATIQUEMENT au passage brouillon -> revue_demande) — IMMUABLE
    ensuite : modifier ``PrevisionDemande`` après coup n'affecte plus cette
    ligne. Seul un ajustement commercial EXPLICITE et MOTIVÉ
    (``quantite_ajustee_commercial``/``motif_ajustement``) peut la faire
    dévier ; ``quantite_finale`` (calculée, stockée pour être filtrable/
    triable) vaut l'ajustée si renseignée, sinon la système."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='scm_lignes_demande_sop', verbose_name='Société')
    cycle = models.ForeignKey(
        CyclePlanificationSOP,
        on_delete=models.CASCADE,  # on_delete: composition — une ligne S&OP n'existe que dans son cycle
        related_name='lignes_demande', verbose_name='Cycle S&OP')
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.CASCADE,  # on_delete: composition — une donnee de planification n'a aucun sens sans son produit
        related_name='scm_lignes_demande_sop', verbose_name='Produit')
    quantite_prevision_systeme = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Quantité prévision système (gelée)')
    quantite_ajustee_commercial = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Quantité ajustée (commercial)')
    motif_ajustement = models.TextField(
        blank=True, default='', verbose_name="Motif de l'ajustement")
    quantite_finale = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Quantité finale',
        help_text='Ajustée si renseignée, sinon système — recalculée à chaque save().')

    class Meta:
        verbose_name = 'Ligne de demande S&OP'
        verbose_name_plural = 'Lignes de demande S&OP'
        ordering = ['cycle_id', 'produit_id']
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'produit'], name='uniq_scm_ligne_demande_sop_produit'),
        ]

    def save(self, *args, **kwargs):
        self.quantite_finale = (
            self.quantite_ajustee_commercial
            if self.quantite_ajustee_commercial is not None
            else self.quantite_prevision_systeme
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.cycle_id} / {self.produit_id} = {self.quantite_finale}'


class LigneOffreSOP(TenantModel):
    """NTSCM14 — snapshot de l'offre (capacité) d'un produit pour un cycle
    S&OP, en miroir de ``LigneDemandeSOP`` (NTSCM13).

    Peuplée par ``services.calculer_offre_cycle`` depuis
    ``apps.stock.selectors`` (stock disponible + quantité déjà en commande
    fournisseur — jamais une duplication de logique, jamais un import de
    modèle ``apps.stock``). ``ecart_offre_demande`` = offre totale
    (``stock_disponible_snapshot + capacite_appro_fournisseur_estimee``) −
    ``LigneDemandeSOP.quantite_finale`` du même produit — négatif = pénurie
    prévisible."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='scm_lignes_offre_sop', verbose_name='Société')
    cycle = models.ForeignKey(
        CyclePlanificationSOP,
        on_delete=models.CASCADE,  # on_delete: composition — une ligne S&OP n'existe que dans son cycle
        related_name='lignes_offre', verbose_name='Cycle S&OP')
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.CASCADE,  # on_delete: composition — une donnee de planification n'a aucun sens sans son produit
        related_name='scm_lignes_offre_sop', verbose_name='Produit')
    stock_disponible_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Stock disponible (snapshot)')
    capacite_appro_fournisseur_estimee = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Capacité appro fournisseur estimée',
        help_text='Quantité déjà en commande (BCF brouillon/envoyé) chez un fournisseur.')
    ecart_offre_demande = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Écart offre − demande',
        help_text='Négatif = pénurie prévisible sur ce produit pour ce cycle.')

    class Meta:
        verbose_name = 'Ligne d\'offre S&OP'
        verbose_name_plural = 'Lignes d\'offre S&OP'
        ordering = ['ecart_offre_demande', 'produit_id']
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'produit'], name='uniq_scm_ligne_offre_sop_produit'),
        ]

    def __str__(self):
        return f'{self.cycle_id} / {self.produit_id} écart={self.ecart_offre_demande}'


class ParametresSCM(TenantModel):
    """NTSCM22/33 — réglages SCM par société (singleton, OneToOne).

    ADAPTATION DE PÉRIMÈTRE (frontière cross-app, CLAUDE.md) : le plan
    d'origine (NTSCM22) posait ``sop_actif``/``animateur_sop`` sur
    ``apps.parametres.CompanyProfile`` — hors périmètre de cette lane
    (``apps/parametres`` n'appartient pas à ``apps/scm``). Posés ICI, en
    OneToOne société — même patron d'adaptation que ``ClassificationABC``
    (NTSCM4, voir sa docstring).

    NTSCM33 enrichit CE modèle (migration additive, comme annoncé par la
    docstring d'origine) : les constantes en dur de NTSCM6/15
    (``services.SERVICE_LEVEL_PAR_CLASSE``,
    ``selectors.SEUIL_ALERTE_ECART_CA_PCT``) sont remplacées par une lecture
    de ces champs via ``selectors.parametres(company)``, avec repli sur les
    MÊMES valeurs par défaut si la ligne n'existe pas encore (créée
    paresseusement, ``services.parametres_scm``) — aucune régression pour une
    société qui n'a jamais rien configuré.

    ``seuil_ecart_delai_pct`` (NTSCM11) et ``seuil_alerte_score_fournisseur_pts``
    (NTSCM23) sont stockés dès maintenant (champs prêts, mêmes défauts que le
    plan) mais SANS consommateur pour l'instant : NTSCM11 (délai fournisseur
    mesuré vs promis) vit dans ``apps.stock`` — hors périmètre de cette lane —
    et NTSCM23 (score fournisseur dégradé) n'existe pas encore dans
    ``docs/plans/PLAN_SUPPLY.md``. Un futur task les raccordera sans nouvelle
    migration."""

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='scm_parametres', verbose_name='Société')
    sop_actif = models.BooleanField(
        default=False, verbose_name='Cycle S&OP automatique actif',
        help_text=(
            "Désactivé par défaut : n'affecte AUCUNE société existante tant "
            'que non activé explicitement (NTSCM22).'))
    animateur_sop = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='scm_animateur_sop_defaut',
        verbose_name='Animateur S&OP par défaut',
        help_text="Notifié à l'ouverture automatique du cycle du mois suivant.")
    # NTSCM33 — horizon par défaut de génération des prévisions (NTSCM2),
    # utilisé quand l'appelant (action `generer`, tâche beat mensuelle) ne
    # précise pas explicitement `horizon_mois`.
    horizon_prevision_mois_defaut = models.PositiveSmallIntegerField(
        default=3, verbose_name='Horizon de prévision par défaut (mois)')
    # NTSCM33 — niveaux de service par défaut PAR CLASSE ABC (NTSCM6),
    # remplace `services.SERVICE_LEVEL_PAR_CLASSE` codé en dur. Appliqués
    # UNIQUEMENT à la création d'une PolitiqueStock (jamais un recalcul
    # n'écrase un niveau déjà personnalisé — même contrat qu'avant).
    service_level_defaut_a_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('95'),
        verbose_name='Niveau de service par défaut — classe A (%)')
    service_level_defaut_b_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('90'),
        verbose_name='Niveau de service par défaut — classe B (%)')
    service_level_defaut_c_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('85'),
        verbose_name='Niveau de service par défaut — classe C (%)')
    # NTSCM33 — seuil d'écart délai fournisseur (NTSCM11, apps.stock, pas
    # encore bâti) : champ prêt, sans consommateur pour l'instant.
    seuil_ecart_delai_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20'),
        verbose_name='Seuil d\'alerte écart délai fournisseur (%)')
    # NTSCM33 — seuil d'alerte score fournisseur (NTSCM23, pas encore au
    # plan) : champ prêt, sans consommateur pour l'instant.
    seuil_alerte_score_fournisseur_pts = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('15'),
        verbose_name='Seuil d\'alerte score fournisseur (points)')
    # NTSCM33 — remplace `selectors.SEUIL_ALERTE_ECART_CA_PCT` codé en dur
    # (NTSCM15, impact financier du cycle S&OP).
    seuil_alerte_ecart_financier_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('15'),
        verbose_name='Seuil d\'alerte écart financier CA prévisionnel (%)')
    # NTSCM36 — rétention des PrevisionDemande (mois), tâche de purge
    # planifiée mensuelle (`tasks.purger_donnees_scm_anciennes`).
    retention_previsions_mois = models.PositiveSmallIntegerField(
        default=24, verbose_name='Rétention des prévisions (mois)')
    # NTSCM45 — seuil d'alerte MAPE mensuel (`selectors.precision_prevision`,
    # NTSCM24) déclenchant une notification ciblée (`tasks.
    # notifier_ecarts_prevision_importants`). Absent de la liste NTSCM33
    # d'origine — ajouté ici, additif, même modèle singleton.
    seuil_alerte_mape_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('40'),
        verbose_name="Seuil d'alerte écart de prévision — MAPE (%)")

    class Meta:
        verbose_name = 'Paramètres SCM'
        verbose_name_plural = 'Paramètres SCM'

    def __str__(self):
        return f'Paramètres SCM — société {self.company_id}'

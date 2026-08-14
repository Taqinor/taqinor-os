"""Groupe NTWMS — couche ENTREPÔT professionnelle de l'app ``stock``.

Regroupe les modèles WMS que `stock` POSSÈDE (vagues de prélèvement, unités
logistiques/SSCC, quais et rendez-vous transporteur, expéditions, plans de
comptage tournant) pour ne pas alourdir le ``models.py`` historique — même
pratique que ``installations/models_kitting.py``. ``models.py`` les ré-importe
en fin de fichier, donc Django les enregistre normalement sous l'app ``stock``.

CE QUI N'EST **PAS** ICI, ET NE LE SERA JAMAIS
----------------------------------------------
La hiérarchie de casiers zone/allée/casier (``BinLocation``/``BinAffectation``,
FG319), les règles de rangement (``RegleRangement``/``CategorieStockage``,
ZSTK9), le put-away (``PutAway``, FG320) et les bons de prélèvement par
chantier (``PickList``, FG321) existent DÉJÀ dans ``installations``. Ce module
ne les duplique pas : il les référence en STRING-FK et les lit via
``apps.installations.selectors``. Un modèle parallèle serait la dette n°1
identifiée par le fondateur.

Règles respectées : multi-tenant via ``core.models.TenantModel`` ; numérotation
via ``core.numbering`` (jamais ``count()+1``) ; cross-app en STRING-FK
uniquement.
"""
import secrets

from django.conf import settings
from django.db import models

from core.models import TenantModel


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS4 — Vagues et bons de picking optimisés (wave picking)
# ═══════════════════════════════════════════════════════════════════════════

class VaguePicking(TenantModel):
    """Vague de prélèvement MULTI-SOURCE.

    Là où ``installations.PickList`` (FG321) sort le matériel d'UN chantier,
    une vague regroupe les besoins de PLUSIEURS sources (chantiers, commandes)
    en une seule tournée de magasin, ordonnée par le parcours physique.
    Référence ``VAG-YYYYMM-NNNN`` race-safe (``core.numbering``).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        LANCEE = 'lancee', 'Lancée'
        TERMINEE = 'terminee', 'Terminée'

    reference = models.CharField(max_length=50)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    note = models.TextField(blank=True, null=True)
    date_lancement = models.DateTimeField(null=True, blank=True)
    date_cloture = models.DateTimeField(null=True, blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vagues_picking_creees')

    class Meta:
        verbose_name = 'Vague de prélèvement'
        verbose_name_plural = 'Vagues de prélèvement'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='stock_vaguepicking_company_reference_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_vaguepick_co_statut'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.statut})'

    @property
    def est_terminee(self):
        """Vrai quand toutes les lignes sont servies (jamais un état déduit
        du seul statut : la vérité vient des lignes)."""
        lignes = list(self.lignes.all())
        if not lignes:
            return False
        return all(ligne.quantite_prelevee >= ligne.quantite_demandee
                   for ligne in lignes)


class LignePicking(TenantModel):
    """Ligne d'une vague : un produit à prélever, sa source, son casier.

    ``ordre_parcours`` est calculé à la création (tri zone → allée → casier du
    casier résolu, NTWMS3) : la liste servie au magasinier suit le magasin, pas
    l'ordre de saisie.
    """

    vague = models.ForeignKey(
        VaguePicking, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='lignes_picking')  # on_delete: PROTECT — une ligne prélevée est une trace d'exécution magasin ; aligné sur MouvementStock/LigneInventaire
    quantite_demandee = models.PositiveIntegerField(default=0)
    quantite_prelevee = models.PositiveIntegerField(default=0)
    # Casier SOURCE — string-FK vers la hiérarchie FG319 (jamais dupliquée).
    bin = models.ForeignKey(
        'installations.BinLocation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes_picking')
    lot = models.ForeignKey(
        'stock.LotEntrepot', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes_picking')
    # Sources possibles de la demande (string-FK cross-app).
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes_picking')
    bon_commande = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes_picking')
    ordre_parcours = models.PositiveIntegerField(default=1000)

    class Meta:
        verbose_name = 'Ligne de prélèvement'
        verbose_name_plural = 'Lignes de prélèvement'
        ordering = ['ordre_parcours', 'id']
        indexes = [
            models.Index(fields=['company', 'vague'],
                         name='idx_lignepick_co_vague'),
        ]

    def __str__(self):
        return f'{self.produit_id} × {self.quantite_demandee}'

    @property
    def reste_a_prelever(self):
        return max(self.quantite_demandee - self.quantite_prelevee, 0)


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS6 — Unités logistiques : colis, palette, SSCC
# ═══════════════════════════════════════════════════════════════════════════

class UniteLogistique(TenantModel):
    """Colis ou palette ADRESSABLE, porteur d'un SSCC GS1 (18 chiffres).

    Étend le colisage FG322 (``installations.Colis``, contrôle avant départ)
    en objet adressable et hiérarchique : une PALETTE (``parent``) regroupe
    plusieurs COLIS, chaque colis regroupe des lignes issues du picking
    (NTWMS4). Le SSCC est calculé en stdlib (clé de contrôle GS1 mod-10) —
    aucune dépendance externe.

    ``sceller()`` (service) FIGE le contenu : après scellage, aucune ligne ne
    peut plus être ajoutée ni modifiée.
    """

    class TypeUnite(models.TextChoices):
        COLIS = 'colis', 'Colis'
        PALETTE = 'palette', 'Palette'

    class Statut(models.TextChoices):
        EN_PREPARATION = 'en_preparation', 'En préparation'
        SCELLE = 'scelle', 'Scellé'
        EXPEDIE = 'expedie', 'Expédié'

    type_unite = models.CharField(
        max_length=10, choices=TypeUnite.choices, default=TypeUnite.COLIS)
    sscc = models.CharField(
        max_length=18,
        help_text='Serial Shipping Container Code GS1 (18 chiffres, clé de '
                  'contrôle mod-10 incluse).')
    # Hiérarchie : une palette contient des colis (self-FK, nullable).
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='enfants',
        help_text='Palette contenante (vide = unité de premier niveau).')
    vague = models.ForeignKey(
        VaguePicking, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='unites_logistiques',
        help_text='Vague de prélèvement d\'origine (NTWMS4), si applicable.')
    poids_kg = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True)
    dimensions = models.CharField(
        max_length=60, blank=True, default='',
        help_text='L × l × h en cm, texte libre (ex. « 120 × 80 × 145 »).')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.EN_PREPARATION)
    date_scellage = models.DateTimeField(null=True, blank=True)
    scelle_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='unites_logistiques_scellees')

    class Meta:
        verbose_name = 'Unité logistique'
        verbose_name_plural = 'Unités logistiques'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'sscc'],
                name='stock_unitelogistique_company_sscc_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_unitelog_co_statut'),
        ]

    def __str__(self):
        return f'{self.get_type_unite_display()} {self.sscc}'

    @property
    def est_figee(self):
        """Une unité scellée ou expédiée ne peut plus changer de contenu."""
        return self.statut in (self.Statut.SCELLE, self.Statut.EXPEDIE)


class UniteLogistiqueLigne(TenantModel):
    """Ligne de contenu d'une unité logistique (produit + quantité + lot)."""

    unite = models.ForeignKey(
        UniteLogistique, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='lignes_unite_logistique')  # on_delete: PROTECT — contenu réel d'un colis expédié, conservé pour la traçabilité (aligné sur LignePicking/MouvementStock)
    quantite = models.PositiveIntegerField(default=0)
    lot = models.ForeignKey(
        'stock.LotEntrepot', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes_unite_logistique')
    ligne_picking = models.ForeignKey(
        LignePicking, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_unite_logistique',
        help_text='Ligne de vague d\'origine (NTWMS4), si applicable.')
    # NTWMS11 — audit du contrôle de conformité au poste d'emballage : QUI a
    # scanné ce contenu, et QUAND. Vides = ligne saisie sans scan (comportement
    # historique conservé).
    scanne_le = models.DateTimeField(null=True, blank=True)
    scanne_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lignes_unite_logistique_scannees')

    class Meta:
        verbose_name = 'Ligne d\'unité logistique'
        verbose_name_plural = 'Lignes d\'unité logistique'
        ordering = ['id']
        indexes = [
            models.Index(fields=['company', 'unite'],
                         name='idx_unitelogl_co_unite'),
        ]

    def __str__(self):
        return f'{self.produit_id} × {self.quantite}'


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS7 — Quais de réception/expédition & créneaux transporteur
# ═══════════════════════════════════════════════════════════════════════════

class Quai(TenantModel):
    """Quai physique de réception et/ou d'expédition d'un entrepôt."""

    class TypeQuai(models.TextChoices):
        RECEPTION = 'reception', 'Réception'
        EXPEDITION = 'expedition', 'Expédition'
        MIXTE = 'mixte', 'Mixte'

    nom = models.CharField(max_length=80)
    type_quai = models.CharField(
        max_length=20, choices=TypeQuai.choices, default=TypeQuai.MIXTE)
    emplacement = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.CASCADE,
        related_name='quais')
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Quai'
        verbose_name_plural = 'Quais'
        ordering = ['nom']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'nom'], name='stock_quai_company_nom_uniq'),
        ]

    def __str__(self):
        return self.nom


class RendezVousTransporteur(TenantModel):
    """Créneau réservé par un transporteur sur un quai.

    INVARIANT SERVEUR : deux rendez-vous NON annulés ne peuvent pas se
    chevaucher sur le MÊME quai. La garde vit dans ``save()`` (jamais
    seulement dans ``clean()`` : un ``objects.create()`` ou un import en masse
    doit être refusé de la même façon), doublée d'une contrainte de base
    ``fin > début``.
    """

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        ARRIVE = 'arrive', 'Arrivé'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'
        NO_SHOW = 'no_show', 'Non présenté'
        ANNULE = 'annule', 'Annulé'

    # Un rendez-vous ANNULÉ libère son créneau ; tous les autres l'occupent.
    STATUTS_OCCUPANTS = (
        Statut.PLANIFIE, Statut.ARRIVE, Statut.EN_COURS, Statut.TERMINE,
        Statut.NO_SHOW,
    )

    quai = models.ForeignKey(
        Quai, on_delete=models.CASCADE, related_name='rendez_vous')
    # String-FK cross-app : le référentiel transporteur vit dans installations
    # (FG324), jamais dupliqué ici.
    transporteur = models.ForeignKey(
        'installations.Transporteur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rendez_vous_quai')
    reference_livraison = models.ForeignKey(
        'installations.Livraison', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rendez_vous_quai')
    date_heure_debut = models.DateTimeField()
    date_heure_fin = models.DateTimeField()
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.PLANIFIE)
    chauffeur_nom = models.CharField(max_length=120, blank=True, default='')
    immatriculation = models.CharField(max_length=30, blank=True, default='')
    note = models.TextField(blank=True, null=True)
    date_arrivee = models.DateTimeField(null=True, blank=True)
    # NTWMS8 — code remis au chauffeur pour s'enregistrer au kiosque de quai
    # SANS compte ERP. Généré côté serveur, imprévisible (secrets), unique par
    # société. Il ne donne accès à RIEN d'autre que la confirmation d'arrivée
    # et le numéro de quai assigné.
    code_checkin = models.CharField(max_length=12, blank=True, default='')

    class Meta:
        verbose_name = 'Rendez-vous transporteur'
        verbose_name_plural = 'Rendez-vous transporteur'
        ordering = ['date_heure_debut', 'id']
        constraints = [
            models.CheckConstraint(
                check=models.Q(date_heure_fin__gt=models.F('date_heure_debut')),
                name='stock_rdvtransporteur_fin_apres_debut'),
            # NTWMS8 — le code de check-in est unique PAR SOCIÉTÉ (condition
            # sur code non vide : les rendez-vous historiques sans code ne
            # s'entre-bloquent pas).
            models.UniqueConstraint(
                fields=['company', 'code_checkin'],
                condition=~models.Q(code_checkin=''),
                name='stock_rdvtransporteur_code_checkin_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'quai', 'date_heure_debut'],
                         name='idx_rdvquai_co_quai_debut'),
        ]

    def __str__(self):
        return f'{self.quai_id} — {self.date_heure_debut:%Y-%m-%d %H:%M}'

    def chevauchements(self):
        """Rendez-vous OCCUPANTS du même quai qui recouvrent ce créneau."""
        if not (self.date_heure_debut and self.date_heure_fin):
            return RendezVousTransporteur.objects.none()
        qs = (RendezVousTransporteur.objects
              .filter(quai_id=self.quai_id,
                      statut__in=self.STATUTS_OCCUPANTS,
                      date_heure_debut__lt=self.date_heure_fin,
                      date_heure_fin__gt=self.date_heure_debut))
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs

    @staticmethod
    def generer_code_checkin():
        """Code court IMPRÉVISIBLE remis au chauffeur (NTWMS8).

        Alphabet sans caractères ambigus (ni O/0, ni I/1) : il est lu à voix
        haute ou tapé sur une tablette de quai. ``secrets`` (jamais ``random``)
        parce qu'il autorise une écriture depuis un endpoint PUBLIC.
        """
        alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        return ''.join(secrets.choice(alphabet) for _ in range(8))

    def save(self, *args, **kwargs):
        if not (self.code_checkin or '').strip():
            self.code_checkin = self.generer_code_checkin()
        if (self.date_heure_debut and self.date_heure_fin
                and self.date_heure_fin <= self.date_heure_debut):
            raise ValueError(
                'La fin du rendez-vous doit être postérieure à son début.')
        if (self.statut in self.STATUTS_OCCUPANTS
                and self.chevauchements().exists()):
            raise ValueError(
                'Ce créneau chevauche un rendez-vous déjà planifié sur ce '
                'quai.')
        return super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS9 — Expédition multi-transporteurs (étiquette réelle, GATED)
# ═══════════════════════════════════════════════════════════════════════════

class ExpeditionTransporteur(TenantModel):
    """Expédition d'UNE unité logistique par UN transporteur.

    Le connecteur (``transporteur_provider``) est résolu via
    ``apps/stock/providers/`` (Strategy pattern posé sur ``core.integrations``).
    Sans intégration configurée pour la société, le connecteur ``aucun``
    (NoOp) produit une étiquette interne SANS aucun appel réseau — dégradation
    gracieuse, jamais un blocage.

    Structure ce que ``installations.Livraison.numero_suivi`` ne fait qu'en
    texte libre : ici le suivi est un OBJET (coût réel, étiquette PDF stockée,
    statut) — pour le e-commerce/B2B pur, hors chantier.
    """

    class Provider(models.TextChoices):
        AUCUN = 'aucun', 'Aucun (étiquette interne)'
        AMANA = 'amana', 'Amana'
        DHL = 'dhl', 'DHL'
        CHRONOPOST = 'chronopost', 'Chronopost'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ETIQUETTE = 'etiquette', 'Étiquette générée'
        EXPEDIE = 'expedie', 'Expédié'
        LIVRE = 'livre', 'Livré'
        ANNULE = 'annule', 'Annulé'

    unite_logistique = models.ForeignKey(
        UniteLogistique, on_delete=models.CASCADE, related_name='expeditions')
    transporteur_provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.AUCUN)
    # Référentiel transporteur interne (FG324) — string-FK, optionnel.
    transporteur = models.ForeignKey(
        'installations.Transporteur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='expeditions_stock')
    numero_suivi = models.CharField(max_length=120, blank=True, default='')
    cout_reel = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    # Clé objet MinIO (bucket uploads), préfixée par société (SCA42) — jamais
    # un FileField brut (règle plateforme ARC26).
    etiquette_pdf_key = models.CharField(
        max_length=500, blank=True, default='')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    destination = models.CharField(max_length=200, blank=True, default='')
    date_expedition = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Expédition transporteur'
        verbose_name_plural = 'Expéditions transporteur'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_expedtr_co_statut'),
            models.Index(fields=['company', 'numero_suivi'],
                         name='idx_expedtr_co_suivi'),
        ]

    def __str__(self):
        return f'{self.transporteur_provider} {self.numero_suivi}'.strip()

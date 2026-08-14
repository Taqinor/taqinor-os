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
from django.utils import timezone

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

    # NTWMS12 — stratégie de LIBÉRATION. MANUEL (défaut) = comportement
    # historique strict : la vague ne part que sur clic.
    class ModeLiberation(models.TextChoices):
        MANUEL = 'manuel', 'Manuel'
        AUTO_HEURE = 'auto_heure', 'Automatique à l\'heure de coupure'
        AUTO_SEUIL = 'auto_seuil', 'Automatique au seuil de lignes'

    reference = models.CharField(max_length=50)
    mode_liberation = models.CharField(
        max_length=20, choices=ModeLiberation.choices,
        default=ModeLiberation.MANUEL)
    seuil_lignes = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='NTWMS12 — nombre de lignes déclenchant la libération en '
                  'mode AUTO_SEUIL. Vide = jamais déclenché.')
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
        VaguePicking, on_delete=models.CASCADE,  # on_delete: CASCADE - une ligne n'existe QUE dans sa vague (composition stricte, aucune valeur orpheline)
        related_name='lignes')
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
    # NTWMS25 — casier où l'unité se trouve PHYSIQUEMENT (string-FK FG319).
    # Vide = position non suivie (comportement historique inchangé).
    bin_actuel = models.ForeignKey(
        'installations.BinLocation', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='unites_logistiques')
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
        UniteLogistique, on_delete=models.CASCADE,  # on_delete: CASCADE - le contenu n'existe QUE dans son colis (composition stricte)
        related_name='lignes')
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
        'stock.EmplacementStock', on_delete=models.CASCADE,  # on_delete: CASCADE - un quai est une partie physique de son entrepot ; sans entrepot il n'a aucun sens
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
        Quai, on_delete=models.CASCADE,  # on_delete: CASCADE - un creneau ne survit pas a la suppression du quai qu'il reserve
        related_name='rendez_vous')
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
        UniteLogistique, on_delete=models.CASCADE,  # on_delete: CASCADE - une expedition n'expedie qu'une unite ; sans elle elle n'a plus d'objet
        related_name='expeditions')
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


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS13 — Comptage tournant ABC récurrent (cycle counting)
# ═══════════════════════════════════════════════════════════════════════════

class PlanComptageTournant(TenantModel):
    """Fréquence de recomptage d'une CLASSE ABC de produits.

    Le comptage tournant remplace l'inventaire annuel « tout d'un coup » par un
    recomptage CONTINU : les articles de classe A (les 20 % de la valeur de
    rotation) sont recomptés souvent, les C rarement. Ce plan génère
    automatiquement des ``InventaireSession`` CIBLÉES (commande
    ``generer_comptages_tournants``) — jamais un mécanisme d'inventaire
    parallèle : c'est la session existante qui est produite.
    """

    class ClasseAbc(models.TextChoices):
        A = 'A', 'A — forte rotation'
        B = 'B', 'B — rotation moyenne'
        C = 'C', 'C — faible rotation'

    # Fréquences par défaut (jours) — configurables par société.
    FREQUENCES_DEFAUT = {'A': 30, 'B': 90, 'C': 180}

    classe_abc = models.CharField(max_length=1, choices=ClasseAbc.choices)
    frequence_jours = models.PositiveIntegerField(default=30)
    actif = models.BooleanField(default=True)
    date_dernier_comptage = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Plan de comptage tournant'
        verbose_name_plural = 'Plans de comptage tournant'
        ordering = ['classe_abc']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'classe_abc'],
                name='stock_plancomptage_company_classe_uniq'),
        ]

    def __str__(self):
        return f'Classe {self.classe_abc} — tous les {self.frequence_jours} j'

    def est_du(self, a_la_date):
        """Vrai si un comptage de cette classe est DÛ à la date fournie.

        Jamais compté = toujours dû. La date est toujours FOURNIE par
        l'appelant (le service/la commande) : ce modèle ne lit pas l'horloge.
        """
        import datetime

        if not self.actif:
            return False
        if self.date_dernier_comptage is None:
            return True
        echeance = self.date_dernier_comptage + datetime.timedelta(
            days=self.frequence_jours or 0)
        return a_la_date >= echeance


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS15 — Cross-dock : de la réception à l'expédition, sans passer en stock
# ═══════════════════════════════════════════════════════════════════════════

class AffectationCrossDock(TenantModel):
    """NTWMS15 — une ligne REÇUE routée DIRECTEMENT vers une expédition.

    Le cross-dock est le raccourci du magasin : la marchandise qui arrive est
    déjà attendue par une vague de prélèvement (NTWMS4), donc elle ne monte
    JAMAIS en rayon — elle va du quai de réception au colis d'expédition. Ce
    modèle est la TRACE de cette décision : tant qu'une ligne de réception
    porte une affectation, le rangement guidé (put-away NTWMS2) est
    explicitement sauté pour elle.

    FRONTIÈRE INTER-APPS. ``ReceptionFournisseur``/``LigneReceptionFournisseur``
    vivent dans ``achats`` (ODX19) : elles sont référencées en STRING-FK, et
    l'app ``achats`` n'est jamais modifiée depuis ``stock``. Le drapeau
    « cette réception est destinée au cross-dock » n'est donc pas une colonne
    de la réception mais l'EXISTENCE de ces affectations, lue par
    ``services.reception_est_cross_dock`` — même information, du bon côté de
    la frontière.
    """

    reception = models.ForeignKey(
        'achats.ReceptionFournisseur', on_delete=models.CASCADE,  # on_delete: CASCADE - une affectation ne decrit qu'une reception ; sans elle elle ne designe plus rien
        related_name='affectations_cross_dock')
    ligne_reception = models.ForeignKey(
        'achats.LigneReceptionFournisseur', on_delete=models.CASCADE,  # on_delete: CASCADE - l'affectation route UNE ligne recue ; la ligne disparue, elle est vide de sens
        related_name='affectations_cross_dock')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='affectations_cross_dock')  # on_delete: PROTECT — trace d'exécution magasin (aligné sur LignePicking/MouvementStock)
    quantite = models.PositiveIntegerField(default=0)
    unite_logistique = models.ForeignKey(
        UniteLogistique, on_delete=models.CASCADE,  # on_delete: CASCADE - le routage n'existe que par le colis d'expedition qu'il alimente
        related_name='affectations_cross_dock')
    ligne_picking = models.ForeignKey(
        LignePicking, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='affectations_cross_dock',
        help_text='Ligne de vague en attente qui a justifié le cross-dock.')

    class Meta:
        verbose_name = 'Affectation cross-dock'
        verbose_name_plural = 'Affectations cross-dock'
        ordering = ['-created_at']
        constraints = [
            # Une ligne reçue n'est routée qu'UNE fois (ré-appeler le service
            # ne duplique jamais le contenu du colis).
            models.UniqueConstraint(
                fields=['company', 'ligne_reception'],
                name='stock_crossdock_company_ligne_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'reception'],
                         name='idx_crossdock_co_reception'),
        ]

    def __str__(self):
        return f'Cross-dock {self.ligne_reception_id} → {self.unite_logistique_id}'


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS17 — Rappel produit (recall) par lot / série
# ═══════════════════════════════════════════════════════════════════════════

class AlerteRappel(TenantModel):
    """NTWMS17 — rappel fournisseur/fabricant sur un produit ou un lot.

    Un rappel devient un incident SAV quand on découvre TROP TARD où la
    marchandise est partie. Ce modèle déclenche l'inverse : dès la
    déclaration, ``services.impact_rappel`` réutilise la traçabilité NTWMS16
    pour lister EN UN CLIC le stock encore en casier ET les chantiers/clients
    déjà livrés avec ce lot.
    """

    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        CLOS = 'clos', 'Clos'

    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='alertes_rappel')  # on_delete: PROTECT — un rappel est une trace réglementaire ; il ne disparaît pas avec la fiche produit
    lot = models.ForeignKey(
        'stock.LotEntrepot', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='alertes_rappel',
        help_text='Lot concerné. Vide = le rappel porte sur TOUT le produit.')
    motif = models.TextField()
    date_declenchement = models.DateTimeField(
        default=timezone.now,
        help_text='Horodatage du déclenchement (aware, jamais naïf).')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_COURS)
    declenchee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alertes_rappel_declenchees')
    date_cloture = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Alerte de rappel produit'
        verbose_name_plural = 'Alertes de rappel produit'
        ordering = ['-date_declenchement', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_alerterappel_co_statut'),
        ]

    def __str__(self):
        return f'Rappel {self.produit_id} ({self.statut})'


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS20 — Portail 3PL : le client dépositaire consulte SON stock
# ═══════════════════════════════════════════════════════════════════════════

def _default_portail_tiers_token():
    return secrets.token_urlsafe(32)


def _default_portail_tiers_expiry():
    import datetime

    return timezone.now() + datetime.timedelta(days=90)


class PortailTiersToken(TenantModel):
    """NTWMS20 — jeton public, révocable et expirant, du portail 3PL.

    Même patron que ``PortailFournisseurToken`` (XPUR22) : long, imprévisible
    (``secrets``), révocable, expirant. La PORTÉE est ici un seul
    ``tiers_nom`` : le porteur ne voit que le stock des emplacements
    ``type_proprietaire=DE_TIERS`` portant CE nom, dans CETTE société —
    jamais le stock interne, jamais un autre dépositaire, jamais un autre
    locataire.
    """

    tiers_nom = models.CharField(
        max_length=150,
        help_text='Dépositaire propriétaire du stock (NTWMS19 : le '
                  '`tiers_nom` des emplacements DE_TIERS qu\'il possède).')
    token = models.CharField(
        max_length=64, default=_default_portail_tiers_token, editable=False)
    expires_at = models.DateTimeField(default=_default_portail_tiers_expiry)
    revoked = models.BooleanField(default=False)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='portails_tiers_crees')
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Jeton portail 3PL'
        verbose_name_plural = 'Jetons portail 3PL'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'token'],
                name='stock_portailtiers_company_token_uniq'),
        ]
        indexes = [
            models.Index(fields=['token'], name='idx_portailtiers_token'),
        ]

    def __str__(self):
        return f'Portail 3PL {self.tiers_nom} · {self.token[:8]}…'

    @property
    def est_valide(self):
        return not self.revoked and self.expires_at > timezone.now()


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS21 — Demande de transfert avec workflow d'approbation
# ═══════════════════════════════════════════════════════════════════════════

class DemandeTransfert(TenantModel):
    """NTWMS21 — demande d'approbation EN AMONT d'un transfert de valeur.

    Le ``TransfertStock`` direct existant reste le chemin normal : tant que la
    valeur reste sous le seuil de la société
    (``AchatsParametres.seuil_approbation_transfert``, 0 par défaut = garde
    désactivée, comportement historique strict), rien ne change. Au-dessus du
    seuil, le transfert direct est REFUSÉ et doit passer par ce document :
    demande → approbation d'un responsable → exécution (qui crée alors le
    ``TransfertStock`` réel, jamais un mécanisme de stock parallèle).
    """

    class Statut(models.TextChoices):
        DEMANDE = 'demande', 'Demandé'
        APPROUVE = 'approuve', 'Approuvé'
        EXECUTE = 'execute', 'Exécuté'
        REJETE = 'rejete', 'Rejeté'

    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='demandes_transfert')  # on_delete: PROTECT — document d'approbation traçable (aligné sur TransfertStock, déjà PROTECT)
    quantite = models.PositiveIntegerField(default=0)
    emplacement_source = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.PROTECT,
        related_name='demandes_transfert_source')  # on_delete: PROTECT — l'emplacement d'un document approuvé ne peut pas disparaître en silence
    emplacement_destination = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.PROTECT,
        related_name='demandes_transfert_destination')  # on_delete: PROTECT — idem source
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.DEMANDE)
    motif = models.TextField(blank=True, default='')
    # Valeur INTERNE (quantité × prix d'achat) : sert uniquement au seuil
    # d'approbation, jamais client-facing.
    valeur_estimee = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    demande_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='demandes_transfert_demandees')
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='demandes_transfert_approuvees')
    date_decision = models.DateTimeField(null=True, blank=True)
    # Transfert réellement créé à l'exécution (jamais avant).
    transfert = models.ForeignKey(
        'stock.TransfertStock', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='demandes')

    class Meta:
        verbose_name = 'Demande de transfert'
        verbose_name_plural = 'Demandes de transfert'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_demtransf_co_statut'),
        ]

    def __str__(self):
        return f'Demande {self.produit_id} × {self.quantite} ({self.statut})'


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS23 — Retours CLIENT (RMA) côté entrepôt
# ═══════════════════════════════════════════════════════════════════════════

class RetourClient(TenantModel):
    """NTWMS23 — marchandise qui REVIENT d'un client vers l'entrepôt.

    À ne pas confondre avec ``achats.RetourFournisseur``, qui part VERS le
    fournisseur : ici le flux est entrant, et la question centrale est l'état
    de ce qui revient. Le stock vendable n'est réintégré que pour les lignes
    constatées REVENDABLE — un rebut n'incrémente JAMAIS le stock.
    """

    class Statut(models.TextChoices):
        DEMANDE = 'demande', 'Demandé'
        EN_TRANSIT = 'en_transit', 'En transit'
        RECEPTIONNE = 'receptionne', 'Réceptionné'
        INSPECTE = 'inspecte', 'Inspecté'
        CLOS = 'clos', 'Clos'

    reference = models.CharField(max_length=50)
    # String-FK cross-app (crm/installations/sav) — jamais un import de leurs
    # modèles depuis stock.
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,
        related_name='retours_entrepot')  # on_delete: PROTECT — un retour est une trace logistique et comptable ; il survit à l'archivage du client
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='retours_entrepot')
    ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='retours_entrepot')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.DEMANDE)
    motif = models.TextField(blank=True, default='')
    date_reception = models.DateTimeField(null=True, blank=True)
    date_inspection = models.DateTimeField(null=True, blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='retours_client_crees')

    class Meta:
        verbose_name = 'Retour client (RMA)'
        verbose_name_plural = 'Retours client (RMA)'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='stock_retourclient_company_reference_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_retourclient_co_statut'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.statut})'


class LigneRetourClient(TenantModel):
    """Ligne d'un retour client : ce qui revient, dans quel état, et où.

    ``etat_constate`` pilote TOUT : REVENDABLE réintègre le stock vendable (au
    casier de quarantaine tant que le contrôle qualité n'a pas tranché),
    A_REPARER et REBUT ne l'incrémentent jamais. ``stock_mouvemente`` rend
    l'opération idempotente : une ligne déjà entrée en stock n'y entre pas
    deux fois, et une ligne qui devient un rebut APRÈS coup en ressort une
    seule fois.
    """

    class EtatConstate(models.TextChoices):
        REVENDABLE = 'revendable', 'Revendable'
        A_REPARER = 'a_reparer', 'À réparer'
        REBUT = 'rebut', 'Rebut'

    retour = models.ForeignKey(
        RetourClient, on_delete=models.CASCADE,  # on_delete: CASCADE - une ligne n'existe QUE dans son retour (composition stricte)
        related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='lignes_retour_client')  # on_delete: PROTECT — trace d'un mouvement de stock réel (aligné sur MouvementStock)
    quantite = models.PositiveIntegerField(default=0)
    etat_constate = models.CharField(
        max_length=20, choices=EtatConstate.choices,
        default=EtatConstate.REVENDABLE)
    # Casier de destination selon l'état (QUARANTAINE avant contrôle, zone de
    # rebut sinon) — string-FK vers la hiérarchie FG319, jamais dupliquée.
    bin = models.ForeignKey(
        'installations.BinLocation', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='lignes_retour_client')
    stock_mouvemente = models.BooleanField(default=False)
    note = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Ligne de retour client'
        verbose_name_plural = 'Lignes de retour client'
        ordering = ['id']
        indexes = [
            models.Index(fields=['company', 'retour'],
                         name='idx_ligneretcli_co_retour'),
        ]

    def __str__(self):
        return f'{self.produit_id} × {self.quantite} ({self.etat_constate})'


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS24 — Casse / freinte / mise au rebut AVEC MOTIF
# ═══════════════════════════════════════════════════════════════════════════

class MouvementRebut(TenantModel):
    """NTWMS24 — déclaration de perte MOTIVÉE, chiffrée, traçable au casier.

    L'ajustement d'inventaire générique dit COMBIEN mais jamais POURQUOI :
    une casse, une péremption, un vol et une erreur de réception se
    ressemblent toutes une fois fondues dans un ajustement. Ce document porte
    la taxonomie de motif, le casier d'origine et la valeur de la perte, et
    reste DISTINCT des ajustements d'inventaire dans tous les rapports.

    Le mouvement de stock réel est celui, existant, du service de rebut
    (``rebuter_produit``, type ``REBUT``) — jamais un second chemin
    d'écriture. ``valeur_perte`` est INTERNE (coût moyen d'achat au moment de
    la déclaration) : elle n'apparaît JAMAIS dans un document client.
    """

    class Motif(models.TextChoices):
        CASSE = 'casse', 'Casse'
        PERIME = 'perime', 'Périmé'
        VOL = 'vol', 'Vol'
        ERREUR_RECEPTION = 'erreur_reception', 'Erreur de réception'

    # Correspondance vers la taxonomie historique de `MouvementStock`
    # (XMFG11/XSTK10) : le mouvement posé reste lisible par les rapports
    # existants, sans inventer un second vocabulaire de motifs.
    MOTIF_MOUVEMENT = {
        'casse': 'casse', 'perime': 'perime', 'vol': 'vol',
        'erreur_reception': 'erreur',
    }

    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='mouvements_rebut')  # on_delete: PROTECT — pièce de suivi comptable des pertes (aligné sur MouvementStock)
    quantite = models.PositiveIntegerField(default=0)
    motif = models.CharField(max_length=20, choices=Motif.choices)
    bin = models.ForeignKey(
        'installations.BinLocation', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='mouvements_rebut',
        help_text='Casier d\'où sort la marchandise perdue.')
    valeur_perte = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='Coût moyen × quantité au moment de la déclaration '
                  '(INTERNE, jamais client-facing).')
    mouvement = models.ForeignKey(
        'stock.MouvementStock', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='rebuts_declares')
    note = models.TextField(blank=True, default='')
    declare_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mouvements_rebut_declares')

    class Meta:
        verbose_name = 'Déclaration de rebut'
        verbose_name_plural = 'Déclarations de rebut'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'motif'],
                         name='idx_mvtrebut_co_motif'),
        ]

    def __str__(self):
        return f'Rebut {self.produit_id} × {self.quantite} ({self.motif})'

"""apps.pos — Vente comptoir (point of sale) pour la vente d'accessoires.

XPOS1 : ``VenteComptoir`` + ``LigneVenteComptoir`` — une vente comptoir devient,
à la validation, une ``Facture`` légale + un/des ``Paiement`` + un mouvement de
stock (via ``ventes.services``/``stock.services`` — jamais d'import direct des
modèles de ces apps, uniquement selectors/services/FK chaîne, cf. CLAUDE.md).

XPOS4 : ``SessionCaisse`` — ouverture/clôture de caisse comptoir, adossée à la
``compta.Caisse`` EXISTANTE (FG124) via ``compta.services`` (pas de nouveau
journal d'espèces dupliqué).

XPOS3 : ``ShareLinkTicket`` — lien public tokenisé + expirant vers le PDF du
ticket de caisse (même patron que ``ventes.ShareLink``, en local à
``apps/pos`` pour ne pas toucher le modèle ``ventes``).

XPOS15 : ``CommandeRetrait`` — click-and-collect (à préparer → prêt → retiré).

XPOS18 : configuration imprimante ESC/POS + rapprochement TPE (champ additif
sur ``SessionCaisse``).
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def default_code_retrait():
    import secrets
    return secrets.token_hex(3).upper()


class VenteComptoir(models.Model):
    """Une vente comptoir (accessoires) : lignes produit + client optionnel.

    À la validation (``services.valider_vente``) elle crée la ``Facture``
    légale (facture classique sans devis, déjà supportée par ``ventes``), le/
    les ``Paiement`` (multi-modes), décrémente le stock, et applique le droit
    de timbre espèces (FG144). Le lien vers la facture créée est conservé
    (string FK, une seule direction : pos → ventes).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDEE = 'validee', 'Validée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ventes_comptoir',
    )
    reference = models.CharField(max_length=50)
    # Client optionnel (FK chaîne — pos ne connaît crm que par référence).
    client = models.ForeignKey(
        'crm.Client',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ventes_comptoir',
    )
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.BROUILLON)
    # Session de caisse active au moment de la vente (obligatoire seulement si
    # un règlement espèces est encaissé — cf. services.valider_vente / XPOS4).
    session_caisse = models.ForeignKey(
        'pos.SessionCaisse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventes',
    )
    caissier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventes_comptoir_caisse',
    )
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    # Facture légale créée à la validation (string FK — jamais d'import direct
    # du modèle facturation.Facture). ODX17 — Facture a déménagé de ventes
    # vers facturation ; même table physique (ventes_facture), FK re-pointée.
    facture = models.ForeignKey(
        'facturation.Facture',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventes_comptoir',
    )
    note = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventes_comptoir_creees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Vente comptoir'
        verbose_name_plural = 'Ventes comptoir'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference or f'VenteComptoir #{self.pk}'

    @property
    def total_ht(self):
        return sum((ligne.total_ht for ligne in self.lignes.all()), Decimal('0'))

    @property
    def total_ttc(self):
        return sum((ligne.total_ttc for ligne in self.lignes.all()), Decimal('0'))


class LigneVenteComptoir(models.Model):
    vente = models.ForeignKey(
        VenteComptoir, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.PROTECT,
        related_name='lignes_vente_comptoir',
    )
    designation = models.CharField(max_length=255)
    quantite = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    # Prix 100 % TTC (écran caisse) — la ligne facture recalculera le HT.
    prix_unitaire_ttc = models.DecimalField(max_digits=10, decimal_places=2)
    remise = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Taux TVA de la ligne (%). Vide = taux de la vente.')
    # Numéros de série saisis à la vente (XPOS9, pos-side capture — la
    # création de l'Équipement SAV reste dans sav.services). Liste JSON de
    # chaînes, vide par défaut → comportement inchangé pour un produit non
    # sérialisé.
    numeros_serie = models.JSONField(null=True, blank=True, default=list)

    class Meta:
        verbose_name = 'Ligne de vente comptoir'
        verbose_name_plural = 'Lignes de vente comptoir'

    @property
    def total_ttc(self):
        quantite = Decimal(str(self.quantite or 0))
        prix = Decimal(str(self.prix_unitaire_ttc or 0))
        remise = Decimal(str(self.remise or 0))
        return quantite * prix * (1 - remise / 100)

    @property
    def taux_tva_effectif(self):
        return self.taux_tva if self.taux_tva is not None else self.vente.taux_tva

    @property
    def total_ht(self):
        # taux_tva peut arriver en float (valeur non encore persistée) — on le
        # ramène en Decimal pour ne jamais diviser un Decimal par un float.
        taux = Decimal(str(self.taux_tva_effectif or 0))
        return (self.total_ttc / (1 + taux / 100)) if taux else self.total_ttc


def _default_share_token():
    import secrets
    return secrets.token_urlsafe(32)


def _default_share_expiry():
    from datetime import timedelta
    return timezone.now() + timedelta(days=30)


class ShareLinkTicket(models.Model):
    """Lien public tokenisé + expirant (30 j) vers le PDF du ticket de caisse
    d'une ``VenteComptoir`` (XPOS3) — même patron que ``ventes.ShareLink``,
    en local à ``apps/pos`` pour rester dans le périmètre de l'app. Jamais de
    login client, jamais de prix d'achat (le ticket ne les contient pas)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='share_links_ticket')
    token = models.CharField(
        max_length=64, unique=True, default=_default_share_token,
        editable=False)
    vente = models.ForeignKey(
        VenteComptoir, on_delete=models.CASCADE, related_name='share_links')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_share_expiry)

    class Meta:
        verbose_name = 'Lien public — ticket de caisse'
        verbose_name_plural = 'Liens publics — tickets de caisse'
        ordering = ['-created_at']
        # Pas d'index explicite supplémentaire : `token` est déjà `unique=True`
        # (index implicite) — évite tout hand-naming d'index qui dériverait du
        # nom hashé auto-généré par Django (cf. CLAUDE.md, garde migrations).

    def __str__(self):
        return f'ShareLinkTicket {self.token[:8]}… ({self.vente.reference})'

    @property
    def is_valid(self):
        return self.expires_at > timezone.now()

    @classmethod
    def for_vente(cls, vente):
        """Réutilise un lien encore valide pour cette vente, sinon en crée un."""
        link = cls.objects.filter(
            vente=vente, expires_at__gt=timezone.now()
        ).order_by('-expires_at').first()
        return link or cls.objects.create(company=vente.company, vente=vente)


# ── XPOS4 — Sessions de caisse comptoir ─────────────────────────────────────

class SessionCaisse(models.Model):
    """Ouverture/clôture de caisse comptoir avec contrôle des espèces (XPOS4).

    Adossée à la ``compta.Caisse`` existante (FG124) via ``compta.services`` —
    ne duplique pas le journal d'espèces : ``caisse_comptable_id`` est une FK
    chaîne (string FK) vers ``compta.Caisse``. Toute vente comptoir réglée en
    espèces référence la session active de sa caisse.
    """

    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        CLOTUREE = 'cloturee', 'Clôturée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='sessions_caisse_pos',
    )
    caisse_comptable = models.ForeignKey(
        'compta.Caisse',
        on_delete=models.PROTECT,
        related_name='sessions_pos',
        help_text="Caisse d'espèces compta (FG124) rattachée à cette session.",
    )
    caissier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions_caisse_pos',
    )
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERTE)
    fond_ouverture = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Fond de caisse (ouverture)')
    date_ouverture = models.DateTimeField(auto_now_add=True)
    date_cloture = models.DateTimeField(null=True, blank=True)
    # Comptage à la clôture (espèces réellement comptées).
    montant_compte_cloture = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    # XPOS18 — rapprochement TPE (terminal carte) : montant carte compté à la
    # clôture. NULL = non renseigné (aucun TPE configuré) → comportement
    # inchangé, aucun écart carte calculé.
    montant_tpe_compte = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant TPE compté (clôture)')
    ecart_tpe = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Écart TPE (compté − attendu)')
    # Écart espèces posté dans la caisse compta (mirroir de compta.ClotureCaisse
    # pour un accès rapide côté rapport Z, sans reparcourir compta).
    cloture_caisse_comptable = models.ForeignKey(
        'compta.ClotureCaisse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions_pos',
    )
    commentaire = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Session de caisse (POS)'
        verbose_name_plural = 'Sessions de caisse (POS)'
        ordering = ['-date_ouverture']

    def __str__(self):
        return f'Session #{self.pk} ({self.get_statut_display()})'

    def clean(self):
        super().clean()
        if self.fond_ouverture is not None and self.fond_ouverture < 0:
            raise ValidationError(
                'Le fond de caisse ne peut pas être négatif.')


# ── XPOS15 — Click-and-collect (retrait en magasin) ─────────────────────────

class CommandeRetrait(models.Model):
    """Commande à retirer en magasin (click-and-collect) — XPOS15.

    Workflow ERP : à préparer → prêt → retiré. Le code de retrait est vérifié
    à la remise. Le stock est décrémenté à la PRÉPARATION (via
    ``stock.services``), pas à la commande. Le paiement se fait au retrait
    (POS, XPOS6) ou en ligne (PaymentLink FG53, gated — hors scope ici).
    """

    class Statut(models.TextChoices):
        A_PREPARER = 'a_preparer', 'À préparer'
        PRET = 'pret', 'Prêt au retrait'
        RETIRE = 'retire', 'Retiré'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='commandes_retrait',
    )
    reference = models.CharField(max_length=50)
    client = models.ForeignKey(
        'crm.Client',
        on_delete=models.PROTECT,
        related_name='commandes_retrait',
    )
    # Devis accepté source, optionnel (demande e-catalogue XPOS14 sinon).
    devis = models.ForeignKey(
        'ventes.Devis',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commandes_retrait',
    )
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.A_PREPARER)
    # Code de retrait (vérifié à la remise). Généré à la création.
    code_retrait = models.CharField(
        max_length=12, blank=True, default=default_code_retrait)
    vente_comptoir = models.ForeignKey(
        VenteComptoir,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commandes_retrait',
        help_text='Encaissement comptoir associé (paiement au retrait, XPOS6).',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_pret = models.DateTimeField(null=True, blank=True)
    date_retrait = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commandes_retrait_creees',
    )

    class Meta:
        verbose_name = 'Commande retrait magasin'
        verbose_name_plural = 'Commandes retrait magasin'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference or f'CommandeRetrait #{self.pk}'


class LigneCommandeRetrait(models.Model):
    commande = models.ForeignKey(
        CommandeRetrait, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.PROTECT,
        related_name='lignes_commande_retrait',
    )
    quantite = models.DecimalField(max_digits=10, decimal_places=2, default=1)

    class Meta:
        verbose_name = 'Ligne de commande retrait'
        verbose_name_plural = 'Lignes de commande retrait'


# ── XPOS18 — Configuration matériel comptoir (imprimante réseau ESC/POS) ────

class ConfigMaterielPOS(models.Model):
    """Configuration matérielle comptoir (XPOS18) : imprimante réseau ESC/POS.

    Une configuration par société (au plus). Non configuré = tout no-op :
    aucune connexion sortante n'est jamais tentée sans IP renseignée.
    """
    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='config_materiel_pos',
    )
    imprimante_ip = models.CharField(max_length=100, blank=True, default='')
    imprimante_port = models.PositiveIntegerField(default=9100)
    imprimante_active = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Configuration matériel POS'
        verbose_name_plural = 'Configurations matériel POS'

    def __str__(self):
        return f'ConfigMaterielPOS ({self.company_id})'

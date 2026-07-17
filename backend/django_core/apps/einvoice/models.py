"""Modèles de facturation électronique DGI (Groupe NTMAR — Maroc & Afrique).

NTMAR5 — ``FactureElectronique`` porte le XML DGI généré pour une facture
``ventes.Facture`` référencée UNIQUEMENT par ``facture_id`` (PK, résolue via
``apps.ventes.selectors.get_facture_scoped`` — jamais un import de
``apps.ventes.models``) + ``facture_ref`` (référence humaine dénormalisée à la
génération, pour affichage/historique sans nouvelle lecture cross-app).

NTMAR9 — chaque régénération crée une NOUVELLE ligne avec ``version``
incrémentée (jamais d'écrasement) : le contenu original reste téléchargeable
à l'identique. ``unique_together (company, facture_id, version)``.

NTMAR7 — ``TransmissionDGI`` (file d'attente inerte tant que
``DGI_TRANSMISSION_ENABLED`` est OFF) — prête pour le jour où la DGI publie
son API Simpl (rule #1 : aucune écriture SQL directe Odoo n'est concernée ici,
ce module ne touche jamais Odoo).

Gaté par ``EINVOICE_ENABLED`` (settings, défaut OFF) — voir ``services.py``.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class FactureElectronique(TenantModel):
    """Facture électronique au schéma DGI (XML), dry-run ou réel (NTMAR5)."""

    class Format(models.TextChoices):
        UBL = 'ubl', 'UBL 2.1'
        CII = 'cii', 'CII'

    class Mode(models.TextChoices):
        DRY_RUN = 'dry_run', 'Simulation (dry-run)'
        REEL = 'reel', 'Réel'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        GENERE = 'genere', 'Généré'
        SIGNE = 'signe', 'Signé'
        TRANSMIS = 'transmis', 'Transmis'
        REJETE = 'rejete', 'Rejeté'

    # SCA4 — socle multi-société via ``TenantModel`` ; ``company`` REdéclarée
    # pour conserver un ``related_name`` explicite (motif ARC1).
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant — les e-factures d'une société disparaissent avec elle (scope multi-société)
        related_name='factures_electroniques', verbose_name='Société')

    # Facture ventes d'origine — string/int-ref UNIQUEMENT (jamais de FK réelle
    # vers apps.ventes.models, frontière cross-app CLAUDE.md).
    facture_id = models.PositiveIntegerField(
        verbose_name='ID de la facture (ventes)')
    facture_ref = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='Référence facture (dénormalisée)')

    format = models.CharField(
        max_length=6, choices=Format.choices, default=Format.UBL,
        verbose_name='Format')
    mode = models.CharField(
        max_length=8, choices=Mode.choices, default=Mode.DRY_RUN,
        verbose_name='Mode')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    # NTMAR9 — version immuable : une régénération CRÉE une nouvelle ligne
    # (jamais un update du XML existant).
    version = models.PositiveIntegerField(default=1, verbose_name='Version')

    xml_key = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name='Clé MinIO du XML')
    hash_contenu = models.CharField(
        max_length=64, blank=True, default='', verbose_name='Empreinte SHA-256')

    # NTMAR6 — scaffold de signature électronique (jamais câblé sans provider
    # réel ; voir ``EINVOICE_SIGNATURE_PROVIDER``, défaut ``noop``).
    signature_xml = models.TextField(
        blank=True, default='', verbose_name='XML de signature')
    certificat_ref = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Référence certificat')
    signe_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Signé le')

    genere_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Généré le')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,  # on_delete: garder l'e-facture si l'auteur est supprimé (traçabilité fiscale)
        null=True, blank=True,
        related_name='factures_electroniques_creees',
        verbose_name='Générée par')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Facture électronique'
        verbose_name_plural = 'Factures électroniques'
        ordering = ['-date_creation', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'facture_id', 'version'],
                name='uniq_einvoice_facture_version',
            ),
        ]

    def __str__(self):
        return f'{self.facture_ref or self.facture_id} v{self.version} ({self.statut})'


class TransmissionDGI(TenantModel):
    """File d'attente de transmission Simpl — inerte tant que non configurée
    (NTMAR7, étend G14). N'émet AUCUNE requête sans clé/URL configurées."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ENVOYE = 'envoye', 'Envoyé'
        ACCEPTE = 'accepte', 'Accepté'
        REJETE = 'rejete', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='transmissions_dgi', verbose_name='Société')
    einvoice = models.ForeignKey(
        FactureElectronique,
        on_delete=models.CASCADE,  # on_delete: la transmission suit son e-facture (pas de transmission orpheline)
        related_name='transmissions', verbose_name='Facture électronique')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE,
        verbose_name='Statut')
    reponse_json = models.JSONField(
        default=dict, blank=True, verbose_name='Réponse DGI (brute)')
    tentatives = models.PositiveIntegerField(default=0, verbose_name='Tentatives')
    prochaine_tentative = models.DateTimeField(
        null=True, blank=True, verbose_name='Prochaine tentative')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Transmission DGI'
        verbose_name_plural = 'Transmissions DGI'
        ordering = ['-date_creation', '-id']

    def __str__(self):
        return f'Transmission {self.einvoice_id} ({self.statut})'

"""NTLOG14 — ``DossierExport`` / ``PieceDossierExport``.

NTLOG10 (« ``DossierImport`` ») reste BLOCKED — voir ``apps/douane/apps.py``
pour la GARDE 2026-07-18 (WIR80) : le modèle entre en conflit avec
``installations.DossierImport`` (FG315, app du domaine PLAN_SERVICE, hors
périmètre d'écriture de cette lane SUPPLY). NTLOG11/12/13/21/22/26/30 en
dépendent tous directement et restent BLOCKED avec lui.

``DossierExport`` est symétrique par la FORME (mêmes familles de champs :
numéro, incoterm, ports, statut, devise) mais INDÉPENDANT par le FOND —
aucun modèle export équivalent n'existe ailleurs dans le dépôt, donc aucune
réconciliation requise ici.

Cross-app : ``ventes.Devis`` / ``facturation.Facture`` en STRING-FK
uniquement (lecture — jamais un import de leurs modèles). Pièces jointes via
``records.Attachment`` par FK à chaîne (magasin de fichiers déjà existant,
jamais un ``FileField`` brut — ARC26).
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


def _defaut_alerte_jours():
    """NTLOG36 — J-30/J-15/J-7 (fonction nommée, pas un ``lambda`` : un
    ``default`` de ``JSONField`` doit rester sérialisable en migration)."""
    return [30, 15, 7]


class DossierExport(TenantModel):
    """NTLOG14 — dossier d'export vers un client étranger. ``numero`` attribué
    côté serveur via ``core.numbering`` (plus-haut-utilisé+1 par société,
    JAMAIS ``count()+1`` — ARC6)."""

    class Incoterm(models.TextChoices):
        EXW = 'exw', 'EXW — À l\'usine'
        FOB = 'fob', 'FOB — Franco à bord'
        CFR = 'cfr', 'CFR — Coût et fret'
        CIF = 'cif', 'CIF — Coût, assurance, fret'
        DAP = 'dap', 'DAP — Rendu au lieu'
        DDP = 'ddp', 'DDP — Rendu droits acquittés'

    class Statut(models.TextChoices):
        # Machine indépendante du statut douanier import (NTLOG10, BLOCKED) —
        # propre au processus documentaire d'export.
        A_PREPARER = 'a_preparer', 'À préparer'
        DUM_DEPOSEE = 'dum_deposee', 'DUM déposée'
        EN_DEDOUANEMENT = 'en_dedouanement', 'En dédouanement'
        LEVE = 'leve', 'Levé'
        CLOTURE = 'cloture', 'Clôturé'

    numero = models.CharField(max_length=30, blank=True, default='', db_index=True)
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='dossiers_export', verbose_name='Devis lié')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='dossiers_export', verbose_name='Facture liée')
    incoterm = models.CharField(
        max_length=3, choices=Incoterm.choices, blank=True, default='')
    port_embarquement = models.CharField(max_length=120, blank=True, default='')
    port_debarquement = models.CharField(max_length=120, blank=True, default='')
    # Pas de champ « pays » structuré en amont (ni crm.Client ni
    # facturation.Facture) : capturé explicitement à la création (voir
    # services.creer_dossier_export_depuis_facture), jamais deviné.
    pays_destinataire = models.CharField(max_length=100, blank=True, default='')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.A_PREPARER)
    devise = models.CharField(max_length=3, blank=True, default='')
    valeur_marchandise_devise = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    note = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dossiers_export_crees')

    class Meta:
        verbose_name = "Dossier d'export"
        verbose_name_plural = "Dossiers d'export"
        ordering = ['-created_at']
        unique_together = [('company', 'numero')]
        indexes = [
            models.Index(fields=['company', 'statut'], name='idx_exp_co_statut'),
        ]

    def __str__(self):
        return self.numero or f'Dossier export #{self.pk}'


class PieceDossierExport(TenantModel):
    """NTLOG14 — pièce requise/déposée d'un dossier d'export. Le fichier
    lui-même vit dans ``records.Attachment`` (jamais un ``file_key`` brut ici
    — ARC26) ; ce modèle porte seulement le SLOT documentaire (type/statut).

    Porte sa PROPRE FK ``company`` (héritée de ``TenantModel``, redondante
    avec ``dossier.company``) — même motif que ``installations.FraisImport``
    (enfant d'un dossier qui garde tout de même sa FK société propre) : ça
    permet à ``PieceDossierExportViewSet`` d'hériter tel quel de
    ``CompanyScopedModelViewSet`` (filtrage/permission standard) sans
    traverser ``dossier__company`` à chaque requête."""

    class TypePiece(models.TextChoices):
        FACTURE_EXPORT = 'facture_export', 'Facture export'
        PACKING_LIST = 'packing_list', 'Packing list'
        CERTIFICAT_ORIGINE = 'certificat_origine', "Certificat d'origine"
        DUM_EXPORT = 'dum_export', 'DUM export'
        EUR1 = 'eur1', 'EUR.1'

    class StatutPiece(models.TextChoices):
        MANQUANTE = 'manquante', 'Manquante'
        DEPOSEE = 'deposee', 'Déposée'
        VALIDEE = 'validee', 'Validée'

    dossier = models.ForeignKey(
        DossierExport, on_delete=models.CASCADE,  # on_delete: composition (parent-enfant)
        related_name='pieces')
    type_piece = models.CharField(max_length=24, choices=TypePiece.choices)
    statut_piece = models.CharField(
        max_length=10, choices=StatutPiece.choices, default=StatutPiece.MANQUANTE)
    date_depot = models.DateField(null=True, blank=True)
    attachment = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pieces_dossier_export')

    class Meta:
        verbose_name = "Pièce de dossier d'export"
        verbose_name_plural = "Pièces de dossier d'export"
        ordering = ['type_piece']
        unique_together = [('dossier', 'type_piece')]

    def __str__(self):
        return f'{self.get_type_piece_display()} · {self.get_statut_piece_display()}'


class ParametresDouane(TenantModel):
    """NTLOG36 — réglages du module douane, un par société (motif
    ``adminops.AdminOpsSettings``/``stock.AchatsParametres`` : singleton
    accédé via ``for_company``, jamais via ``count()+1`` ni un ``get()`` qui
    plante s'il manque). Hérite de ``TenantModel`` mais REdéclare ``company``
    en ``OneToOneField`` (motif ARC1/SCA4 documenté sur ``TenantModel`` —
    un ``company = models.OneToOneField`` hors-socle NON précédé de
    ``TenantModel`` dans les bases casserait le garde CI ``check_platform.py``
    « pas de nouvelle FK company à la main »).
    ``alerte_expiration_jours`` alimente NTLOG22/23 (échéances engagement/
    grille tarifaire) ; ``mention_estimation_droits`` est le libellé affiché
    sur l'estimation droits/taxes (NTLOG13) et le PDF de synthèse transitaire
    (NTLOG30) — NTLOG13/30 restent BLOCKED (dépendent de NTLOG10) donc rien
    ne consomme encore ce champ, mais son contrat est déjà fixé pour eux."""

    class RegimeDouanier(models.TextChoices):
        MISE_CONSOMMATION = 'mise_consommation', 'Mise à la consommation'
        ADMISSION_TEMPORAIRE = 'admission_temporaire', 'Admission temporaire'
        ENTREPOT_DOUANE = 'entrepot_douane', 'Entrepôt sous douane'
        TRANSIT = 'transit', 'Transit'
        PERFECTIONNEMENT_ACTIF = 'perfectionnement_actif', 'Perfectionnement actif'

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: réglages liés au cycle de vie de la société
        related_name='douane_parametres', verbose_name='Société')
    regime_douanier_par_defaut = models.CharField(
        max_length=24, choices=RegimeDouanier.choices,
        default=RegimeDouanier.MISE_CONSOMMATION)
    # Liste de jours avant échéance (J-30/J-15/J-7 par défaut) — NTLOG22/23
    # notifient à chacun de ces paliers, jamais un seul seuil fixe.
    alerte_expiration_jours = models.JSONField(default=_defaut_alerte_jours)
    mention_estimation_droits = models.TextField(
        blank=True,
        default='Estimation — non contractuelle, barème à vérifier à jour.')

    class Meta:
        verbose_name = 'Paramètres douane'
        verbose_name_plural = 'Paramètres douane'

    def __str__(self):
        return f'Paramètres douane — {self.company}'

    @classmethod
    def for_company(cls, company):
        obj, _ = cls.objects.get_or_create(company=company)
        return obj

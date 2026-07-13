"""
FG315 — Suivi import / dédouanement.

``DossierImport`` suit un conteneur importé (typiquement des panneaux) depuis la
commande à l'étranger jusqu'à la sortie de douane : incoterm, n° de connaissement
(BL), n° de conteneur, dates clés (départ / arrivée port / dédouanement) et statut
douanier. Il se rattache optionnellement à un fournisseur (``stock.Fournisseur``,
string-FK) et/ou un contrat-cadre / bon de commande fournisseur d'origine.

Cross-app : ``stock.Fournisseur`` / ``stock.BonCommandeFournisseur`` en STRING-FK
uniquement — aucun import du modèle ``stock``. Couche INDÉPENDANTE des statuts de
l'OS (le statut douanier ci-dessous est PROPRE au dossier d'import). Additif &
multi-tenant : FK ``company`` posée côté serveur.
"""
from django.conf import settings
from django.db import models


class DossierImport(models.Model):
    """FG315 — dossier d'import / dédouanement d'un conteneur. Multi-tenant :
    société posée côté serveur. Référence ``IMP-YYYYMM-NNNN`` anti-collision
    (jamais count()+1)."""

    class Incoterm(models.TextChoices):
        EXW = 'exw', 'EXW — À l\'usine'
        FOB = 'fob', 'FOB — Franco à bord'
        CFR = 'cfr', 'CFR — Coût et fret'
        CIF = 'cif', 'CIF — Coût, assurance, fret'
        DAP = 'dap', 'DAP — Rendu au lieu'
        DDP = 'ddp', 'DDP — Rendu droits acquittés'

    class StatutDouane(models.TextChoices):
        # Machine à états PROPRE au dossier d'import.
        COMMANDE = 'commande', 'Commandé'
        EXPEDIE = 'expedie', 'Expédié'
        ARRIVE_PORT = 'arrive_port', 'Arrivé au port'
        EN_DOUANE = 'en_douane', 'En cours de dédouanement'
        DEDOUANE = 'dedouane', 'Dédouané'
        LIVRE = 'livre', 'Livré'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_dossiers_import')
    reference = models.CharField(max_length=50)
    designation = models.CharField(max_length=255)
    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_dossiers_import')
    bon_commande = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_dossiers_import')
    # max_length=3 couvre tous les incoterms ('ddp', 'cif'…).
    incoterm = models.CharField(
        max_length=3, choices=Incoterm.choices, blank=True, null=True)
    numero_bl = models.CharField(max_length=80, blank=True, null=True)
    numero_conteneur = models.CharField(max_length=40, blank=True, null=True)
    port_arrivee = models.CharField(max_length=120, blank=True, null=True)
    date_depart = models.DateField(null=True, blank=True)
    date_arrivee_port = models.DateField(null=True, blank=True)
    date_dedouanement = models.DateField(null=True, blank=True)
    # max_length=20 couvre 'arrive_port' (11) / 'en_douane' (9).
    statut_douane = models.CharField(
        max_length=20, choices=StatutDouane.choices,
        default=StatutDouane.COMMANDE)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_dossiers_import_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dossier d'import"
        verbose_name_plural = "Dossiers d'import"
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            # Noms d'index ≤ 30 caractères.
            models.Index(fields=['company', 'statut_douane'],
                         name='idx_imp_co_statut'),
            models.Index(fields=['company', 'fournisseur'],
                         name='idx_imp_co_fournisseur'),
        ]

    def __str__(self):
        return f'{self.reference} · {self.designation}'
